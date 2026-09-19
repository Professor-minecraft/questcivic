"""
Account migration script:
- Backs up app.db to backend/backups/app-<timestamp>.db
- Safely alters users, submissions, and complaints tables using PRAGMA table_info
- Backfills state_norm and constituency_norm
- Ensures pending_signups and otp_requests tables are created
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

from app.database import engine, Base
from app.models import User, Submission, Complaint, PendingSignup, OTPRequest  # noqa: F401
from app.services.normalize import normalize_place


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

    conn = sqlite3.connect(app_db)
    cursor = conn.cursor()

    columns_added = []
    rows_backfilled = {}

    def get_columns(table: str):
        cursor.execute(f"PRAGMA table_info({table})")
        return {row[1] for row in cursor.fetchall()}

    # --- USERS ---
    user_cols = get_columns("users")
    user_target_cols = [
        ("name", "TEXT"),
        ("password_hash", "TEXT"),
        ("email_verified", "INTEGER DEFAULT 0"),
        ("password_changed_at", "DATETIME"),
        ("location_changed_at", "DATETIME"),
    ]
    for col_name, col_type in user_target_cols:
        if col_name not in user_cols:
            cursor.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")
            columns_added.append(f"users.{col_name}")

    # Set email_verified = 1 for existing users who are not yet verified
    cursor.execute("UPDATE users SET email_verified = 1 WHERE email_verified = 0 OR email_verified IS NULL")
    users_verified = cursor.rowcount
    if users_verified > 0:
        rows_backfilled["users.email_verified"] = users_verified

    # --- SUBMISSIONS ---
    subm_cols = get_columns("submissions")
    subm_target_cols = [
        ("state_norm", "TEXT"),
        ("constituency_norm", "TEXT"),
    ]
    for col_name, col_type in subm_target_cols:
        if col_name not in subm_cols:
            cursor.execute(f"ALTER TABLE submissions ADD COLUMN {col_name} {col_type}")
            columns_added.append(f"submissions.{col_name}")

    cursor.execute("CREATE INDEX IF NOT EXISTS ix_submissions_state_norm ON submissions (state_norm)")
    cursor.execute("CREATE INDEX IF NOT EXISTS ix_submissions_constituency_norm ON submissions (constituency_norm)")

    # Backfill submissions from submitting user's state and constituency
    cursor.execute("""
        SELECT s.id, u.state, u.constituency
        FROM submissions s
        JOIN users u ON s.user_id = u.id
        WHERE s.state_norm IS NULL OR s.constituency_norm IS NULL
    """)
    unfilled_subs = cursor.fetchall()
    subs_updated = 0
    for sub_id, u_state, u_const in unfilled_subs:
        s_norm = normalize_place(u_state)
        c_norm = normalize_place(u_const)
        cursor.execute(
            "UPDATE submissions SET state_norm = ?, constituency_norm = ? WHERE id = ?",
            (s_norm, c_norm, sub_id)
        )
        subs_updated += 1
    if subs_updated > 0:
        rows_backfilled["submissions_norm"] = subs_updated

    # --- COMPLAINTS ---
    compl_cols = get_columns("complaints")
    compl_target_cols = [
        ("state_norm", "TEXT"),
        ("constituency_norm", "TEXT"),
    ]
    for col_name, col_type in compl_target_cols:
        if col_name not in compl_cols:
            cursor.execute(f"ALTER TABLE complaints ADD COLUMN {col_name} {col_type}")
            columns_added.append(f"complaints.{col_name}")

    cursor.execute("CREATE INDEX IF NOT EXISTS ix_complaints_state_norm ON complaints (state_norm)")
    cursor.execute("CREATE INDEX IF NOT EXISTS ix_complaints_constituency_norm ON complaints (constituency_norm)")

    # Backfill complaints from complaint's own state and constituency
    cursor.execute("""
        SELECT id, state, constituency
        FROM complaints
        WHERE state_norm IS NULL OR constituency_norm IS NULL
    """)
    unfilled_compls = cursor.fetchall()
    compls_updated = 0
    for compl_id, c_state, c_const in unfilled_compls:
        s_norm = normalize_place(c_state)
        c_norm = normalize_place(c_const)
        cursor.execute(
            "UPDATE complaints SET state_norm = ?, constituency_norm = ? WHERE id = ?",
            (s_norm, c_norm, compl_id)
        )
        compls_updated += 1
    if compls_updated > 0:
        rows_backfilled["complaints_norm"] = compls_updated

    conn.commit()
    conn.close()

    # Ensure all tables defined in models.py exist (pending_signups, otp_requests)
    Base.metadata.create_all(bind=engine)

    # Print summary
    print("\n--- Migration Summary ---")
    if columns_added:
        print(f"Columns added ({len(columns_added)}): {', '.join(columns_added)}")
    else:
        print("Columns added: None (all columns already exist)")

    if rows_backfilled:
        for k, v in rows_backfilled.items():
            print(f"Rows updated/backfilled [{k}]: {v}")
    else:
        print("Rows updated/backfilled: None (all rows already up-to-date)")

    if not columns_added and not rows_backfilled:
        print("Result: No changes needed (database is already fully migrated).")
    else:
        print("Result: Migration completed successfully.")


if __name__ == "__main__":
    run_migration()
