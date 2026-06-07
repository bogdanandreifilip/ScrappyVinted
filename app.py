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


# ---------------- COMMANDS (FIXED) ----------------
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

        # ---------------- ADD (ROBUST FIX) ----------------
        if text.startswith("/add"):

            parts = text.split()

            if len(parts) < 5:
                send("Format: /add name category price keywords...")
                continue

            name = parts[1]
            category = parts[2]

            # 🔥 FIND PRICE (first number anywhere)
            price = None
            price_index = None

            for i in range(3, len(parts)):
                if parts[i].isdigit():
                    price = int(parts[i])
                    price_index = i
                    break

            if price is None:
                send("❌ Nu am găsit un preț numeric. Exemplu: /add Seiko watch 200 automatic")
                continue

            # keywords = everything else
            keywords = " ".join(parts[3:price_index] + parts[price_index+1:])

            c.execute(
                "INSERT INTO searches (name, category, keywords, price_to) VALUES (?, ?, ?, ?)",
                (name, category, keywords, price)
            )

            conn.commit()
            send(f"✅ Added: {name}")

        # ---------------- LIST ----------------
        if text == "/list":
            c.execute("SELECT name, category FROM searches")
            rows = c.fetchall()

            msg = "SEARCHES:\n"
            for r in rows:
                msg += f"- {r[0]} ({r[1]})\n"

            send(msg)

        # ---------------- REMOVE ----------------
        if text.startswith("/remove"):
            name = text.replace("/remove ", "")

            c.execute("DELETE FROM searches WHERE name = ?", (name,))
            conn.commit()

            send(f"🗑 Removed: {name}")

    conn.close()


# ---------------- FILTER ----------------
def match(category, title, keywords):

    title = title.lower()

    rules = {
        "watch": ["seiko", "casio", "omega", "rolex", "watch", "automatic", "diver"],
        "sneaker": ["jordan", "nike", "adidas", "sneaker", "air"],
        "jewelry": ["ring", "necklace", "bracelet", "gold", "silver"]
    }

    if category in rules:
        if not any(w in title for w in rules[category]):
            return False

    return any(k.lower() in title for k in keywords.split())


# ---------------- SCRAPER ----------------
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

    page.goto(url, timeout=60000)
    page.wait_for_timeout(4000)

    items = page.query_selector_all("a[href*='/items/']")

    sent = 0

    for item in items:

        try:
            href = item.get_attribute("href")
            if not href:
                continue

            full_url = "https://www.vinted.ro" + href

            if full_url in seen:
                continue

            title = item.inner_text().strip()

            if not match(category, title, keywords):
                continue

            send(f"""🛒 {name}
🛍 {title[:90]}
🔗 {full_url}""")

            seen.append(full_url)
            sent += 1

        except:
            continue

    print("SENT:", sent)


# ---------------- MAIN ----------------
def main():

    print("🚀 PRO V2.5 FIXED START")

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