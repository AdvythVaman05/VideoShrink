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
        cursor.execute("SELECT * FROM experiments ORDER BY created_at ASC")
        rows = cursor.fetchall()
    except sqlite3.OperationalError as e:
        print(f"[ERROR] Failed to query experiments table: {e}")
        conn.close()
        sys.exit(1)

    print(f"[INFO] Found {len(rows)} experiment records in SQLite.")

    if not rows:
        print("[INFO] No records to migrate. Exiting.")
        conn.close()
        return

    # Check MongoDB connection
    mongo_uri = settings.MONGODB_URI
    if not mongo_uri:
        print("[WARNING] MONGODB_URI is not configured in environment.")
        print("[INFO] Records verified in SQLite, but MongoDB write was skipped because MONGODB_URI is unset.")
        conn.close()
        return

    masked_uri = mask_mongo_uri(mongo_uri)
    print(f"[INFO] Target MongoDB Atlas: {masked_uri} (Database: {settings.MONGODB_DATABASE})")

    if args.dry_run:
        print(f"[DRY RUN] Would upsert {len(rows)} records into MongoDB Atlas.")
        conn.close()
        return

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

    for row in rows:
        data = dict(row)
        exp_id = data.get("id")

        # Parse JSON fields safely
        for json_field in ["parameters", "failure_summary", "quality_summary"]:
            val = data.get(json_field)
            if isinstance(val, str) and val.strip():
                try:
                    data[json_field] = json.loads(val)
                except json.JSONDecodeError:
                    pass

        try:
            coll.update_one({"id": exp_id}, {"$set": data}, upsert=True)
            migrated_count += 1
        except Exception as e:
            print(f"[ERROR] Failed to upsert experiment {exp_id}: {e}")
            error_count += 1

    conn.close()
    print(f"[SUCCESS] Migration completed: {migrated_count} records upserted, {error_count} errors.")

if __name__ == "__main__":
    migrate()
