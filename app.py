import os
import json
import re
import requests
from playwright.sync_api import sync_playwright

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

SEARCH_FILE = "searches.json"
SEEN_FILE = "seen.json"


# ---------------- FILE HELPERS ----------------
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

        # ---------------- ADD ----------------
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

        # ---------------- LIST ----------------
        if text == "/list":
            msg = "SEARCHES:\n"
            for s in searches:
                msg += f"- {s['name']} ({s['keywords']})\n"
            send(msg)

        # ---------------- REMOVE ----------------
        if text.startswith("/remove"):
            name = text.replace("/remove ", "")
            searches = [s for s in searches if s["name"] != name]
            save_json(SEARCH_FILE, searches)
            send(f"🗑 Removed: {name}")


# ---------------- AI FILTER ----------------
def normalize(text):
    text = text.lower()
    text = re.sub(r"[^a-z0-9 ]", " ", text)
    return " ".join(text.split())


def match(title, keywords):

    if not title:
        return False

    title = normalize(title)
    keywords = normalize(keywords)

    title_tokens = set(title.split())
    keyword_tokens = keywords.split()

    score = 0

    # 🔥 exact token match
    for k in keyword_tokens:
        if k in title_tokens:
            score += 3

    # 🔥 fuzzy match
    for k in keyword_tokens:
        for t in title_tokens:
            if k in t or t in k:
                score += 1

    # 🔥 brand boost
    brands = [
        "seiko", "casio", "rolex", "omega",
        "jordan", "nike", "adidas", "puma"
    ]

    for b in brands:
        if b in title_tokens and b in keyword_tokens:
            score += 2

    # 🔥 noise penalty
    noise = ["lot", "bundle", "kids", "broken", "parts", "spare"]
    for n in noise:
        if n in title_tokens:
            score -= 2

    # 🔥 adaptive threshold
    if len(keyword_tokens) <= 2:
        threshold = 2
    else:
        threshold = 3

    return score >= threshold


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

    # 🔥 scroll to load more items
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

    print("🚀 VINTED AI PLAYWRIGHT BOT START")

    handle_commands()

    searches = load_json(SEARCH_FILE, [])
    seen = load_json(SEEN_FILE, [])

    if not searches:
        print("⚠️ No searches")
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