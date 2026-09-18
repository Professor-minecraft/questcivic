import sys
from sqlalchemy import func, select
from app.database import engine, SessionLocal, Base
import app.models  # Ensures all tables are known
from app.models import Work
from app.services.csv_loader import import_csv_data

# Ensure UTF-8 output encoding on Windows consoles
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def main():
    # Ensure tables exist
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        print("Starting CSV import...")
        result = import_csv_data(db)
        print(f"Import finished successfully!")
        print(f"Lok Sabha (LS) rows imported: {result['ls_count']}")
        print(f"Rajya Sabha (RS) rows imported: {result['rs_count']}")
        print(f"Total rows in works table: {result['ls_count'] + result['rs_count']}")

        # Validation checks
        ls_empty_district = db.scalar(
            select(func.count(Work.id)).where(Work.source == "LS", (Work.district == "") | (Work.district.is_(None)))
        )
        ls_empty_constituency = db.scalar(
            select(func.count(Work.id)).where(Work.source == "LS", (Work.constituency == "") | (Work.constituency.is_(None)))
        )
        rs_with_constituency = db.scalar(
            select(func.count(Work.id)).where(Work.source == "RS", Work.constituency.isnot(None))
        )

        print("\n--- Validation Checks ---")
        print(f"LS rows with empty district: {ls_empty_district} (Must be 0)")
        print(f"LS rows with empty constituency: {ls_empty_constituency} (Must be 0)")
        print(f"RS rows with constituency: {rs_with_constituency} (Must be 0)")

        # Print 3 sample rows of each source
        print("\n--- 3 Sample Lok Sabha (LS) Rows ---")
        ls_samples = db.scalars(select(Work).where(Work.source == "LS").limit(3)).all()
        for i, work in enumerate(ls_samples, 1):
            print(
                f"[LS #{i}] ID: {work.id} | Sr: {work.sr_no} | Code: {work.work_code} | "
                f"Type: {work.work_type[:30]}... | State: {work.state} ({work.state_norm}) | "
                f"District: {work.district} ({work.district_norm}) | "
                f"Constituency: {work.constituency} ({work.constituency_norm}) | "
                f"MP: {work.mp_name} | Amount: ₹{work.amount} | Date: {work.completion_date}"
            )

        print("\n--- 3 Sample Rajya Sabha (RS) Rows ---")
        rs_samples = db.scalars(select(Work).where(Work.source == "RS").limit(3)).all()
        for i, work in enumerate(rs_samples, 1):
            print(
                f"[RS #{i}] ID: {work.id} | Sr: {work.sr_no} | Code: {work.work_code} | "
                f"Type: {work.work_type[:30]}... | State: {work.state} ({work.state_norm}) | "
                f"District: {work.district} ({work.district_norm}) | "
                f"Constituency: {work.constituency} | "
                f"MP: {work.mp_name} | Amount: ₹{work.amount} | Date: {work.completion_date}"
            )

    finally:
        db.close()


if __name__ == "__main__":
    main()
