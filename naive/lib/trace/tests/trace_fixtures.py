"""Small trace-back worlds for the trace tool tests, built by hand (no generator, no hidden data).

Base world: romaine from Green Acres Farm (F-01, lots RL-0412 and RL-0413, packed by P-01, shipped by FreshWay D-01)
reaches the stores of six illness cases. Sunny Slope Ranch (F-02, lots RL-0410 and RL-0415 via P-02 and Valley Fresh
D-02) reaches three of those stores too, so it is a decoy that explains some cases equally. IL-007 bought romaine at S-06
weeks later and fits no lot (an unrelated case). Spinach and iceberg rows are filler that keep both distributors
shipping daily. Each test copies the world and changes one thing.
"""
import copy
import csv
import os

ENTITIES = [
    ("F-01", "farm", "Green Acres Farm", "Salinas, CA"),
    ("F-02", "farm", "Sunny Slope Ranch", "Yuma, AZ"),
    ("F-03", "farm", "Blue River Farms", "Gonzales, CA"),
    ("F-04", "farm", "Hilltop Growers", "Soledad, CA"),
    ("P-01", "packer", "Salinas Valley Packing", "Salinas, CA"),
    ("P-02", "packer", "Coastal Pack Co", "Yuma, AZ"),
    ("D-01", "distributor", "FreshWay Distribution", "Fresno, CA"),
    ("D-02", "distributor", "Valley Fresh Distributors", "Bakersfield, CA"),
    ("S-01", "store", "Maple Street Market", "Fresno, CA"),
    ("S-02", "store", "Corner Grocer", "Clovis, CA"),
    ("S-03", "store", "Harbor Foods", "Visalia, CA"),
    ("S-04", "store", "Riverside Grocery", "Hanford, CA"),
    ("S-05", "store", "Oak Lane Market", "Tulare, CA"),
    ("S-06", "store", "Pine Hill Supermarket", "Merced, CA"),
]

LOTS = [  # lot_code, packer_id, pack_date, product, farm_ids
    ("RL-0410", "P-02", "2026-09-28", "romaine", "F-02"),
    ("RL-0411", "P-01", "2026-09-30", "romaine", "F-03"),
    ("RL-0412", "P-01", "2026-10-02", "romaine", "F-01"),
    ("RL-0413", "P-01", "2026-10-04", "romaine", "F-01"),
    ("RL-0415", "P-02", "2026-10-03", "romaine", "F-02"),
    ("RL-0416", "P-02", "2026-10-05", "romaine", "F-04"),
    ("SP-0201", "P-02", "2026-09-30", "spinach", "F-03"),
    ("SP-0202", "P-02", "2026-10-07", "spinach", "F-04"),
    ("IB-0301", "P-01", "2026-09-30", "iceberg", "F-03"),
    ("IB-0302", "P-01", "2026-10-06", "iceberg", "F-04"),
]

SHIPMENTS = [  # ship_date, distributor_id, packer_id, store_id, product, lot_code, qty_cases
    ("2026-10-01", "D-01", "P-01", "S-05", "romaine", "RL-0411", 4),
    ("2026-10-01", "D-01", "P-01", "S-06", "iceberg", "IB-0301", 3),
    ("2026-10-02", "D-01", "P-01", "S-06", "romaine", "RL-0411", 4),
    ("2026-10-02", "D-01", "P-01", "S-01", "iceberg", "IB-0301", 2),
    ("2026-10-03", "D-01", "P-01", "S-01", "romaine", "RL-0412", 6),
    ("2026-10-03", "D-01", "P-01", "S-02", "romaine", "RL-0412", 5),
    ("2026-10-04", "D-01", "P-01", "S-03", "romaine", "RL-0412", 4),
    ("2026-10-04", "D-01", "P-01", "S-02", "iceberg", "IB-0301", 2),
    ("2026-10-05", "D-01", "P-01", "S-04", "romaine", "RL-0413", 5),
    ("2026-10-05", "D-01", "P-01", "S-01", "romaine", "RL-0413", 6),
    ("2026-10-06", "D-01", "P-01", "S-02", "romaine", "RL-0413", 5),
    ("2026-10-06", "D-01", "P-01", "S-03", "iceberg", "IB-0301", 2),
    ("2026-10-07", "D-01", "P-01", "S-04", "iceberg", "IB-0302", 2),
    ("2026-10-08", "D-01", "P-01", "S-05", "iceberg", "IB-0302", 2),
    ("2026-10-09", "D-01", "P-01", "S-06", "iceberg", "IB-0302", 2),
    ("2026-10-10", "D-01", "P-01", "S-01", "iceberg", "IB-0302", 2),
    ("2026-10-01", "D-02", "P-02", "S-01", "spinach", "SP-0201", 3),
    ("2026-10-02", "D-02", "P-02", "S-04", "romaine", "RL-0410", 4),
    ("2026-10-03", "D-02", "P-02", "S-02", "spinach", "SP-0201", 3),
    ("2026-10-04", "D-02", "P-02", "S-02", "romaine", "RL-0415", 4),
    ("2026-10-05", "D-02", "P-02", "S-05", "romaine", "RL-0415", 4),
    ("2026-10-05", "D-02", "P-02", "S-03", "spinach", "SP-0201", 2),
    ("2026-10-06", "D-02", "P-02", "S-05", "romaine", "RL-0416", 3),
    ("2026-10-07", "D-02", "P-02", "S-06", "romaine", "RL-0416", 3),
    ("2026-10-08", "D-02", "P-02", "S-04", "spinach", "SP-0202", 2),
    ("2026-10-09", "D-02", "P-02", "S-05", "spinach", "SP-0202", 2),
    ("2026-10-10", "D-02", "P-02", "S-06", "spinach", "SP-0202", 2),
]

