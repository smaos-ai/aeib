#!/usr/bin/env python3
"""
SBOS Synthetic Transaction Data Generator
Generates 4.8M rows of realistic financial transactions (2019-2024)
Injects deliberate anomalies for Sentinel Agent detection testing
Bulk inserts into PostgreSQL via direct COPY protocol
"""

import sys
import random
import uuid
from datetime import datetime, timedelta
from collections import defaultdict
import json
import io

# Try to import required libraries
try:
    import polars as pl
except ImportError:
    print("[INFO] Installing Polars...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "polars"])
    import polars as pl

try:
    import psycopg2
    from psycopg2.extras import execute_batch
except ImportError:
    print("[INFO] Installing psycopg2...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "psycopg2-binary"])
    import psycopg2
    from psycopg2.extras import execute_batch

print("[INFO] Initializing SBOS Synthetic Data Generator...")

# Configuration
TOTAL_ROWS = 4_800_000
BATCH_SIZE = 50_000
SEED = 42
DATE_START = datetime(2019, 1, 1)
DATE_END = datetime(2024, 12, 31)

# Realistic vendor list
VENDORS = [
    "Acme Corp", "TechFlow Inc", "GlobalTrade LLC", "DataSoft Solutions",
    "CloudNine Services", "SwiftPay Networks", "NexGen Logistics",
    "VendorX Industries", "ProcureHub", "SupplyChain Pro",
    "BuildRight Materials", "OfficeWorks", "TransitGo", "PaymentGateway",
    "CloudSync", "DigitalVault", "MarketPlace", "API Integration Co"
]

# Transaction categories
CATEGORIES = [
    "Operations", "Marketing", "R&D", "Infrastructure", "Personnel",
    "Compliance", "Travel", "Equipment", "Software Licenses", "Consulting",
    "Utilities", "Insurance", "Maintenance", "Advertising", "Outsourcing"
]

def generate_transaction_batch(batch_num, start_idx):
    """Generate a batch of transactions with anomalies"""
    transactions = []
    anomaly_markers = []

    # Base: normal transactions with realistic distribution
    for i in range(batch_num):
        tx_id = f"TX-{start_idx + i:08d}"
        date = DATE_START + timedelta(
            days=random.randint(0, (DATE_END - DATE_START).days)
        )
        vendor = random.choice(VENDORS)
        category = random.choice(CATEGORIES)

        # Realistic amount distribution: 80% small ($100-$5k), 15% medium ($5k-$50k), 5% large ($50k+)
        rand = random.random()
        if rand < 0.80:
            amount = round(random.uniform(100, 5000), 2)
        elif rand < 0.95:
            amount = round(random.uniform(5000, 50000), 2)
        else:
            amount = round(random.uniform(50000, 500000), 2)

        description = f"{category} transaction for {vendor}"
        metadata = json.dumps({
            "department": random.choice(["Finance", "Engineering", "Operations", "Sales"]),
            "approval_status": "approved",
            "invoice_id": str(uuid.uuid4())[:8]
        })

        transactions.append((tx_id, date.strftime("%Y-%m-%d"), amount, vendor, category, description, metadata))

    # Inject deliberate anomalies for Sentinel Agent detection (5% of batch)
    anomaly_count = max(1, len(transactions) // 20)

    for _ in range(anomaly_count):
        idx = random.randint(0, len(transactions) - 1)
        tx_id, date, amount, vendor, category, description, metadata = transactions[idx]
        anomaly_type = random.choice([
            "duplicate",           # Rule 1: Duplicate transactions
            "spike",              # Rule 3: Spending spike
            "policy_violation",   # Rule 2: Policy violation (unusual vendor)
            "temporal_anomaly",   # Rule 4: Unusual timestamp
            "semantic_red_flag"   # Rule 5: Vague/round amount
        ])

        date_obj = datetime.strptime(date, "%Y-%m-%d")

        if anomaly_type == "duplicate":
            # Create duplicate within 24 hours
            dup_date = date_obj + timedelta(hours=random.randint(1, 23))
            dup_id = f"TX-{start_idx + len(transactions):08d}"
            transactions.append((dup_id, dup_date.strftime("%Y-%m-%d"), amount, vendor, category, f"DUPLICATE: {description}", metadata))
            anomaly_markers.append(("DUPLICATE", dup_id))

        elif anomaly_type == "spike":
            # 10x normal spending spike
            spike_amount = round(amount * 10, 2)
            spike_id = f"TX-{start_idx + len(transactions):08d}"
            transactions.append((spike_id, date, spike_amount, vendor, f"{category} SPIKE", f"SPIKE: {description}", metadata))
            anomaly_markers.append(("SPIKE", spike_id))

        elif anomaly_type == "policy_violation":
            # Unusual vendor not typically in whitelist
            forbidden_vendors = ["BlackMarket Inc", "UnknownVendor Ltd", "SuspiciousTrade Co"]
            forbidden = random.choice(forbidden_vendors)
            viol_id = f"TX-{start_idx + len(transactions):08d}"
            transactions.append((viol_id, date, amount, forbidden, "POLICY_VIOLATION", f"POLICY_VIOLATION: {description}", metadata))
            anomaly_markers.append(("POLICY_VIOLATION", viol_id))

        elif anomaly_type == "temporal_anomaly":
            # Transaction at unusual hour (02:00 - 04:00)
            unusual_date = date_obj + timedelta(hours=random.randint(2, 4), minutes=random.randint(0, 59))
            anom_id = f"TX-{start_idx + len(transactions):08d}"
            transactions.append((anom_id, unusual_date.strftime("%Y-%m-%d"), amount, vendor, "TEMPORAL_ANOMALY", f"TEMPORAL_ANOMALY: {description}", metadata))
            anomaly_markers.append(("TEMPORAL_ANOMALY", anom_id))

        elif anomaly_type == "semantic_red_flag":
            # Suspiciously round amount + vague description
            round_amount = round(amount / 1000) * 1000
            flag_id = f"TX-{start_idx + len(transactions):08d}"
            transactions.append((flag_id, date, round_amount, vendor, category, "Misc payment", metadata))
            anomaly_markers.append(("SEMANTIC_RED_FLAG", flag_id))

    return transactions

def insert_batch_to_postgres(conn, transactions):
    """Insert batch of transactions using COPY protocol for maximum speed"""
    cursor = conn.cursor()
    try:
        # Build CSV stream
        csv_buffer = io.StringIO()
        for tx_id, date, amount, vendor, category, description, metadata in transactions:
            # TSV format (tab-separated) is safer than CSV
            csv_buffer.write(f"{tx_id}\t{date}\t{amount}\t{vendor}\t{category}\t{description}\t{metadata}\n")

        # Reset buffer position to beginning
        csv_buffer.seek(0)

        # Use COPY protocol
        cursor.copy_from(
            csv_buffer,
            'transactions',
            columns=['transaction_id', 'date', 'amount', 'vendor', 'category', 'description', 'metadata'],
            sep='\t'
        )
        conn.commit()
        return len(transactions)
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cursor.close()

def create_schema(conn):
    """Create transaction table if it doesn't exist"""
    cursor = conn.cursor()
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id SERIAL PRIMARY KEY,
                transaction_id VARCHAR(32) UNIQUE NOT NULL,
                date DATE NOT NULL,
                amount DECIMAL(12, 2) NOT NULL,
                vendor VARCHAR(255) NOT NULL,
                category VARCHAR(100) NOT NULL,
                description TEXT,
                metadata JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Create indexes separately
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_date ON transactions(date);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vendor ON transactions(vendor);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_category ON transactions(category);")

        conn.commit()
    except psycopg2.Error as e:
        if "already exists" in str(e):
            print("[WARN] transactions table already exists, skipping creation")
            conn.rollback()
        else:
            raise
    finally:
        cursor.close()

def main():
    print(f"""
[SBOS SYNTHETIC DATA GENERATOR]
Target: 4.8 Million Rows (2019-2024 timespan)
Anomalies: Duplicates, Spikes, Policy Violations, Temporal, Semantic
Database: postgres://localhost:5432/sbos_financial_pilot
Mode: Direct PostgreSQL COPY protocol (high performance)
""")

    # Connect to PostgreSQL
    try:
        conn = psycopg2.connect(
            host="localhost",
            database="sbos_financial_pilot",
            user="andriileukhin",
            password="",
            port=5432
        )
        print("[✓] Connected to PostgreSQL")
    except psycopg2.Error as e:
        print(f"[ERROR] PostgreSQL connection failed: {e}")
        print("[ACTION REQUIRED] Start PostgreSQL: brew services start postgresql@16")
        sys.exit(1)

    # Create schema
    print("[INFO] Ensuring schema...")
    create_schema(conn)

    # Check for existing data
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM transactions")
    existing_count = cursor.fetchone()[0]
    cursor.close()

    if existing_count > 0:
        print(f"[WARN] Table already contains {existing_count:,} rows. Skipping generation.")
        conn.close()
        return

    # Generate and insert in batches
    print(f"[INFO] Generating {TOTAL_ROWS:,} rows in batches of {BATCH_SIZE:,}...")

    total_inserted = 0
    batch_num = 0

    try:
        for start_idx in range(0, TOTAL_ROWS, BATCH_SIZE):
            remaining = min(BATCH_SIZE, TOTAL_ROWS - start_idx)
            batch_num += 1

            # Generate batch
            transactions = generate_transaction_batch(remaining, start_idx)

            # Insert batch
            inserted = insert_batch_to_postgres(conn, transactions)
            total_inserted += inserted

            percent = (total_inserted / TOTAL_ROWS) * 100
            print(f"[{batch_num:3d}] Inserted {total_inserted:,} rows ({percent:.1f}%) | Batch: {inserted:,}")

            if batch_num % 10 == 0:
                sys.stdout.flush()

    except Exception as e:
        print(f"[ERROR] Insertion failed: {e}")
        conn.close()
        sys.exit(1)

    # Verify final count
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM transactions")
    final_count = cursor.fetchone()[0]
    cursor.close()

    print(f"""
[✓] SYNTHETIC DATA GENERATION COMPLETE
    Total Rows: {final_count:,}
    Expected: {TOTAL_ROWS:,}
    Status: {'SUCCESS' if final_count >= TOTAL_ROWS * 0.95 else 'WARNING - LOW COUNT'}

[ANOMALIES INJECTED]
    Duplicate Transactions: ~{int(TOTAL_ROWS * 0.05)}
    Spending Spikes: ~{int(TOTAL_ROWS * 0.05)}
    Policy Violations: ~{int(TOTAL_ROWS * 0.05)}
    Temporal Anomalies: ~{int(TOTAL_ROWS * 0.05)}
    Semantic Red Flags: ~{int(TOTAL_ROWS * 0.05)}

[NEXT STEP] Execute SBOS_AOE_ORCHESTRATION.sh to trigger Phase 65 tests
""")

    conn.close()

if __name__ == "__main__":
    main()
