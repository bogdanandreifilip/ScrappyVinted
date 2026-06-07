import requests
import os
import json
import time
from bs4 import BeautifulSoup

# ---------- CONFIG ----------
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

HEADERS = {"User-Agent": "Mozilla/5.0"}

SEARCHES_FILE = "searches.json"
SEEN_FILE = "seen.json"

MAX_PAGES = 3  # auto expand pages


# ---------- UTILS ----------
def load_json(file, default):
    if os.path.exists(file):
        with open(file, "r") as f:
            return json.load(f)
    return default


def save_json(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=2)


def notify(text):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return

    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "disable_web_page_preview": True
        },
        timeout=10
    )


# ---------- TELEGRAM COMMANDS ----------
def handle_commands():
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
    r = requests.get(url, timeout=10).json()

    searches = load_json(SEARCHES_FILE, [])

    for update in r.get("result", []):
        msg = update.get("message", {})
        text = msg.get("text", "")
        chat_id = msg.get("chat", {}).get("id")

        if str(chat_id) != TELEGRAM_CHAT_ID:
            continue

        if text.startswith("/add"):
            parts = text.split(maxsplit=3)
            if len(parts) != 4:
                notify("❌ Format: /add <name> <query> <price>")
                continue

            name = parts[1]
            query = parts[2]
            price = int(parts[3])

            searches = [s for s in searches if s["name"] != name]
            searches.append({
                "name": name,
                "query": query,
                "price_to": price
            })

            save_json(SEARCHES_FILE, searches)
            notify(f"✅ Added: {name}")

        if text.startswith("/list"):
            if not searches:
                notify("⚠️ No searches")
            else:
                msg = "\n".join(f"- {s['name']} ({s['price_to']})" for s in searches)
                notify(msg)

        if text.startswith("/remove"):
            name = text.replace("/remove", "").strip()
            searches = [s for s in searches if s["name"] != name]
            save_json(SEARCHES_FILE, searches)
            notify(f"🗑 Removed: {name}")


# ---------- SCRAPER ----------
def scrape(search, seen):
    print(f"🔎 {search['name']}")
    sent = 0

    for page in range(1, MAX_PAGES + 1):
        url = (
            "https://www.olx.ro/oferte/q-"
            + search["query"].replace(" ", "-")
            + f"/?page={page}&search%5Bfilter_float_price%3Ato%5D={search['price_to']}"
        )

        print("URL:", url)

        r = requests.get(url, headers=HEADERS, timeout=20)
        soup = BeautifulSoup(r.text, "html.parser")

        cards = soup.select("div[data-cy='l-card']")
        print(f"PAGE {page} FOUND:", len(cards))

        if not cards:
            break

        for card in cards:
            link = card.find("a", href=True)
            title_el = card.find("h6")
            price_el = card.select_one("p[data-testid='ad-price']")

            if not link or not title_el or not price_el:
                continue

            href = link["href"]
            if not href.startswith("http"):
                href = "https://www.olx.ro" + href

            if href in seen:
                continue

            title = title_el.get_text(strip=True).lower()
            price = price_el.get_text(strip=True)

            # HARD FILTER (anti haine)
            required = ["ceas", "watch", "seiko", "automatic"]
            if not any(r in title for r in required):
                continue

            message = (
                f"⌚ {search['name']}\n"
                f"{title}\n"
                f"💰 {price}\n"
                f"{href}"
            )

            notify(message)
            seen.add(href)
            sent += 1

        time.sleep(2)

    print("SENT:", sent)


# ---------- MAIN ----------
def main():
    print("🚀 OLX TELEGRAM BOT START")

    handle_commands()

    searches = load_json(SEARCHES_FILE, [])
    if not searches:
        print("⚠️ No searches found")
        return

    seen = set(load_json(SEEN_FILE, []))

    for s in searches:
        scrape(s, seen)

    save_json(SEEN_FILE, list(seen))
    print("DONE")


if __name__ == "__main__":
    main()