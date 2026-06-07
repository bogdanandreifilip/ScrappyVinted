import os
import json
import time
import requests
from playwright.sync_api import sync_playwright

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

SEARCH_FILE = "searches.json"
SEEN_FILE = "seen.json"


# ---------------- FILES ----------------
def load_json(file, default):
    try:
        with open(file, "r") as f:
            return json.load(f)
    except:
        return default


def save_json(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=2)


# ---------------- TELEGRAM ----------------
def send(text):
    if not TELEGRAM_TOKEN:
        return

    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": text},
            timeout=10
        )
        print("📨 SENT")
    except Exception as e:
        print("Telegram error:", e)


# ---------------- COMMANDS ----------------
def handle_commands():

    try:
        data = requests.get(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates",
            timeout=10
        ).json()
    except:
        return

    searches = load_json(SEARCH_FILE, [])

    for u in data.get("result", []):

        if "message" not in u:
            continue

        text = u["message"].get("text", "")

        # /add name keywords price(optional)
        if text.startswith("/add"):
            parts = text.split()

            if len(parts) < 3:
                send("Format: /add name keywords price(optional)")
                continue

            name = parts[1]

            price = 999999
            keywords = ""

            if parts[-1].isdigit():
                price = int(parts[-1])
                keywords = " ".join(parts[2:-1])
            else:
                keywords = " ".join(parts[2:])

            searches.append({
                "name": name,
                "keywords": keywords,
                "price_to": price
            })

            save_json(SEARCH_FILE, searches)
            send(f"✅ Added: {name}")

        if text == "/list":
            msg = "SEARCHES:\n"
            for s in searches:
                msg += f"- {s['name']} ({s['keywords']})\n"
            send(msg)

        if text.startswith("/remove"):
            name = text.replace("/remove ", "")
            searches = [s for s in searches if s["name"] != name]
            save_json(SEARCH_FILE, searches)
            send(f"🗑 Removed: {name}")


# ---------------- MATCH (PERMISSIVE) ----------------
def match(title, keywords):

    if not title:
        return False

    title = title.lower()
    keywords = keywords.lower().split()

    score = 0

    for k in keywords:
        if k in title:
            score += 2

    # accept anything with at least 1 match
    return score >= 1


# ---------------- SCRAPER ----------------
def scrape(page, search, seen):

    name = search["name"]
    keywords = search["keywords"]
    price_to = search.get("price_to", 999999)

    query = keywords.replace(" ", "%20")

    url = f"https://www.vinted.ro/catalog?search_text={query}&price_to={price_to}&order=newest_first"

    print(f"\n🔎 {name}")
    print("URL:", url)

    page.goto(url, timeout=60000)

    # 🔥 scroll to load everything
    for _ in range(5):
        page.mouse.wheel(0, 3000)
        page.wait_for_timeout(1500)

    page.wait_for_timeout(3000)

    items = page.query_selector_all("article")

    print("FOUND ITEMS:", len(items))

    sent = 0

    for item in items:

        try:
            link = item.query_selector("a[href*='/items/']")
            if not link:
                continue

            href = link.get_attribute("href")
            if not href:
                continue

            full_url = "https://www.vinted.ro" + href

            if full_url in seen:
                continue

            title = ""
            for sel in ["h3", "p", "div"]:
                el = item.query_selector(sel)
                if el:
                    t = el.inner_text().strip()
                    if t:
                        title = t.split("\n")[0]
                        break

            if not match(title, keywords):
                continue

            send(f"""🛒 {name}
🛍 {title[:100]}
🔗 {full_url}""")

            seen.append(full_url)
            sent += 1

        except Exception as e:
            print("Error:", e)

    print("SENT:", sent)


# ---------------- MAIN ----------------
def main():

    print("🚀 VINTED PLAYWRIGHT BOT START")

    handle_commands()

    searches = load_json(SEARCH_FILE, [])
    seen = load_json(SEEN_FILE, [])

    if not searches:
        print("⚠️ No searches yet")
        return

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        for s in searches:
            scrape(page, s, seen)

        browser.close()

    save_json(SEEN_FILE, seen)

    print("DONE")


if __name__ == "__main__":
    main()