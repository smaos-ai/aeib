#!/usr/bin/env python3
"""
Zenodo REST API Deposit Script for AEIB v0.4.1
Per strict zero-egress boundaries, this script is provided for the user to execute.
It requires ZENODO_ACCESS_TOKEN to be set in the environment.
"""

import os
import sys
import json
import urllib.request
import urllib.parse
from pathlib import Path

# Zenodo Sandbox API for testing (change to zenodo.org for production)
ZENODO_URL = "https://sandbox.zenodo.org/api/deposit/depositions"
ACCESS_TOKEN = os.environ.get("ZENODO_ACCESS_TOKEN")
DIST_DIR = Path("dist")

def main():
    if not ACCESS_TOKEN:
        print("ERROR: ZENODO_ACCESS_TOKEN environment variable is not set.", file=sys.stderr)
        sys.exit(1)

    print(f"Initiating Zenodo deposit for AEIB v0.4.1...")
    
    # 1. Create empty deposit
    req = urllib.request.Request(
        f"{ZENODO_URL}?access_token={ACCESS_TOKEN}",
        method="POST",
        data=b"{}",
        headers={"Content-Type": "application/json"}
    )
    
    try:
        with urllib.request.urlopen(req) as response:
            deposit_data = json.loads(response.read())
            deposit_id = deposit_data["id"]
            bucket_url = deposit_data["links"]["bucket"]
            print(f"Created new deposition ID: {deposit_id}")
    except Exception as e:
        print(f"Failed to create deposition: {e}")
        sys.exit(1)

    # 2. Upload files
    files_to_upload = [
        "aeib-enterprise-v0.4.1.tar.gz",
        ".zenodo.json",
        "CITATION.cff"
    ]
    
    for filename in files_to_upload:
        filepath = DIST_DIR / filename
        if not filepath.exists():
            print(f"WARNING: File {filename} not found in {DIST_DIR}/. Skipping.")
            continue
            
        print(f"Uploading {filename}...")
        with open(filepath, "rb") as f:
            file_data = f.read()
            req = urllib.request.Request(
                f"{bucket_url}/{filename}?access_token={ACCESS_TOKEN}",
                method="PUT",
                data=file_data
            )
            try:
                urllib.request.urlopen(req)
                print(f" - Uploaded {filename} successfully.")
            except Exception as e:
                print(f" - Failed to upload {filename}: {e}")

    # 3. Apply Metadata (using .zenodo.json)
    metadata_path = DIST_DIR / ".zenodo.json"
    if metadata_path.exists():
        with open(metadata_path, "r") as f:
            metadata = json.load(f)
            
        print(f"Applying metadata to deposition {deposit_id}...")
        payload = json.dumps({"metadata": metadata}).encode('utf-8')
        
        req = urllib.request.Request(
            f"{ZENODO_URL}/{deposit_id}?access_token={ACCESS_TOKEN}",
            method="PUT",
            data=payload,
            headers={"Content-Type": "application/json"}
        )
        try:
            urllib.request.urlopen(req)
            print("Metadata applied successfully.")
        except Exception as e:
            print(f"Failed to apply metadata: {e}")
            
    print(f"\nDeposit completed successfully. Review and publish at: https://sandbox.zenodo.org/deposit/{deposit_id}")

if __name__ == "__main__":
    main()
