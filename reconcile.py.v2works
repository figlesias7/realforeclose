import csv
import os
from datetime import datetime
from html import escape

DATA_DIR = "data"
DOCS_DIR = "docs"

ACTIVE_FILE = os.path.join(DATA_DIR, "active_foreclosures.csv")
EVENT_FILE = os.path.join(DATA_DIR, "event_log.csv")
HTML_FILE = os.path.join(DOCS_DIR, "index.html")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(DOCS_DIR, exist_ok=True)


def latest_snapshot_file():
    candidates = []
    for name in os.listdir(DATA_DIR):
        if not name.endswith(".csv"):
            continue
        if name in {"active_foreclosures.csv", "event_log.csv", "all_seen.csv"}:
            continue
        stem = name[:-4]
        try:
            datetime.strptime(stem, "%Y-%m-%d")
            candidates.append(name)
        except ValueError:
            continue
    if not candidates:
        return None
    return os.path.join(DATA_DIR, sorted(candidates, reverse=True)[0])


def read_csv(path):
    if not path or not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path, rows, fieldnames):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})


def append_event(timestamp, case_no, action, row):
    exists = os.path.exists(EVENT_FILE)
    with open(EVENT_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not exists:
            writer.writerow([
                "Timestamp",
                "Action",
                "Case #",
                "Auction Date",
                "Property Address",
                "Final Judgment",
                "Assessed Value",
                "Plaintiff Max Bid",
                "Parcel ID",
            ])
        writer.writerow([
            timestamp,
            action,
            row.get("Case #", case_no),
            row.get("Auction Date", ""),
            row.get("Property Address", ""),
            row.get("Final Judgment", ""),
            row.get("Assessed Value", ""),
            row.get("Plaintiff Max Bid", ""),
            row.get("Parcel ID", ""),
        ])


def normalize_row(row):
    return {
        "Auction Date": row.get("Auction Date", ""),
        "Property Address": row.get("Property Address", ""),
        "Final Judgment": row.get("Final Judgment", ""),
        "Assessed Value": row.get("Assessed Value", ""),
        "Plaintiff Max Bid": row.get("Plaintiff Max Bid", ""),
        "Case #": row.get("Case #", ""),
        "Parcel ID": row.get("Parcel ID", ""),
        "Case Link": row.get("Case Link", ""),
        "Parcel Link": row.get("Parcel Link", ""),
    }


def build_html(active_rows, event_rows):
    active_body = "\n".join(
        f"""
        <tr>
          <td>{escape(r.get("Auction Date", ""))}</td>
          <td>{escape(r.get("Property Address", ""))}</td>
          <td>{escape(r.get("Final Judgment", ""))}</td>
          <td>{escape(r.get("Assessed Value", ""))}</td>
          <td>{escape(r.get("Plaintiff Max Bid", ""))}</td>
          <td>{escape(r.get("Case #", ""))}</td>
          <td>{escape(r.get("Parcel ID", ""))}</td>
        </tr>
        """
        for r in active_rows
    ) or '<tr><td colspan="7">No active foreclosures</td></tr>'

    event_body = "\n".join(
        f"""
        <tr>
          <td>{escape(r.get("Timestamp", ""))}</td>
          <td>{escape(r.get("Action", ""))}</td>
          <td>{escape(r.get("Case #", ""))}</td>
          <td>{escape(r.get("Auction Date", ""))}</td>
          <td>{escape(r.get("Property Address", ""))}</td>
        </tr>
        """
        for r in event_rows[:100]
    ) or '<tr><td colspan="5">No changes logged</td></tr>'

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Foreclosure Dashboard</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 20px; }}
    h1, h2 {{ margin-bottom: 12px; }}
    table {{ border-collapse: collapse; width: 100%; margin-top: 10px; margin-bottom: 28px; }}
    th, td {{ border: 1px solid #ccc; padding: 8px; text-align: left; vertical-align: top; }}
    th {{ background: #f3f3f3; }}
  </style>
</head>
<body>
  <h1>Active Foreclosures</h1>
  <table>
    <thead>
      <tr>
        <th>Auction Date</th>
        <th>Property Address</th>
        <th>Final Judgment</th>
        <th>Assessed Value</th>
        <th>Plaintiff Max Bid</th>
        <th>Case #</th>
        <th>Parcel ID</th>
      </tr>
    </thead>
    <tbody>
      {active_body}
    </tbody>
  </table>

  <h2>Recent Changes</h2>
  <table>
    <thead>
      <tr>
        <th>Timestamp</th>
        <th>Action</th>
        <th>Case #</th>
        <th>Auction Date</th>
        <th>Property Address</th>
      </tr>
    </thead>
    <tbody>
      {event_body}
    </tbody>
  </table>
</body>
</html>
"""
    with open(HTML_FILE, "w", encoding="utf-8") as f:
        f.write(html)


def main():
    snapshot = latest_snapshot_file()
    if not snapshot:
        print("No dated snapshot CSV found in data/")
        return

    latest_rows = [normalize_row(r) for r in read_csv(snapshot)]
    previous_rows = [normalize_row(r) for r in read_csv(ACTIVE_FILE)]

    latest_by_case = {r["Case #"]: r for r in latest_rows if r.get("Case #")}
    previous_by_case = {r["Case #"]: r for r in previous_rows if r.get("Case #")}

    timestamp = datetime.now().isoformat(timespec="seconds")

    for case_no, row in latest_by_case.items():
        if case_no not in previous_by_case:
            append_event(timestamp, case_no, "NEW", row)

    for case_no, row in previous_by_case.items():
        if case_no not in latest_by_case:
            append_event(timestamp, case_no, "CLOSED", row)

    fieldnames = [
        "Auction Date",
        "Property Address",
        "Final Judgment",
        "Assessed Value",
        "Plaintiff Max Bid",
        "Case #",
        "Parcel ID",
        "Case Link",
        "Parcel Link",
    ]
    write_csv(ACTIVE_FILE, list(latest_by_case.values()), fieldnames)

    event_rows = read_csv(EVENT_FILE)
    event_rows = sorted(event_rows, key=lambda r: r.get("Timestamp", ""), reverse=True)

    active_rows = list(latest_by_case.values())
    active_rows = sorted(active_rows, key=lambda r: (r.get("Auction Date", ""), r.get("Case #", "")))

    build_html(active_rows, event_rows)

    print(f"Snapshot: {os.path.basename(snapshot)}")
    print(f"Active cases: {len(active_rows)}")
    print(f"New cases this run: {sum(1 for c in latest_by_case if c not in previous_by_case)}")
    print(f"Closed cases this run: {sum(1 for c in previous_by_case if c not in latest_by_case)}")


if __name__ == "__main__":
    main()