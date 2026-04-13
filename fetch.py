import asyncio
from playwright.async_api import async_playwright
import csv
import json
import os
import re
from datetime import datetime

BASE_DOMAIN = "https://www.pinellas.realforeclose.com"
CALENDAR_URL = f"{BASE_DOMAIN}/index.cfm?zaction=USER&zmethod=CALENDAR"

DATA_DIR = "data"
TODAY_FILE = os.path.join(DATA_DIR, f"{datetime.now().strftime('%Y-%m-%d')}.csv")
SEEN_FILE = os.path.join(DATA_DIR, "all_seen.csv")
INDEX_FILE = os.path.join(DATA_DIR, "index.json")

os.makedirs(DATA_DIR, exist_ok=True)


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
        address = clean_text(match.group("address"))
        rows.append({
            "Property Address": address,
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
            "Property Address",
            "Final Judgment",
            "Assessed Value",
            "Plaintiff Max Bid",
            "Case #",
            "Parcel ID",
        ])
        for r in rows:
            writer.writerow([
                r["Property Address"],
                r["Final Judgment"],
                r["Assessed Value"],
                r["Plaintiff Max Bid"],
                r["Case #"],
                r["Parcel ID"],
            ])


async def get_live_foreclosure_days(page):
    boxes = await page.locator(".CALBOX").all()
    days = []

    for idx, box in enumerate(boxes):
        text = clean_text(await box.inner_text())

        if "Foreclosure" not in text or "FC" not in text:
            continue

        m = re.search(r"^(\d+).*?(\d+)\s*/\s*(\d+)\s*FC", text)
        if not m:
            continue

        day_num = int(m.group(1))
        active = int(m.group(2))
        scheduled = int(m.group(3))

        if active <= 0:
            continue

        days.append({
            "index": idx,
            "day": day_num,
            "active": active,
            "scheduled": scheduled,
            "text": text,
        })

    return days


async def get_next_month_url(page):
    links = await page.locator("a").evaluate_all(
        """
        els => els.map(a => ({
            text: (a.innerText || a.textContent || '').trim(),
            href: a.href || ''
        }))
        """
    )

    for link in links:
        href = link["href"]
        text = clean_text(link["text"])
        if "zmethod=calendar" in href.lower() and href and "selCalDate=" in href:
            if ">" in text or text.lower().startswith("may") or text.lower().startswith("jun") or text.lower().startswith("jul") or text.lower().startswith("aug") or text.lower().startswith("sep") or text.lower().startswith("oct") or text.lower().startswith("nov") or text.lower().startswith("dec") or text.lower().startswith("jan") or text.lower().startswith("feb") or text.lower().startswith("mar") or text.lower().startswith("apr"):
                return href

    return None


async def click_day(page, idx):
    box = page.locator(".CALBOX").nth(idx)
    await box.click(force=True)
    await page.wait_for_timeout(5000)


async def collect_month_data(page, month_url, seen_cases, new_rows):
    await page.goto(month_url, wait_until="domcontentloaded")
    await page.wait_for_timeout(3500)

    days = await get_live_foreclosure_days(page)
    print(f"Month page {month_url}")
    print(f"Found {len(days)} live foreclosure days")

    for item in days:
        print(f"Opening day {item['day']} with {item['active']} live auctions")

        await page.goto(month_url, wait_until="domcontentloaded")
        await page.wait_for_timeout(2500)

        await click_day(page, item["index"])

        body_text = await page.locator("body").inner_text()
        waiting_text = extract_auctions_waiting(body_text)
        rows = parse_waiting_records(waiting_text)

        print(f"  Parsed {len(rows)} waiting records")

        for r in rows:
            case_no = r["Case #"]
            if not case_no or case_no in seen_cases:
                continue
            seen_cases.add(case_no)
            new_rows.append(r)

    await page.goto(month_url, wait_until="domcontentloaded")
    await page.wait_for_timeout(2000)
    next_month_url = await get_next_month_url(page)

    return next_month_url, len(days)


async def scrape():
    seen_cases = load_seen()
    new_rows = []
    visited_months = set()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        current_month_url = CALENDAR_URL
        empty_month_streak = 0

        while current_month_url and current_month_url not in visited_months:
            visited_months.add(current_month_url)

            next_month_url, live_day_count = await collect_month_data(
                page, current_month_url, seen_cases, new_rows
            )

            if live_day_count == 0:
                empty_month_streak += 1
            else:
                empty_month_streak = 0

            if empty_month_streak >= 1:
                break

            current_month_url = next_month_url

        await browser.close()

    write_daily(new_rows)
    save_seen(seen_cases)
    update_index()
    print(f"Saved {len(new_rows)} new records")


if __name__ == "__main__":
    asyncio.run(scrape())