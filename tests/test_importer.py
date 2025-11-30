import os
import pytest
import duckdb
from tosec_importer import parse_dat_file, create_database
from _version import __version__

SAMPLE_DAT_XML = """<?xml version="1.0"?>
<datafile>
    <header>
        <name>Commodore 64 - Games - T (TOSEC-v2020-01-01)</name>
        <description>Commodore 64 - Games - T (TOSEC-v2020-01-01)</description>
    </header>
    <game name="Test Game (1986)">
        <description>Test Game Desc</description>
        <rom name="test.tap" size="100" crc="123" md5="abc" sha1="def"/>
    </game>
</datafile>
"""

def test_platform_parsing(tmp_path):
    """
    XML parsing mantığını ve 'system' (klasör) adı çıkarma işlemini test eder.
    """
    filename = "Commodore 64 - Games - T (TOSEC-v2020).dat"
    
    dats_dir = tmp_path / "dats"
    dats_dir.mkdir()
    dat_file = dats_dir / filename
    dat_file.write_text(SAMPLE_DAT_XML, encoding="utf-8")

    results = parse_dat_file(str(dat_file))

    assert len(results) == 1, "Parser should have found exactly 1 game"
    
    row = results[0]
    assert row[0] == filename
    assert row[1] == "Commodore 64" # platform extracted from filename
    assert row[2] == "Test Game (1986)"

def test_database_integration(tmp_path):
   
    db_path = str(tmp_path / "test.duckdb")
    conn = create_database(db_path)
    
    mock_data = [
        ("Amiga.dat", "Commodore Amiga", "Game X", "Desc", "rom.adf", 500, "c", "m", "s", "good", "folder")
    ]
    
    conn.executemany("INSERT INTO roms VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", mock_data)
    
    res = conn.execute("SELECT platform FROM roms").fetchone()
    assert res[0] == "Commodore Amiga"
    
    conn.close()
