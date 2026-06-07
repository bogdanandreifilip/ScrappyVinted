import os
import json
import requests
import sqlite3
from playwright.sync_api import sync_playwright

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

DB_FILE = "bot.db"
SEEN_FILE = "seen.json"


# ---------------- DB ----------------
def db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS searches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        category TEXT,
        keywords TEXT,
        price_to INTEGER
    )
    """)

    conn.commit()
    return conn


# ---------------- FILES ----------------
def load_seen():
    try:
        with open(SEEN_FILE, "r") as f:
            return json.load(f)
    except:
        return []


def save_seen(data):
    with open(SEEN_FILE, "w") as f:
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
        print("📨 SENT:", text)
    except Exception as e:
        print("Telegram error:", e)


# ---------------- COMMANDS ----------------
def handle_commands():

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
    data = requests.get(url).json()

    conn = db()
    c = conn.cursor()

    for u in data.get("result", []):

        if "message" not in u:
            continue

        text = u["message"].get("text", "")
        chat_id = str(u["message"]["chat"]["id"])

        if chat_id != str(TELEGRAM_CHAT_ID):
            continue

        # ---------------- ADD SAFE ----------------
        if text.startswith("/add"):

            parts = text.split()

            if len(parts) < 5:
                send("Format: /add name category price keywords...")
                continue

            name = parts[1]
            category = parts[2]

            price = None
            price_index = None

            for i in range(3, len(parts)):
                if parts[i].isdigit():
                    price = int(parts[i])
                    price_index = i
                    break

            if price is None:
                send("❌ Price missing: /add Seiko watch 200 seiko automatic")
                continue

            keywords = " ".join(parts[3:price_index] + parts[price_index+1:])

            c.execute(
                "INSERT INTO searches (name, category, keywords, price_to) VALUES (?, ?, ?, ?)",
                (name, category, keywords, price)
            )

            conn.commit()
            send(f"✅ Added: {name}")

        if text == "/list":
            c.execute("SELECT name, category FROM searches")
            rows = c.fetchall()

            msg = "SEARCHES:\n"
            for r in rows:
                msg += f"- {r[0]} ({r[1]})\n"

            send(msg)

        if text.startswith("/remove"):
            name = text.replace("/remove ", "")
            c.execute("DELETE FROM searches WHERE name = ?", (name,))
            conn.commit()
            send(f"🗑 Removed: {name}")

    conn.close()


# ---------------- MATCH (STABLE) ----------------
def match(category, title, keywords):

    title = title.lower()
    keywords = keywords.lower().split()

    rules = {
        "watch": ["watch", "seiko", "casio", "omega", "rolex", "automatic", "diver"],
        "sneaker": ["jordan", "nike", "adidas", "sneaker", "air"],
        "jewelry": ["ring", "necklace", "bracelet", "gold", "silver"]
    }

    category_hit = True
    if category in rules:
        category_hit = any(w in title for w in rules[category])

    keyword_hit = any(k in title for k in keywords)

    return keyword_hit or category_hit


# ---------------- SCRAPER (FINAL FIXED VINTED) ----------------
def scrape(page, search, seen):

    name, category, keywords, price_to = search

    query = "%20".join(keywords.split())

    url = (
        "https://www.vinted.ro/catalog?"
        f"search_text={query}"
        f"&price_to={price_to}"
        "&order=newest_first"
    )

    print(f"\n🔎 {name}")
    print("URL:", url)

    page.goto(url, timeout=60000)

    # IMPORTANT: wait JS render
    page.wait_for_timeout(9000)

    # 🔥 ONLY REAL ITEM LINKS
    items = page.query_selector_all("a[href*='/items/']")

    # fallback dacă Vinted schimbă structura
    if not items:
        items = page.query_selector_all("article a[href]")

    print("FOUND LINKS:", len(items))

    sent = 0

    for item in items:

        try:
            href = item.get_attribute("href")

            if not href:
                continue

            # ensure valid product link
            if "/items/" not in href:
                continue

            full_url = "https://www.vinted.ro" + href

            if full_url in seen:
                continue

            title = item.inner_text().strip()
            title = title.split("\n")[0] if title else ""

            if not title:
                continue

            if not match(category, title, keywords):
                continue

            send(f"""🛒 {name}
🛍 {title[:90]}
🔗 {full_url}""")

            seen.append(full_url)
            sent += 1

        except Exception as e:
            print("Item error:", e)

    print("SENT:", sent)


# ---------------- MAIN ----------------
def main():

    print("🚀 PRO V2.5 FINAL STABLE START")

    handle_commands()

    conn = db()
    c = conn.cursor()

    c.execute("SELECT name, category, keywords, price_to FROM searches")
    searches = c.fetchall()
    conn.close()

    if not searches:
        print("⚠️ No searches found")
        return

    seen = load_seen()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        for s in searches:
            scrape(page, s, seen)

        browser.close()

    save_seen(seen)

    print("DONE")


if __name__ == "__main__":
    main()