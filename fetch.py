# ONLY CHANGE: function signature
async def get_month_info(page, current_month_url) -> tuple[list[dict], str | None]:
    boxes = await page.locator(".CALBOX").all()
    days = []

    for idx in range(len(boxes)):
        try:
            box = page.locator(".CALBOX").nth(idx)
            text = clean_text(await box.inner_text(timeout=3000))
        except Exception:
            continue

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
        })

    next_month_url = None
    links = await page.locator("a").evaluate_all(
        """
        els => els.map(a => ({
            text: (a.innerText || a.textContent || '').trim(),
            href: a.href || ''
        }))
        """
    )

    candidates = []
    for link in links:
        href = link["href"]
        if "zmethod=calendar" in href.lower() and "selCalDate=" in href:
            candidates.append(href)

    if candidates:
        next_month_url = candidates[-1]

    # 🔥 DEBUG BLOCK (ONLY ADDITION)
    print("\n====================")
    print("CURRENT MONTH:", current_month_url)
    print("CANDIDATES:")
    for c in candidates:
        print("  ", c)
    print("CHOSEN NEXT MONTH:", next_month_url)
    print("====================\n")

    return days, next_month_url