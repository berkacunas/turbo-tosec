"""
Turbo-TOSEC: High-Performance TOSEC DAT Importer
================================================

This module parses TOSEC DAT files (XML format) and imports them into a DuckDB database.
It is designed to handle massive collections efficiently using multi-threading.

Architecture & Concurrency Design
---------------------------------
The importer uses a "Producer-Consumer" pattern adapted for DuckDB's single-writer constraint:

1.  **Workers (Producers):**
    - Managed by a `ThreadPoolExecutor`.
    - Responsible for I/O (reading files) and CPU (parsing XML) tasks.
    - They do NOT write to the database. They return parsed tuples to the main thread.
    - This ensures thread-safety without complex locking mechanisms.

2.  **Main Thread (Consumer & Writer):**
    - Submits tasks to workers.
    - Collects results as they complete (`as_completed`).
    - Buffers results and performs batched inserts (`executemany`) into DuckDB.
    - Updates the progress bar (`tqdm`).

Error Handling Strategy
-----------------------
- **Console:** Kept clean for the progress bar. Only critical crashes are printed.
- **Log File:** All skipped files, malformed XMLs, or read errors are written to `import_errors.log`.
- **Resilience:** A single corrupt file does not stop the process. It is logged and skipped.

Usage:
    python tosec_importer.py -i "path/to/dats" -w 8

Author: Depones Studio
License: GPL v3
"""
import os
import sys
from datetime import datetime
import time
import argparse
import xml.etree.ElementTree as ET
from typing import List, Tuple, Optional
import duckdb
from tqdm import tqdm 
import concurrent.futures
import logging
import subprocess
import platform
from _version import __version__


def setup_logging(log_file: str):
   
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)

    logging.basicConfig(level=logging.ERROR, 
            format="%(asctime)s [%(levelname)s] %(message)s",
            handlers=[logging.FileHandler(log_file, mode='w', encoding='utf-8')]
    )

def open_file_with_default_app(filepath):

    try:
        if platform.system() == 'Windows':
            os.startfile(filepath)
        elif platform.system() == 'Darwin': # macOS
            subprocess.call(('open', filepath))
        else: # Linux
            subprocess.call(('xdg-open', filepath))
    except Exception as e:
        print(f"\n⚠️ Could not open log file automatically: {e}")
        
def create_database(db_path: str):
    
    conn = duckdb.connect(db_path)
    
    conn.execute("DROP TABLE IF EXISTS roms")
    conn.execute("""
        CREATE TABLE roms (
            dat_filename VARCHAR,
            platform VARCHAR,
            game_name VARCHAR,
            description VARCHAR,
            rom_name VARCHAR,
            size BIGINT,
            crc VARCHAR,
            md5 VARCHAR,
            sha1 VARCHAR,
            status VARCHAR,
            system VARCHAR
        )
    """)
    return conn

def get_dat_files(root_dir: str) -> List[str]:
    
    dat_files = []
    
    for root, _, files in os.walk(root_dir):
        for file in files:
            if file.lower().endswith(".dat"):
                dat_files.append(os.path.join(root, file))
                
    return dat_files

def parse_dat_file(file_path: str) -> List[Tuple]:
    """
    Parses a single DAT file and returns a list of tuples.
    Safe to run in a worker thread (no DB access here).
    """
    rows = []
    
    dat_filename = os.path.basename(file_path)
    try:
        system_name = os.path.basename(os.path.dirname(file_path))
    except:
        system_name = "Unknown"

    platform = dat_filename.split(' - ')[0]

    tree = ET.parse(file_path)
    root = tree.getroot()
    
    for game in root.findall('game'):
        game_name = game.get('name')
        # Description may be missing sometimes, take it safe
        desc_node = game.find('description')
        description = desc_node.text if desc_node is not None else ""
        
        for rom in game.findall('rom'):
            rows.append((dat_filename, platform, game_name, description, 
                         rom.get('name'), rom.get('size'), rom.get('crc'), rom.get('md5'), 
                         rom.get('sha1'), rom.get('status', 'good'), system_name))

    return rows

