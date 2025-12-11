import os
from typing import List, Tuple
import threading
import concurrent.futures
import time
from tqdm import tqdm
import logging

from turbo_tosec.database import DatabaseManager
from turbo_tosec.parser import DatFileParser

def get_dat_files(root_dir: str) -> List[str]:
    """
    Finds all .dat files in the specified directory and its subdirectories.
    """
    dat_files = []
    for root, _, files in os.walk(root_dir):
        for file in files:
            if file.lower().endswith(".dat"):
                dat_files.append(os.path.join(root, file))
                
    return dat_files

class ImportSession:
    """
    Orchestrates the scanning, parsing, and database insertion workflow.
    """
    def __init__(self, args, db_manager: DatabaseManager, all_files: List[str]):
        
        self.args = args
        self.db = db_manager
        self.parser = DatFileParser()
        self.buffer = []
        self.total_roms = 0
        self.error_count = 0
        self.all_files = all_files

    def run(self, files_to_process: List[str]):
        """
        Executes the import process.
        """
        print("Calculating total size for progress bar...")
        total_bytes = sum(os.path.getsize(f) for f in self.all_files)
        remaining_bytes = sum(os.path.getsize(f) for f in files_to_process)
        initial_bytes = total_bytes - remaining_bytes
        print(f"Starting import with {self.args.workers} worker(s)...")

        try:
            with tqdm(total=total_bytes, initial=initial_bytes, unit='B', unit_scale=True, unit_divisor=1024) as pbar:
                # Monitör Thread
                stop_monitor = threading.Event()
                def monitor_progress():
                    while not stop_monitor.is_set():
                        time.sleep(1)
                        pbar.refresh()
                
                monitor_thread = threading.Thread(target=monitor_progress, daemon=True)
                monitor_thread.start()

                # Start workers
                if self.args.workers < 2:
                    self._run_serial(files_to_process, pbar)
                else:
                    self._run_parallel(files_to_process, pbar)

                stop_monitor.set()
                monitor_thread.join()

            self._flush_buffer() # Write any remaining data

        except KeyboardInterrupt:
            print("\nInterrupted.")
        except Exception as error:
            print(f"\nCritical Error: {error}")

        return self.total_roms, self.error_count

    def _flush_buffer(self):
        if self.buffer:
            self.db.insert_batch(self.buffer)
            self.total_roms += len(self.buffer)
            self.buffer.clear()

    def _process_result(self, data, file_path, pbar):
        """
        Common logic for handling a parsed file result.
        """
        if data:
            self.buffer.extend(data)
            if len(self.buffer) >= self.args.batch_size:
                self._flush_buffer()
        
        # Update stats
        stats = {"ROMs": self.total_roms}
        if self.error_count > 0:
            stats["Errors"] = self.error_count
        pbar.set_postfix(stats)
        
        try:
            pbar.update(os.path.getsize(file_path))
        except:
            pbar.update(0)

    def _run_serial(self, files, pbar):
        
        for file_path in files:
            try:
                data = self.parser.parse(file_path)
                self._process_result(data, file_path, pbar)
                
            except Exception as error:
                error_msg = str(error).lower()
                # If disk is full or read-only, stop the program
                if "not enough space" in error_msg or "read-only file system" in error_msg:
                    raise OSError("CRITICAL: Disk is full or not writable!") from error
                
                self.error_count += 1
                logging.error(f"Failed (Serial): {file_path} -> {error}")

    def _run_parallel(self, files, pbar):
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.args.workers) as executor:
            # parser.parse method is thread-safe (stateless)
            future_to_file = {executor.submit(self.parser.parse, f): f for f in files}
            
            for future in concurrent.futures.as_completed(future_to_file):
                file_path = future_to_file[future]
                try:
                    data = future.result()
                    self._process_result(data, file_path, pbar)
                    
                except Exception as error:
                    error_msg = str(error).lower()
                    # If disk is full or read-only, stop the program
                    if "not enough space" in error_msg or "read-only file system" in error_msg:
                        # Try to shut down the thread pool immediately
                        executor.shutdown(wait=False, cancel_futures=True)
                        raise OSError("CRITICAL: Disk is full or not writable!") from error
                
                    self.error_count += 1
                    logging.error(f"Failed: {file_path} -> {error}")