# 🚀 turbo-tosec

[![CI/CD](https://github.com/berkacunas/turbo-tosec/actions/workflows/release.yml/badge.svg)](https://github.com/berkacunas/turbo-tosec/actions/workflows/release.yml)
[![License: GPL v3](https://img.shields.io/badge/License-GPL_v3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Latest Release](https://img.shields.io/github/v/release/berkacunas/turbo-tosec)](https://github.com/berkacunas/turbo-tosec/releases)

> **High-performance, DuckDB-based importer to query TOSEC databases at light speed.**

**turbo-tosec** scans, parses, and converts the massive **TOSEC (The Old School Emulation Center)** DAT collection into a single, instantly queryable **DuckDB** database file.

Designed for archivists and retro gaming enthusiasts, it transforms piles of hundreds of thousands of XML/DAT files into a modern format that can be queried via SQL in seconds.

---

### 📥 Download Now (No Python Required)

If you don't want to install Python, simply download the standalone executable for your OS:

* **Windows:** [Download `turbo-tosec_v1.3.3_Windows.exe`](https://github.com/berkacunas/turbo-tosec/releases/latest)
* **Linux:** [Download `turbo-tosec_v1.3.3_Linux.tar.gz`](https://github.com/berkacunas/turbo-tosec/releases/latest)

---

## ⚡ Why turbo-tosec?

  - **Speed Driven:** Combines Python's XML parsing power with DuckDB's "Bulk Insert" capabilities for maximum throughput.
  - **Zero Dependencies:** No need for external servers (MySQL, Postgres). The output is a single, portable `.duckdb` file.
  - **Smart Scanning:** Automatically finds thousands of `.dat` files in nested subdirectories (`recursive scan`).
  - **Progress Tracking:** Detailed, real-time progress bar via `tqdm`.

## 📦 Installation

This project requires Python 3.x.

```bash
git clone https://github.com/berkacunas/turbo-tosec.git
cd turbo-tosec
pip install -r requirements.txt
```

## 🛠️ Usage

### 1\. Prepare the Data

This tool processes TOSEC DAT files (metadata). Download the latest DAT package from the [Official TOSEC Website](https://www.tosecdev.org/downloads) and extract it to a folder.

### 2\. Run the Importer

#### Standard Mode (Safe)
Best for debugging or small collections. Uses a single thread.
```bash
python tosec_importer.py -i "/path/to/TOSEC" -o "tosec.duckdb"
```

#### Turbo Mode (Multi-Threaded) 🔥

Unleash the full power of your CPU\! Recommended for full TOSEC imports.

```bash
# Use 8 worker threads and larger batch size
python tosec_importer.py -i "/path/to/TOSEC" -w 8 -b 5000
```

#### CLI Arguments

| Flag | Description | Default |
| :--- | :--- | :--- |
| `-i, --input` | Path to the root directory containing DAT files. | **Required** |
| `-o, --output` | Path for the output DuckDB database. | `tosec.duckdb` |
| `-w, --workers` | Number of parallel parsing threads. | `1` |
| `-b, --batch-size`| Number of records to insert per DB transaction. | `1000` |
| `--no-open-log` | Do NOT automatically open the log file on error. | `False` |

## ⚡ Performance

*Benchmarks based on a dataset of \~3,000 DAT files (approx. 1 million ROM entries).*

| Mode | Workers | Time |
| :--- | :--- | :--- |
| **Standard** | 1 | \~45 seconds |
| **Turbo** | 4 | \~15 seconds |
| **Turbo Max** | 8 | \~9 seconds |

> *Note: Performance scales well with core count until disk I/O becomes the bottleneck.*

## 🔍 Example Queries (DuckDB / SQL)

You can open the generated database using **DBeaver**, **VSCode SQLTools**, or **Python** to run queries like these:

**Find Verified [\!] Commodore 64 Games:**

```sql
SELECT game_name, rom_name 
FROM roms 
WHERE platform LIKE '%Commodore 64%' 
  AND rom_name LIKE '%[!]%';
```

**Verify a Local File (via Hash):**

```sql
SELECT * FROM roms WHERE md5 = 'YOUR_FILE_MD5_HASH_HERE';
```

## 📄 License

This project is licensed under the **GNU General Public License v3.0 (GPL-3.0)**.

--- 
## ❤️ Support the Project

turbo-tosec is developed and maintained by an independent developer. If you find this tool useful and want to support its continued development (or simply want to say thanks for the pre-built `.exe`), please consider making a donation!

<a href="https://github.com/sponsors/berkacunas">
  <img src="https://img.shields.io/badge/Sponsor-GitHub-pink?style=for-the-badge&logo=github-sponsors" height="50" alt="Sponsor on GitHub">
</a>

<a href="https://www.buymeacoffee.com/depones" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" style="height: 60px !important;width: 217px !important;" ></a>

* **Star this repo!** ⭐ It helps visibility.

---
*Disclaimer: This project does not contain TOSEC database files or ROMs. It strictly provides a tool to process the metadata files provided by the TOSEC project.*

**Copyright © 2025 berkacunas & DeponesStudio.**