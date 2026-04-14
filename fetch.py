# ONLY CHANGE: added auction date safely
# NOTHING ELSE TOUCHED

import asyncio
from playwright.async_api import async_playwright
import csv
import json
import os
import re
from datetime import datetime
from html import escape

BASE_DOMAIN = "https://www.pinellas.realforeclose.com"
CALENDAR_URL = f"{BASE_DOMAIN}/index.cfm?zaction=USER&zmethod=CALENDAR"

DATA_DIR = "data"
DOCS_DIR = "docs"
TODAY_STR = datetime.now().strftime("%Y-%m-%d")
TODAY_FILE = os.path.join(DATA_DIR, f"{TODAY_STR}.csv")
SEEN_FILE = os.path.join(DATA_DIR, "all_seen.csv")
INDEX_FILE = os.path.join(DATA_DIR, "index.json")
HTML_FILE = os.path.join(DOCS_DIR, "index.html")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(DOCS_DIR, exist_ok=True)


def load_seen():
    if not os.path.exists(SEEN_FILE):
        return set()
    with open(SEEN_FILE, newline="", encoding="utf-8") as f:
        return {row[0].strip() for row in csv.reader(f) if row and row[0].strip()}


def save_seen(seen):
    with open(SEEN_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        for case_no in sorted(seen):
            writer.writerow([case_no])


def update_index():
    files = sorted(
        [f for f in os.listdir(DATA_DIR) if f.endswith(".csv") and f != "all_seen.csv"],
        reverse=True,
    )
    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(files, f)
    return files


def clean_text(value: str) -> str:
    return " ".join(value.replace("\xa0", " ").split())


def extract_auctions_waiting(text: str) -> str:
    start = text.find("Auctions Waiting")
    if start == -1:
        return ""

    section = text[start:]

    stop_markers = [
        "Auctions Closed",
        "Closed Auctions",
        "Canceled Auctions",
        "Auctions Canceled",
        "Sales List",
        "Connection",
        "About Us | Site Map |",
    ]

    end_positions = [section.find(marker) for marker in stop_markers if section.find(marker) != -1]
    if end_positions:
        section = section[:min(end_positions)]

    return section


def parse_waiting_records(section_text: str):
    if not section_text:
        return []

    pattern = re.compile(
        r"(?:Auction Starts\s*(?P<auction_date>\d{2}/\d{2}/\d{4}\s+\d{1,2}:\d{2}\s+[AP]M\s+ET).*?)?"
        r"Case #:\s*(?P<case>\S+).*?"
        r"Final Judgment Amount:\s*(?P<judgment>\$[\d,]+\.\d{2}|Hidden).*?"
        r"Parcel ID:\s*(?P<parcel>\S+).*?"
        r"Property Address:\s*(?P<address>.*?)"
        r"Assessed Value:\s*(?P<assessed>\$[\d,]+\.\d{2}|Hidden).*?"
        r"Plaintiff Max Bid:\s*(?P<max_bid>\$[\d,]+\.\d{2}|Hidden)",
        re.DOTALL | re.IGNORECASE,
    )

    rows = []

    for match in pattern.finditer(section_text):
        rows.append({
            "Auction Date": clean_text(match.group("auction_date") or ""),
            "Property Address": clean_text(match.group("address")),
            "Final Judgment": clean_text(match.group("judgment")),
            "Assessed Value": clean_text(match.group("assessed")),
            "Plaintiff Max Bid": clean_text(match.group("max_bid")),
            "Case #": clean_text(match.group("case")),
            "Parcel ID": clean_text(match.group("parcel")),
        })

    return rows


def write_daily(rows):
    with open(TODAY_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Auction Date",
            "Property Address",
            "Final Judgment",
            "Assessed Value",
            "Plaintiff Max Bid",
            "Case #",
            "Parcel ID",
        ])
        for r in rows:
            writer.writerow([
                r["Auction Date"],
                r["Property Address"],
                r["Final Judgment"],
                r["Assessed Value"],
                r["Plaintiff Max Bid"],
                r["Case #"],
                r["Parcel ID"],
            ])


def read_csv_rows(path):
    rows = []
    if not os.path.exists(path):
        return rows
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def build_html(index_files):
    list_items = []
    sections = []

    for i, file in enumerate(index_files):
        date_label = file.replace(".csv", "")
        section_id = f"day-{date_label}"

        list_items.append(
            f'<li><a href="#{section_id}">{escape(date_label)}</a></li>'
        )

        rows = read_csv_rows(os.path.join(DATA_DIR, file))
        if rows:
            body_rows = "\n".join(
                f"""
                <tr>
                  <td>{escape(r.get("Auction Date",""))}</td>
                  <td>{escape(r.get("Property Address",""))}</td>
                  <td>{escape(r.get("Final Judgment",""))}</td>
                  <td>{escape(r.get("Assessed Value",""))}</td>
                  <td>{escape(r.get("Plaintiff Max Bid",""))}</td>
                  <td>{escape(r.get("Case #",""))}</td>
                  <td>{escape(r.get("Parcel ID",""))}</td>
                </tr>
                """
                for r in rows
            )
        else:
            body_rows = '<tr><td colspan="7">No records</td></tr>'

        sections.append(
            f"""
            <section id="{section_id}">
              <h2>{escape(date_label)}</h2>
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
                  {body_rows}
                </tbody>
              </table>
            </section>
            """
        )

    html = f"""<html><body><h1>Daily New Foreclosures</h1>
<ul>{''.join(list_items)}</ul>
{''.join(sections)}
</body></html>"""

    with open(HTML_FILE, "w", encoding="utf-8") as f:
        f.write(html)


async def get_live_foreclosure_days(page):
    boxes = await page.locator(".CALBOX").all()
    days = []

    for idx, box in enumerate(boxes):
        text = clean_text(await box.inner_text())

        if "FC" not in text:
            continue

        m = re.search(r"(\d+)\s*/\s*(\d+)\s*FC", text)
        if not m:
            continue

        if int(m.group(1)) == 0:
            continue

        days.append({"index": idx})

    return days


async def scrape():
    seen_cases = load_seen()
    rows = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        await page.goto(CALENDAR_URL)
        await page.wait_for_timeout(3000)

        days = await get_live_foreclosure_days(page)

        for d in days:
            await page.goto(CALENDAR_URL)
            await page.wait_for_timeout(2000)

            await page.locator(".CALBOX").nth(d["index"]).click()
            await page.wait_for_timeout(5000)

            body = await page.locator("body").inner_text()
            section = extract_auctions_waiting(body)
            parsed = parse_waiting_records(section)

            for r in parsed:
                if r["Case #"] not in seen_cases:
                    rows.append(r)
                    seen_cases.add(r["Case #"])

        await browser.close()

    write_daily(rows)
    save_seen(seen_cases)
    index = update_index()
    build_html(index)


if __name__ == "__main__":
    asyncio.run(scrape())