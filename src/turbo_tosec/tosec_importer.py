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
import re
import sys
from datetime import datetime
import time
import argparse
import xml.etree.ElementTree as ET
from typing import List, Tuple, Optional
import duckdb
from tqdm import tqdm 
import threading
import concurrent.futures
import logging
import subprocess
import platform
from turbo_tosec._version import __version__


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
    
    # Main ROMs table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS roms (
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
    
    # Processed files tracking table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS processed_files (
            filename VARCHAR PRIMARY KEY,
            processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Metadata table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS db_metadata (
            key VARCHAR PRIMARY KEY,
            value VARCHAR
        )
    """)
    
    return conn

def extract_tosec_version(path: str) -> str:
    # Example pattern: TOSEC-v2023-08-15
    match = re.search(r"(TOSEC-v\d{4}-\d{2}-\d{2})", path, re.IGNORECASE)
    if match:
        return match.group(1)
    return "Unknown"

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
    parser.add_argument("--resume", action="store_true", help="Automatically resume if database exists (skip prompt).")
    parser.add_argument("--force-new", action="store_true", help="Force overwrite existing database (skip prompt).")
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

    current_version = extract_tosec_version(args.input)
    print(f"🔖 Detected TOSEC version: {current_version}")
    
    db_exists = os.path.exists(args.output)
    conn = create_database(args.output)

    resume_mode = False
    if db_exists:
        # Check metadata for TOSEC version
        stored_version = None
        try:
            result = conn.execute("SELECT value FROM db_metadata WHERE key = 'tosec_version'").fetchone()
            if result:
                stored_version = result[0]
        except:
            pass
        
        # Check version mismatch
        if stored_version and stored_version != current_version:
            print(f"\n⚠️  WARNING: TOSEC version mismatch!")
            print(f"   Database belongs to: {stored_version}")
            print(f"   Input directory is:  {current_version}")
            print("   Mixing versions creates a corrupted archive.")
            
            q = input("❓ Start FRESH and wipe old database? (Required for new version) [y/N]: ").lower()
            if q != 'y':
                print("🛑 Operation aborted to protect data.")
                conn.close()
                return
            # User agreed to wipe old DB
            print("🧹 Wiping old database and starting FRESH import...")
            resume_mode = False
            
        else:
            # Version matches or version unknown, resumable ?
            processed_count = conn.execute("SELECT COUNT(*) FROM processed_files").fetchone()[0]
            
            if processed_count > 0:
                # Flag Control 
                if args.resume:
                    print(f"🔄 --resume detected. Resuming import. ({processed_count} files already processed)")
                    resume_mode = True
                elif args.force_new:
                    print("💥 --force-new detected. Wiping old database.")
                    resume_mode = False
                else:
                    # Interactive Mode (Ask User)
                    print(f"\nFound existing database with {processed_count} processed files.")
                    q = input("❓ [R]esume interrupted import or [S]tart fresh? [R/s]: ").lower()
                    resume_mode = q == 'r'
            
    files_to_process = []
    
    if not resume_mode:
        print("🧹 Wiping database for fresh import...")
        conn.execute("DELETE FROM roms")
        conn.execute("DELETE FROM processed_files")
        conn.execute("DELETE FROM db_metadata") # Reset metadata
        
        # Save current TOSEC version
        conn.execute("INSERT INTO db_metadata VALUES ('tosec_version', ?)", (current_version,))
        
        files_to_process = all_dat_files
    else:
        # Resume mode: skip already processed files
        print("🔍 Calculating resume list...")
        result = conn.execute("SELECT filename FROM processed_files").fetchall()
        processed_set = {row[0] for row in result}
        
        # Take files not in processed_set
        files_to_process = [f for f in all_dat_files if os.path.basename(f) not in processed_set]
        
        skipped_count = len(all_dat_files) - len(files_to_process)
        print(f"⏩ Resuming: {skipped_count} files skipped. {len(files_to_process)} remaining.")

    if not files_to_process:
        print("✨ All files are already processed! Nothing to do.")
        conn.close()
        return
    
    count_files = len(files_to_process) # for progress bar

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
            
            unique_files = {row[0] for row in buffer}
            
            for filename in unique_files:
                # Hata vermeden ekle (Varsa atla)
                # DuckDB'de 'INSERT OR IGNORE' yerine 'INSERT OR IGNORE INTO' çalışır
                conn.execute("INSERT OR IGNORE INTO processed_files (filename) VALUES (?)", (filename,))
            
            total_roms += len(buffer)
            buffer.clear()
    
    try:
        # Processing logic 
        with tqdm(total=count_files, unit="file") as pbar:
            stop_monitor = threading.Event()
            
            def monitor_progress():
                while not stop_monitor.is_set():
                    time.sleep(1)
                    pbar.refresh()
                    
            monitor_thread = threading.Thread(target=monitor_progress, daemon=True)
            monitor_thread.start()
            
            # Serial Mode (by default)
            # No overhead of threading, best for debugging or small tasks.
            if args.workers < 2:
                for file_path in files_to_process:
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
                with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
                    # Submit all tasks
                    future_to_file = {executor.submit(parse_dat_file, f): f for f in files_to_process}
                    
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
        
            stop_monitor.set()
            monitor_thread.join()

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