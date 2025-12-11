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
- **Console:** Kept clean for the progress bar. Only critical crashes are printed
- **Log File:** All skipped files, malformed XMLs, or read errors are written to `import_errors.log`.
- **Resilience:** A single corrupt file does not stop the process. It is logged and skipped.

Usage:
    python tosec_importer.py scan -i "path/to/dats" -w 8
    python tosec_importer.py parquet -o "backup.parquet"

Author: Depones Studio
License: GPL v3
"""
import os
import re
import sys
from datetime import datetime
import time
import argparse
import logging
import subprocess
import platform

from turbo_tosec.database import DatabaseManager
from turbo_tosec.session import ImportSession
from turbo_tosec.utils import get_dat_files
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
        print(f"\nCould not open log file automatically: {e}")
        
def extract_tosec_version(path: str) -> str:
    # Example pattern: TOSEC-v2023-08-15
    match = re.search(r"(TOSEC-v\d{4}-\d{2}-\d{2})", path, re.IGNORECASE)
    if match:
        return match.group(1)
    return "Unknown"

def run_scan_mode(args, log_filename: str):
    """
    Orchestrates the scanning process using the new OOP architecture.
    """
    # 1. Setting up logging
    setup_logging(log_filename)

    start_time = time.time()
    
    # 2. Scan for .dat files
    print(f"Scanning directory: {args.input}...")
    all_dat_files = get_dat_files(args.input)
    
    if not all_dat_files:
        print("No .dat files found. Exiting.")
        return

    # 3. Detect TOSEC Version
    current_version = extract_tosec_version(args.input)
    print(f"Detected Input Version: {current_version}")

    # Database Context Manager for safe handling (auto connect/close)
    with DatabaseManager(args.output) as db:
        
        # Resume / Wipe Decision Logic
        resume_mode = False
        db_version = db.get_metadata_value('tosec_version')
        
        # A. Version Mismatch Check
        if db_version and db_version != current_version:
            print(f"\nWARNING: Version Mismatch! (DB: {db_version} vs Input: {current_version})")
            
            if args.force_new:
                print("--force-new detected. Wiping old database.")
                resume_mode = False
            else:
                q = input("Start FRESH and wipe old database? (Required for new version) [y/N]: ").lower()
                if q != 'y': 
                    print("Operation aborted.")
                    return
                resume_mode = False
        
        # B. Version is compatible, ask about resuming
        else:
            processed_files = db.get_processed_files()
            if processed_files:
                if args.resume:
                    resume_mode = True
                elif args.force_new:
                    resume_mode = False
                else:
                    print(f"\nFound {len(processed_files)} processed files.")
                    q = input("[R]esume or [S]tart fresh? [R/s]: ").lower()
                    resume_mode = (q != 's')
        
        files_to_process = []
        
        if not resume_mode:
            #Start from scratch
            print("Wiping database...")
            db.wipe_database()
            db.set_metadata_value('tosec_version', current_version)
            files_to_process = all_dat_files
        else:
            # Resume from last state
            print("Calculating resume list...")
            processed_set = db.get_processed_files()
            files_to_process = [f for f in all_dat_files if os.path.basename(f) not in processed_set]
            
            skipped = len(all_dat_files) - len(files_to_process)
            print(f"Resuming: {skipped} files skipped. {len(files_to_process)} remaining.")

        if not files_to_process:
            print("Nothing to do. All files processed.")
            return

        db.configure_threads(args.workers)
        
        session = ImportSession(args, db, all_dat_files)
        total_roms, error_count = session.run(files_to_process)

    end_time = time.time()
    duration = end_time - start_time
    
    print("\nTransaction completed!")
    print(f"Database: {args.output}")
    print(f"Total ROMs: {total_roms:,}")
    print(f"Elapsed Time: {duration:.2f}s")
    
    if error_count > 0:
        print(f"\nWARNING: {error_count} files failed.")
        if args.open_log: 
            open_file_with_default_app(log_filename)
    else:
        logging.shutdown()
        if os.path.exists(log_filename): 
            try: os.remove(log_filename)
            except: pass
        print("Clean import.")

def run_parquet_mode(args):
    """
    Handles Parquet import/export operations.
    """
    with DatabaseManager(args.db) as db:
        if args.export_file:
            db.export_to_parquet(args.export_file, args.workers)
        elif args.import_file:
            db.import_from_parquet(args.import_file, args.workers)

def main():

    # Backward Compatibility Hack
    # If no subcommand given, and not asking for help/version, add 'scan' as default command.
    if len(sys.argv) > 1 and sys.argv[1] not in ['scan', 'parquet', '--help', '-h', '--version', '-v', '--about']:
        sys.argv.insert(1, 'scan')    
    
    parser = argparse.ArgumentParser(description="High-performance TOSEC DAT importer using DuckDB.")
    
    # Global arguments (may apply to all commands)
        # About & Version
    parser.add_argument("--about", action="store_true", help="Show program information, philosophy, and safety defaults.")
    parser.add_argument("--version", "-v", action="version", version=f"{__version__ if '__version__' in globals() else '1.2.2'}")

    # Sub-commands for different modes
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Scan Command (Main Mode)
    parser_scan = subparsers.add_parser("scan", help="Scan DAT files and import to DB (Default mode).")
    parser_scan.add_argument("--input", "-i", required=True, help="The main directory path where the TOSEC DAT files are located.")
    parser_scan.add_argument("--output", "-o", default="tosec.duckdb", help="Name/path of the DuckDB file to be created.")
    parser_scan.add_argument("--workers", "-w", type=int, default=1, help="Number of worker threads (Default: 1). Tip: Use 0 to auto-detect CPU count.")
    parser_scan.add_argument("--batch-size", "-b", type=int, default=1000, help="Number of rows to insert per batch transaction (Default: 1000).")
    parser_scan.add_argument("--resume", action="store_true", help="Automatically resume if database exists (skip prompt).")
    parser_scan.add_argument("--force-new", action="store_true", help="Force overwrite existing database (skip prompt).")
    parser_scan.add_argument("--no-open-log", action="store_false", dest="open_log", default=True, help="Do NOT automatically open the log file if errors occur.")

    # Parquet Command (Import/Export)
    parser_parquet = subparsers.add_parser("parquet", help="Import/Export data using Parquet files.")
    parser_parquet.add_argument("--db", "-d", default="tosec.duckdb", help="Target/Source DuckDB file.")
    parser_parquet.add_argument("--workers", "-w", type=int, default=1, help="Max threads for DuckDB engine (Default: 1).")
    group = parser_parquet.add_mutually_exclusive_group(required=True)
    group.add_argument("--import-file", "-i", help="Import FROM this Parquet file.")
    group.add_argument("--export-file", "-o", help="Export TO this Parquet file.")
    
    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)
        
    args = parser.parse_args()
        
    if args.about:
        print(f"""
 *** turbo-tosec v{__version__} ***
 A high-performance, DuckDB-based importer for TOSEC DAT collections.

 ** SAFETY FIRST PHILOSOPHY
 turbo-tosec is designed to handle massive datasets without freezing your
 system. By default, it runs in **SINGLE-THREADED (SAFE) MODE**.

 This tool respects your hardware limits. It does not auto-detect your CPU cores
 to prevent system unresponsiveness during large imports.

 ** WANT SPEED? (TURBO MODE)
 If you want to unleash the full power of your CPU, you must explicitly
 ask for it by using the '--workers' (or '-w') flag.
 
 Example: python tosec_importer.py -i "..." -w 8
 
 MODES
 ---------------------------
