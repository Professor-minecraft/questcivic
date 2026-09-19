"""
Migration script to add show_name column to users table:
- Backs up app.db to backend/backups/app-<timestamp>.db
- Safely checks PRAGMA table_info(users)
- Adds users.show_name (INTEGER DEFAULT 1) if missing
- Backfills existing users with show_name = 1 if NULL
- Safe to run multiple times (idempotent)
"""
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

# Ensure backend root is on sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))


def run_migration():
    app_db = backend_dir / "app.db"

    if not app_db.exists():
        print(f"Database {app_db} does not exist. Nothing to migrate.")
        return

    # Step 1: Backup app.db
    backups_dir = backend_dir / "backups"
    backups_dir.mkdir(parents=True, exist_ok=True)
    gitignore = backups_dir / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text("*\n", encoding="utf-8")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = backups_dir / f"app-{timestamp}.db"
    shutil.copy2(app_db, backup_file)
    print(f"Created backup: {backup_file.name}")

    # Step 2: Check and add column
    conn = sqlite3.connect(app_db)
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(users)")
    cols = {row[1] for row in cursor.fetchall()}

    if "show_name" not in cols:
        cursor.execute("ALTER TABLE users ADD COLUMN show_name INTEGER DEFAULT 1")
        cursor.execute("UPDATE users SET show_name = 1 WHERE show_name IS NULL")
        conn.commit()
        print("Added column users.show_name (INTEGER DEFAULT 1)")
    else:
        cursor.execute("UPDATE users SET show_name = 1 WHERE show_name IS NULL")
        conn.commit()
        print("Column users.show_name already exists. Migration safe and idempotent.")

    conn.close()


if __name__ == "__main__":
    run_migration()
