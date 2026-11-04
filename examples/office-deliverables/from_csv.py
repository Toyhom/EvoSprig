"""Convert a source table to the application's input: period,revenue,cost,orders."""

import argparse
import csv
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path)
    parser.add_argument("--goal", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    with args.csv.open(encoding="utf-8-sig", newline="") as stream:
        rows = [{"period": row["period"], "revenue": float(row["revenue"]),
                 "cost": float(row["cost"]), "orders": int(row["orders"])} for row in csv.DictReader(stream)]
    args.out.write_text(json.dumps({"rows": rows, "goal": args.goal}, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