1.  SCAN (Default): Reads XML DATs -> DuckDB
    Usage: turbo-tosec scan -i "<input_file>" -w 8

2.  PARQUET: Import/Export DuckDB <-> Parquet
    Usage: turbo-tosec parquet -o "backup.parquet"

 ---------------------------
 Author:  Berk Acunas & Depones Studio
 License: GPL v3 (Open Source)
 GitHub:  https://github.com/berkacunas/turbo-tosec
""")
        return
    
    log_filename = None
    
    try:
        if args.command == "parquet":
            run_parquet_mode(args)
            
        elif args.command == "scan":
            if args.workers > 4:
                print(f"  WARNING: Using {args.workers} threads.")
                print("   If you are using a mechanical HDD, performance may drop due to seek time.")
                print("   Recommended for HDD: 1-4 threads. Recommended for SSD: 4-16 threads.")
            if not args.input:
                parser.error("the following arguments are required: --input/-i")
                
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            os.makedirs("logs", exist_ok=True)
            log_filename = os.path.join("logs", f"tosec_import_log_{timestamp}.log")
            
            run_scan_mode(args, log_filename)
    except KeyboardInterrupt:
        print("\n  Process interrupted by user.")
        return
    except OSError as e:
        if "Disk is full" in str(e):
            print(f"\n\nCRITICAL STORAGE ERROR: {e}")
            print("   The operation was stopped to prevent data corruption.")
            print("   Please free up space and try again (use --resume).")
            
            logging.shutdown()
            if args.open_log:
                print("   Opening log file for details...")
                open_file_with_default_app(log_filename)
            
            sys.exit(1)
        else:
            # Standard behavior for other OSErrors
            print(f"\nOS Error: {e}")
            sys.exit(1)
    # Critical system errors
    except (RuntimeError, MemoryError) as e:
        print(f"\n\nCRITICAL ERROR: System resources exhausted!")
        print(f"Details: {e}")
        print(f"Tip: Try reducing --workers (current: {args.workers}) or --batch-size (current: {args.batch_size}).")
        print("Exiting safely to prevent crash...")
        return
    except Exception as e:
        print(f"\n  Critical Error: {e}")
        return
        
if __name__ == "__main__":
    
    main()
