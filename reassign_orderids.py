import os
import json
import sqlite3
from datetime import datetime
from fuzzywuzzy import fuzz

REVIEW_FOLDER = r"C:\Users\ChristopherCato\OneDrive - clarity-dx.com\Documents\Bill_Review_INTERNAL\scripts\VAILIDATION\data\extracts\valid\mapped\staging" # Update this
DB_PATH = r"C:\Users\ChristopherCato\OneDrive - clarity-dx.com\Documents\Bill_Review_INTERNAL\reference_tables\orders2.db"  # Same DB as before

def normalize_text(text):
    return ''.join(sorted(char for char in text.strip().upper() if char.isalnum()))

def parse_date(date_str):
    for fmt in ["%Y-%m-%d", "%m/%d/%Y", "%Y%m%d"]:
        try:
            return datetime.strptime(date_str, fmt)
        except:
            continue
    return None

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def load_orders():
    conn = get_db_connection()
    orders = conn.execute("""
        SELECT o.Order_ID, o.FileMaker_Record_Number, o.PatientName,
               GROUP_CONCAT(DISTINCT li.DOS) AS DOS_List,
               GROUP_CONCAT(DISTINCT li.CPT) AS CPT_List
        FROM orders o
        LEFT JOIN line_items li ON o.Order_ID = li.Order_ID
        GROUP BY o.Order_ID
    """).fetchall()
    conn.close()
    return orders

def reassess_json_file(filepath, orders):
    with open(filepath, 'r') as f:
        data = json.load(f)

    json_name = normalize_text(data.get("patient_info", {}).get("patient_name", ""))
    json_dos_list = [
        parse_date(sl.get("date_of_service", ""))
        for sl in data.get("service_lines", []) if sl.get("date_of_service")
    ]
    json_cpts = {sl.get("cpt_code", "").strip() for sl in data.get("service_lines", []) if sl.get("cpt_code")}

    candidates = []
    for row in orders:
        db_name = normalize_text(row["PatientName"] or "")
        name_score = (fuzz.token_sort_ratio(json_name, db_name) + fuzz.token_set_ratio(json_name, db_name)) / 2
        if name_score < 90:
            continue

        db_dos = [parse_date(x.strip()) for x in (row["DOS_List"] or "").split(",") if x.strip()]
        db_cpts = {x.strip() for x in (row["CPT_List"] or "").split(",") if x.strip()}

        for jd in json_dos_list:
            if any(abs((jd - dd).days) <= 14 for dd in db_dos if dd):
                cpt_match_score = len(json_cpts & db_cpts)
                candidates.append((cpt_match_score, name_score, row))
                break

    if not candidates:
        return False, None

    # Pick best by CPT match score, then name score
    candidates.sort(reverse=True, key=lambda x: (x[0], x[1]))
    best = candidates[0][2]

    if data.get("Order_ID") != best["Order_ID"]:
        data["Order_ID"] = best["Order_ID"]
        data["filemaker_number"] = best["FileMaker_Record_Number"]
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=4)
        return True, best["Order_ID"]

    return False, None

def reassign_all():
    orders = load_orders()
    updated = []
    for file in os.listdir(REVIEW_FOLDER):
        if file.endswith(".json"):
            filepath = os.path.join(REVIEW_FOLDER, file)
            changed, new_order = reassess_json_file(filepath, orders)
            if changed:
                updated.append((file, new_order))
                print(f"✅ Reassigned {file} to {new_order}")
            else:
                print(f"— No better match found for {file}")
    print(f"\nDone. {len(updated)} files reassigned.")

if __name__ == "__main__":
    reassign_all()
