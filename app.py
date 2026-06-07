import os
import json
import requests

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

API_URL = "https://www.vinted.ro/api/v2/catalog/items"

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

    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        json={"chat_id": TELEGRAM_CHAT_ID, "text": text},
        timeout=10
    )


def get_updates():
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
    return requests.get(url).json()


# ---------------- COMMANDS ----------------
def handle_commands():

    data = get_updates()

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

            # detect price if last is number
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


# ---------------- MATCH ----------------
def match(title, keywords):

    if not title:
        return False

    title = title.lower()
    keywords = keywords.lower().split()

    score = 0
    for k in keywords:
        if k in title:
            score += 2

    return score >= 1


# ---------------- SCRAPER ----------------
def scrape(search, seen):

    name = search["name"]
    keywords = search["keywords"]
    price_to = search.get("price_to", 999999)

    params = {
        "search_text": keywords,
        "price_to": price_to,
        "per_page": 50,
        "page": 1,
        "order": "newest_first"
    }

    print(f"\n🔎 {name}")

    r = requests.get(API_URL, params=params, timeout=15)
    data = r.json()

    items = data.get("items", [])

    print("FOUND:", len(items))

    sent = 0

    for item in items:

        item_id = str(item["id"])

        if item_id in seen:
            continue

        title = item.get("title", "")
        price = item.get("price", {}).get("amount", "")
        currency = item.get("price", {}).get("currency_code", "")
        url = item.get("url", "")

        if not match(title, keywords):
            continue

        send(f"""🛒 {name}
🛍 {title}
💰 {price} {currency}
🔗 {url}""")

        seen.append(item_id)
        sent += 1

    print("SENT:", sent)


# ---------------- MAIN ----------------
def main():

    print("🚀 HYBRID VINTED BOT START")

    handle_commands()

    searches = load_json(SEARCH_FILE, [])
    seen = load_json(SEEN_FILE, [])

    for s in searches:
        scrape(s, seen)

    save_json(SEEN_FILE, seen)

    print("DONE")


if __name__ == "__main__":
    main()