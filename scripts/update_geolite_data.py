# -*- coding: utf-8 -*-
"""
update_geolite_data.py - Maintainer script for updating bundled GeoIP data.

This script automates the process of fetching the latest GeoLite2 Country
database from MaxMind, processing the CSV files, and generating a clean,
two-column `ip_ranges.csv` file for use by the InMemoryResolver.

*** USAGE ***
1.  Sign up for a free MaxMind account at https://www.maxmind.com/en/geolite2/signup
2.  Get your Account ID and a License Key from your MaxMind dashboard.
3.  Set the environment variables: MAXMIND_ACCOUNT_ID and MAXMIND_LICENSE_KEY
    (e.g., in a .env file in the project root).
4.  Run this script from the project root:
    python scripts/update_geolite_data.py
"""

import csv
import io
import os
import zipfile
from datetime import date
from pathlib import Path

import requests
from dotenv import load_dotenv

# ==============================================================================
# CONFIGURATION
# ==============================================================================

load_dotenv()

MAXMIND_ACCOUNT_ID = os.getenv("MAXMIND_ACCOUNT_ID")
MAXMIND_LICENSE_KEY = os.getenv("MAXMIND_LICENSE_KEY")

DOWNLOAD_URL = (
    "https://download.maxmind.com/app/geoip_download"
    f"?edition_id=GeoLite2-Country-CSV&license_key={MAXMIND_LICENSE_KEY}&suffix=zip"
)

PROJECT_ROOT = Path(__file__).parent.parent
OUTPUT_CSV_PATH = PROJECT_ROOT / "geofence_validator" / "data" / "ip_ranges.csv"

# Filenames we need from the archive
LOCATIONS_FILENAME = "GeoLite2-Country-Locations-en.csv"
IPV4_BLOCKS_FILENAME = "GeoLite2-Country-Blocks-IPv4.csv"
IPV6_BLOCKS_FILENAME = "GeoLite2-Country-Blocks-IPv6.csv"

# ==============================================================================
# SCRIPT LOGIC
# ==============================================================================

def fetch_data() -> bytes:
    """Downloads the GeoLite2 database from MaxMind."""
    print("Downloading GeoLite2 data from MaxMind...")
    if not MAXMIND_ACCOUNT_ID or not MAXMIND_LICENSE_KEY:
        raise ValueError(
            "MAXMIND_ACCOUNT_ID and MAXMIND_LICENSE_KEY environment variables must be set."
        )

    response = requests.get(DOWNLOAD_URL, timeout=60)
    response.raise_for_status()
    print("Download complete.")
    return response.content


def process_zip_data(zip_content: bytes) -> list[tuple[str, str]]:
    """
    Extracts, processes, and merges GeoLite2 data from the zip file in memory.
    """
    print("Processing zip file in memory...")
    country_map = {}
    ip_ranges = []

    with zipfile.ZipFile(io.BytesIO(zip_content)) as zf:
        try:
            locations_path = next(
                p for p in zf.namelist() if p.endswith(LOCATIONS_FILENAME)
            )
        except StopIteration:
            raise RuntimeError(f"Could not find '{LOCATIONS_FILENAME}' in the zip archive.")
        
        dir_name = Path(locations_path).parent.as_posix()
        print(f"  -> Found data directory inside zip: '{dir_name}'")

        print("  -> Reading country locations...")
        with zf.open(f"{dir_name}/{LOCATIONS_FILENAME}") as f:
            reader = csv.DictReader(io.TextIOWrapper(f, "utf-8"))
            for row in reader:
                if row.get("country_iso_code"):
                    country_map[row["geoname_id"]] = row["country_iso_code"]
        print(f"  -> Mapped {len(country_map)} geoname_ids to country codes.")

        print("  -> Reading IPv4 blocks...")
        ipv4_count = 0
        with zf.open(f"{dir_name}/{IPV4_BLOCKS_FILENAME}") as f:
            reader = csv.DictReader(io.TextIOWrapper(f, "utf-8"))
            for row in reader:
                geoname_id = row.get("geoname_id") or row.get("registered_country_geoname_id")
                if geoname_id and geoname_id in country_map:
                    ip_ranges.append((row["network"], country_map[geoname_id]))
                    ipv4_count += 1
        print(f"  -> Processed {ipv4_count} IPv4 ranges.")

        print("  -> Reading IPv6 blocks...")
        ipv6_count = 0
        with zf.open(f"{dir_name}/{IPV6_BLOCKS_FILENAME}") as f:
            reader = csv.DictReader(io.TextIOWrapper(f, "utf-8"))
            for row in reader:
                geoname_id = row.get("geoname_id") or row.get("registered_country_geoname_id")
                if geoname_id and geoname_id in country_map:
                    ip_ranges.append((row["network"], country_map[geoname_id]))
                    ipv6_count += 1
        print(f"  -> Processed {ipv6_count} IPv6 ranges.")

    print(f"\nProcessing complete. Found a total of {len(ip_ranges)} IP ranges.")
    return ip_ranges


def write_output_file(ip_ranges: list[tuple[str, str]]):
    """Writes the processed data to the library's internal CSV file."""
    print(f"Writing {len(ip_ranges)} records to {OUTPUT_CSV_PATH}...")
    OUTPUT_CSV_PATH.parent.mkdir(exist_ok=True)    
    update_date_str = date.today().isoformat()

    with open(OUTPUT_CSV_PATH, "w", newline="", encoding="utf-8") as f:
        f.write("# Geofence Validator - IP Range Data\n")
        f.write("# Automatically generated by scripts/update_geolite_data.py\n")
        f.write(f"# Last updated on: {update_date_str}\n")
        f.write("# Data sourced from the GeoLite2 database created by MaxMind, available from https://www.maxmind.com\n")
        f.write("# Format: CIDR,ISO_COUNTRY_CODE\n")
        writer = csv.writer(f)
        writer.writerows(ip_ranges)
    print("Output file written successfully.")


if __name__ == "__main__":
    try:
        zip_bytes = fetch_data()
        final_ranges = process_zip_data(zip_bytes)
        write_output_file(final_ranges)
        print("\n✅ Successfully updated the geofence data file!")
    except Exception as e:
        print("\n--- ERROR ---")
        print(f"An error occurred: {e}")
        print("Please check your environment variables and internet connection.")