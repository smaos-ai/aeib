import json
import sys

with open("provenance/receipts/receipt_rs_20260928_1790639864_1790639864.json", "r") as f:
    data = json.load(f)

cose_hex = data.get("cose_envelope_hex")
if cose_hex:
    with open("test_receipt.cose", "wb") as f:
        f.write(bytes.fromhex(cose_hex))
    print("test_receipt.cose created.")
else:
    print("No cose_envelope_hex found")
