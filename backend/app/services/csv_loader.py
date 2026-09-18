import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import pandas as pd
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models import Work

WORK_REGEX = re.compile(r"^(WS/[^/]+/\d{4}-\d{4}/\d+)-(.*)$")
CONSTITUENCY_CLEAN_REGEX = re.compile(r"\s*\((?:SC|ST)\)\s*$", flags=re.IGNORECASE)


def normalize_text(text: Optional[str]) -> Optional[str]:
    if text is None:
        return None
    cleaned = re.sub(r"\s+", " ", str(text)).strip().upper()
    return cleaned if cleaned else None


def clean_district(ida_val: Any) -> str:
    if pd.isna(ida_val) or ida_val is None:
        return ""
    text = str(ida_val)
    if "(" in text:
        return text.split("(")[0].strip()
    return text.strip()


def clean_constituency(const_val: Any) -> Optional[str]:
    if pd.isna(const_val) or const_val is None:
        return None
    text = str(const_val).strip()
    cleaned = CONSTITUENCY_CLEAN_REGEX.sub("", text).strip()
    return cleaned if cleaned else None


def parse_amount(val: Any) -> Optional[float]:
    if pd.isna(val) or val is None:
        return None
    text = str(val).strip()
    if not text:
        return None
    # Remove currency symbol, commas, and other non-numeric chars except dot
    num_str = re.sub(r"[^\d.]", "", text)
    if not num_str:
        return None
    try:
        return float(num_str)
    except ValueError:
        return None


def parse_completion_date(val: Any):
    if pd.isna(val) or val is None:
        return None
    text = str(val).strip()
    if not text:
        return None
    try:
        return datetime.strptime(text, "%d-%b-%Y").date()
    except (ValueError, TypeError):
        return None


def parse_work_field(work_val: Any):
    work_str = str(work_val).strip() if pd.notna(work_val) else ""
    match = WORK_REGEX.match(work_str)
    if match:
        work_code = match.group(1).strip()
        work_type = match.group(2).strip()
    else:
        work_code = None
        work_type = work_str
    return work_code, work_type


def process_lok_sabha_df(df: pd.DataFrame) -> List[Dict[str, Any]]:
    # Drop any row where Sr. No. is not a number
    df = df[df["Sr. No."].astype(str).str.strip().str.isnumeric() == True].copy()

    records: List[Dict[str, Any]] = []
    for _, row in df.iterrows():
        sr_no = int(str(row["Sr. No."]).strip())
        state = str(row["State"]).strip() if pd.notna(row["State"]) else ""
        district = clean_district(row["IDA"])
        constituency = clean_constituency(row["Constituency"])
        category = str(row["Work Category"]).strip() if pd.notna(row["Work Category"]) else None
        mp_name = str(row["Hon'ble Members of Parliament"]).strip() if pd.notna(row["Hon'ble Members of Parliament"]) else None

        work_code, work_type = parse_work_field(row["Work"])

        desc_raw = str(row["Work Description"]).strip() if pd.notna(row["Work Description"]) else ""
        description = desc_raw if desc_raw else work_type

        amount = parse_amount(row.get("Amount Disbursed ( ₹ )"))
        completion_date = parse_completion_date(row.get("Completion Date"))

        records.append({
            "source": "LS",
            "sr_no": sr_no,
            "work_code": work_code,
            "work_type": work_type,
            "category": category,
            "state": state,
            "district": district,
            "constituency": constituency,
            "state_norm": normalize_text(state) or "",
            "district_norm": normalize_text(district) or "",
            "constituency_norm": normalize_text(constituency),
            "mp_name": mp_name,
            "description": description,
            "amount": amount,
            "completion_date": completion_date,
        })
    return records


def process_rajya_sabha_df(df: pd.DataFrame) -> List[Dict[str, Any]]:
    # Drop any row where Sr. No. is not a number
    df = df[df["Sr. No."].astype(str).str.strip().str.isnumeric() == True].copy()

    records: List[Dict[str, Any]] = []
    for _, row in df.iterrows():
        sr_no = int(str(row["Sr. No."]).strip())
        state = str(row["State"]).strip() if pd.notna(row["State"]) else ""
        district = clean_district(row["IDA"])
        # Rajya Sabha rows have NO constituency
        constituency = None
        category = str(row["Work Category"]).strip() if pd.notna(row["Work Category"]) else None
        mp_name = str(row["Hon'ble Members of Parliament"]).strip() if pd.notna(row["Hon'ble Members of Parliament"]) else None

        work_code, work_type = parse_work_field(row["Work"])

        desc_raw = str(row["Work Description"]).strip() if pd.notna(row["Work Description"]) else ""
        description = desc_raw if desc_raw else work_type

        amount = parse_amount(row.get("Amount Disbursed ( ₹ )"))
        completion_date = parse_completion_date(row.get("Completion Date"))

        records.append({
            "source": "RS",
            "sr_no": sr_no,
            "work_code": work_code,
            "work_type": work_type,
            "category": category,
            "state": state,
            "district": district,
            "constituency": constituency,
            "state_norm": normalize_text(state) or "",
            "district_norm": normalize_text(district) or "",
            "constituency_norm": None,
            "mp_name": mp_name,
            "description": description,
            "amount": amount,
            "completion_date": completion_date,
        })
    return records


def import_csv_data(
    db: Session,
    ls_path: str = "data/Loksova.csv",
    rs_path: str = "data/RajyaSabha.csv",
    batch_size: int = 5000,
) -> Dict[str, int]:
    # Clear existing works table
    db.execute(delete(Work))
    db.commit()

    # Process Lok Sabha
    ls_df = pd.read_csv(ls_path, encoding="utf-8-sig", dtype=str)
    ls_records = process_lok_sabha_df(ls_df)
    for i in range(0, len(ls_records), batch_size):
        db.bulk_insert_mappings(Work, ls_records[i : i + batch_size])
    db.commit()

    # Process Rajya Sabha
    rs_df = pd.read_csv(rs_path, encoding="utf-8-sig", dtype=str)
    rs_records = process_rajya_sabha_df(rs_df)
    for i in range(0, len(rs_records), batch_size):
        db.bulk_insert_mappings(Work, rs_records[i : i + batch_size])
    db.commit()

    return {
        "ls_count": len(ls_records),
        "rs_count": len(rs_records),
    }