CASES = [  # case_id, onset_date, store_id, purchase_date, product, notes
    ("IL-001", "2026-10-09", "S-01", "2026-10-06", "romaine", "ate a Caesar salad at home"),
    ("IL-002", "2026-10-10", "S-02", "2026-10-07", "romaine", ""),
    ("IL-003", "2026-10-09", "S-03", "2026-10-06", "romaine", ""),
    ("IL-004", "2026-10-10", "S-04", "2026-10-07", "romaine", ""),
    ("IL-005", "2026-10-12", "S-01", "2026-10-09", "romaine", ""),
    ("IL-006", "2026-10-11", "S-02", "2026-10-08", "romaine", ""),
    ("IL-007", "2026-10-30", "S-06", "2026-10-27", "romaine", "shops weekly"),
]


def world():
    """A fresh copy of the base world. Receiving rows mirror the shipments (received the same day)."""
    return {
        "entities": [list(x) for x in ENTITIES],
        "lots": [list(x) for x in LOTS],
        "shipments": [list(x) for x in SHIPMENTS],
        "receiving": [[s[0], s[3], s[1], s[4], s[5], s[6]] for s in SHIPMENTS],
        "cases": [list(x) for x in CASES],
        "emails": {},
        "notes": {},
        "files": {},
    }


def drop(rows, **match):
    """Remove the rows whose columns match, e.g. drop(w["shipments"], date="2026-10-05", d="D-01")."""
    keys = {"date": 0, "d": 1, "p": 2, "s": 3, "lot": 5}
    return [r for r in rows if not all(r[keys[k]] == v for k, v in match.items())]


def drop_receiving(rows, **match):
    keys = {"date": 0, "s": 1, "d": 2, "lot": 4}
    return [r for r in rows if not all(r[keys[k]] == v for k, v in match.items())]


def _csv(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        for r in rows:
            w.writerow(r)


HEADERS = {
    "entities": ["entity_id", "type", "name", "location"],
    "lots": ["lot_code", "packer_id", "pack_date", "product", "farm_ids"],
    "shipments": ["ship_date", "distributor_id", "packer_id", "store_id", "product", "lot_code", "qty_cases"],
    "receiving": ["date", "store_id", "distributor_id", "product", "lot_code", "qty_cases"],
    "cases": ["case_id", "onset_date", "store_id", "purchase_date", "product", "notes"],
}
FILES = {"entities": "entities.csv", "lots": "packer_lots.csv", "shipments": "distributor_shipments.csv",
         "receiving": "store_receiving.csv", "cases": "illness_cases.csv"}


def write_case(d, w, flat=False, headers=None):
    """Write world w as case files in folder d. flat=True puts every file in one folder (like C-0001-working).
    headers: {"receiving": [...]} to write a file with other column names."""
    os.makedirs(d, exist_ok=True)
    for key, name in FILES.items():
        _csv(os.path.join(d, name), (headers or {}).get(key) or HEADERS[key], w[key])
    for folder, files in (("supplier_emails", w["emails"]), ("delivery_notes", w["notes"]), ("", w["files"])):
        for name, text in files.items():
            sub = d if flat or not folder else os.path.join(d, folder)
            path = os.path.join(sub, (folder + "__" + name) if flat and folder else name)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)
    return d


def copy_world(w):
    return copy.deepcopy(w)