def main():

    parser = argparse.ArgumentParser(description="Imports TOSEC DAT files into DuckDB database.")
    parser.add_argument("--input", "-i", help="The main directory path where the TOSEC DAT files are located.")
    parser.add_argument("--output", "-o", default="tosec.duckdb", help="Name/path of the DuckDB file to be created.")
    parser.add_argument("--workers", "-w", type=int, default=1, help="Number of worker threads (Default: 1). Tip: Use 0 to auto-detect CPU count.")
    parser.add_argument("--batch-size", "-b", type=int, default=1000, help="Number of rows to insert per batch transaction (Default: 1000).")
    parser.add_argument("--no-open-log", action="store_false", dest="open_log", default=True, help="Do NOT automatically open the log file if errors occur.")
    parser.add_argument("--about", action="store_true", help="Show program information, philosophy, and safety defaults.")
    parser.add_argument("--version", "-v", action="version", version=f"{__version__ if '__version__' in globals() else '1.2.2'}")
    
    args = parser.parse_args()
    
    if args.about:
        print(f"""
 *** turbo-tosec v{__version__ if '__version__' in globals() else '1.2.2'} ***
 A high-performance, DuckDB-based importer for TOSEC DAT collections.

 ** SAFETY FIRST PHILOSOPHY
 This tool is designed to handle massive datasets without freezing your
 system. By default, it runs in **SINGLE-THREADED (SAFE) MODE**.

 We respect your hardware limits. We do not auto-detect your CPU cores
 to prevent system unresponsiveness during large imports.

 ** WANT SPEED? (TURBO MODE)
 If you want to unleash the full power of your CPU, you must explicitly
 ask for it by using the '--workers' (or '-w') flag.
 
 Example: python tosec_importer.py -i "..." -w 8
""")
        return
    
    if not args.input:
        parser.error("the following arguments are required: --input/-i")
        
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    
    os.makedirs("logs", exist_ok=True)
    log_filename = os.path.join("logs", f"tosec_import_log_{timestamp}.log")
    
    setup_logging(log_filename)
    start_time = time.time()
    
    print(f"📂 Scanning directory: {args.input}...")
    all_dat_files = get_dat_files(args.input)
    count_files = len(all_dat_files)
    print(f"📄 A total of {count_files} .dat files were found.")

    if not all_dat_files:
        print("❌ No .dat file found. Exiting.")
        return

    conn = create_database(args.output)
    
    total_roms = 0
    error_count = 0
    if args.workers == 0: 
        args.workers = os.cpu_count() or 1
        
    print(f"🚀 Starting import with {args.workers} worker(s)...", flush=True)
    
    buffer = []
    
    def flush_buffer():
        nonlocal total_roms
        if buffer:
            conn.executemany("""INSERT INTO roms VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", buffer)
            total_roms += len(buffer)
            buffer.clear()
    
    # --- PROCESSING LOGIC ---
    if args.workers < 2:
        # ### SERIAL MODE (Default) ###
        # No overhead of threading, best for debugging or small tasks.
        with tqdm(total=count_files, unit="file") as pbar:
            for file_path in all_dat_files:
                try:
                    data = parse_dat_file(file_path)
                    if data:
                        buffer.extend(data)
                        if len(buffer) >= args.batch_size:
                            flush_buffer()
                except Exception as exc:
                    error_count += 1
                    logging.error(f"FAILED: (Serial) {file_path} -> {exc}")
                    
                stats = {"ROMs": total_roms}
                if error_count > 0:
                    stats["Errors"] = error_count
                
                pbar.set_postfix(stats)
                pbar.update(1)
    else:
        # ### PARALLEL MODE (Turbo) ###
        # Workers parse XML, Main Thread writes to DB.
        try:
            with tqdm(total=count_files, unit="file") as pbar:
                with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
                    # Submit all tasks
                    future_to_file = {executor.submit(parse_dat_file, f): f for f in all_dat_files}
                    
                    # Process results as they complete
                    for future in concurrent.futures.as_completed(future_to_file):
                        file_path = future_to_file[future]
                        try:
                            data = future.result()
                            if data:
                                buffer.extend(data)
                                # Batch write in Main Thread
                                if len(buffer) >= args.batch_size:
                                    flush_buffer()
                        except Exception as exc:
                            error_count += 1
                            logging.error(f"FAILED: {file_path} -> {exc}")
                            
                        stats = {"ROMs": total_roms}
                        if error_count > 0:
                            stats["Errors"] = error_count
                        
                        pbar.set_postfix(stats)
                        pbar.update(1)

        except KeyboardInterrupt:
            print("\n🛑 Process interrupted by user.")
            return
        # Critical system errors
        except (RuntimeError, MemoryError) as e:
            print(f"\n\n❌ CRITICAL ERROR: System resources exhausted!")
            print(f"   Details: {e}")
            print(f"   👉 Tip: Try reducing --workers (current: {args.workers}) or --batch-size (current: {args.batch_size}).")
            print("   Exiting safely to prevent crash...")
            return
        except Exception as e:
            print(f"\n❌ Critical Error: {e}")
            return
        
    # Final flush for remaining items
    flush_buffer()
    conn.close()
    
    end_time = time.time()
    duration = end_time - start_time
    
    print("\n✅ Transaction completed!")
    print(f"💾 Database: {args.output}")
    print(f"📊 Total ROM: {total_roms:,}")  # Print with thousands separator
    print(f"⏱️ Elapsed Time: {duration:.2f} second ({duration/60:.1f} minute)")

    if error_count > 0:
        print(f"\n⚠️  WARNING: {error_count} files could not be processed!")
        print(f"📝 Details written to: {os.path.abspath(log_filename)}")
        
        if args.open_log: 
            print("launching log viewer...")
            open_file_with_default_app(log_filename)
    else:
        logging.shutdown()
        
        if os.path.exists(log_filename):
            try:
                os.remove(log_filename)
            except Exception as e:
                print(f"\n⚠️ Could not delete empty log file: {e}")
                
        print("✨ Clean import. No errors.")
        
if __name__ == "__main__":
    
    main()