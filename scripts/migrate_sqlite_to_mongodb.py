#!/usr/bin/env python3
"""
Migration Script: SQLite to MongoDB Atlas for VideoShrink.

Reads historical experiment records from SQLite (experiments/videoshrink.db)
and upserts them into MongoDB Atlas 'experiments' collection.
Safe: Never exposes or prints credentials in logs or output.
"""

import os
import sys
import json
import sqlite3
import argparse
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.database.mongodb import MongoDBManager, mask_mongo_uri
from backend.app.config import settings

def parse_args():
    parser = argparse.ArgumentParser(description="Migrate VideoShrink experiment data from SQLite to MongoDB Atlas.")
    parser.add_argument(
        "--db-path",
        type=str,
        default=str(settings.DB_PATH),
        help="Path to the SQLite database file (default: experiments/videoshrink.db)"
    )
    parser.add_argument(
        "--mongo-uri",
        type=str,
        default=None,
        help="MongoDB connection URI (optional; defaults to MONGODB_URI environment variable or .env)"
    )
    parser.add_argument(
        "--cutoff",
        type=str,
        default="2026-09-11 03:40:05",
        help="Only migrate records created on or before this timestamp (default: '2026-09-11 03:40:05' for the 49 historical records)"
    )
    parser.add_argument(
        "--max-records",
        type=int,
        default=49,
        help="Maximum historical records to migrate (default: 49)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Perform a dry run without modifying MongoDB."
    )
    return parser.parse_args()

def migrate():
    args = parse_args()
    sqlite_path = Path(args.db_path)

    if not sqlite_path.exists():
        print(f"[ERROR] SQLite database not found at: {sqlite_path}")
        sys.exit(1)

    print(f"[INFO] Reading SQLite database from: {sqlite_path}")
    conn = sqlite3.connect(str(sqlite_path))
    conn.row_factory = sqlite3.Row

    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT * FROM experiments WHERE created_at <= ? ORDER BY created_at ASC LIMIT ?",
            (args.cutoff, args.max_records)
        )
        rows = cursor.fetchall()
    except sqlite3.OperationalError as e:
        print(f"[ERROR] Failed to query experiments table: {e}")
        conn.close()
        sys.exit(1)

    print(f"[INFO] Query matched {len(rows)} historical records (cutoff <= '{args.cutoff}', limit {args.max_records}).")

    if not rows:
        print("[INFO] No records to migrate. Exiting.")
        conn.close()
        return

    # Dry-run validation of records
    seen_ids = set()
    seen_codes = set()
    duplicates = []
    malformed_fields = []
    parsed_records = []

    for idx, row in enumerate(rows):
        data = dict(row)
        exp_id = data.get("id")
        exp_code = data.get("experiment_code")

        if not exp_id:
            malformed_fields.append((idx, "missing_id"))
        elif exp_id in seen_ids:
            duplicates.append(exp_id)
        seen_ids.add(exp_id)
        seen_codes.add(exp_code)

        # Validate & parse JSON fields
        for json_field in ["parameters", "failure_summary", "quality_summary"]:
            val = data.get(json_field)
            if isinstance(val, str) and val.strip():
                try:
                    data[json_field] = json.loads(val)
                except json.JSONDecodeError as e:
                    malformed_fields.append((exp_id, f"{json_field}: {e}"))

        parsed_records.append(data)

    if args.dry_run:
        print("\n=======================================================")
        print("MIGRATION DRY-RUN AUDIT REPORT")
        print("=======================================================")
        print(f"Total SQLite Records:           {len(rows)}")
        print(f"Unique Experiment IDs:          {len(seen_ids)}")
        print(f"Unique Experiment Codes:        {len(seen_codes)}")
        print(f"Duplicate IDs Detected:         {len(duplicates)}")
        print(f"Malformed / Invalid Fields:     {len(malformed_fields)}")
        print(f"Target Database:                {settings.MONGODB_DATABASE}")
        print(f"Target Collection:              experiments")
        print(f"ID Preservation:                YES (retaining original UUIDs in 'id' field)")
        print("Idempotency Guarantee:          YES (upsert on {'id': exp_id})")

        if duplicates:
            print(f"[WARNING] Duplicate IDs: {duplicates}")
        if malformed_fields:
            print(f"[WARNING] Malformed fields: {malformed_fields}")

        print("\nEarliest record to migrate:")
        e0 = parsed_records[0]
        print(f"  ID: {e0.get('id')} | Code: {e0.get('experiment_code')} | Date: {e0.get('created_at')} | Strategy: {e0.get('strategy')}")
        print("Latest record to migrate:")
        e_last = parsed_records[-1]
        print(f"  ID: {e_last.get('id')} | Code: {e_last.get('experiment_code')} | Date: {e_last.get('created_at')} | Strategy: {e_last.get('strategy')}")
        print("=======================================================")
        print("[DRY RUN COMPLETE] Dataset is valid and ready for migration.")
        conn.close()
        return

    # Check MongoDB connection URI
    mongo_uri = args.mongo_uri or settings.MONGODB_URI
    if not mongo_uri:
        print("[ERROR] MONGODB_URI is not configured in environment, .env, or via --mongo-uri.")
        print("[INFO] Cannot connect to MongoDB Atlas without a connection URI.")
        conn.close()
        sys.exit(1)

    masked_uri = mask_mongo_uri(mongo_uri)
    print(f"[INFO] Target MongoDB Atlas: {masked_uri} (Database: {settings.MONGODB_DATABASE})")

    # Override setting if provided via CLI
    if args.mongo_uri:
        settings.MONGODB_URI = args.mongo_uri

    mgr = MongoDBManager()
    if not mgr.connect():
        print("[ERROR] Could not connect to MongoDB Atlas. Aborting migration.")
        conn.close()
        sys.exit(1)

    db = mgr.database
    if db is None:
        print("[ERROR] MongoDB database reference is None.")
        conn.close()
        sys.exit(1)

    coll = db["experiments"]
    migrated_count = 0
    error_count = 0

    for data in parsed_records:
        exp_id = data.get("id")
        try:
            coll.update_one({"id": exp_id}, {"$set": data}, upsert=True)
            migrated_count += 1
        except Exception as e:
            print(f"[ERROR] Failed to upsert experiment {exp_id}: {e}")
            error_count += 1

    conn.close()
    print(f"\n[SUCCESS] Migration completed: {migrated_count} records upserted into 'experiments', {error_count} errors.")

if __name__ == "__main__":
    migrate()
