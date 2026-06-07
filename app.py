import os
import json
import requests

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

API_URL = "https://www.vinted.ro/api/v2/catalog/items"

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
        print("📨 SENT:", text)
    except Exception as e:
        print("Telegram error:", e)


# ---------------- TELEGRAM COMMANDS ----------------
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


# ---------------- SAFE API CALL ----------------
def safe_request(params):

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json"
    }

    try:
        r = requests.get(API_URL, params=params, headers=headers, timeout=15)
    except Exception as e:
        print("Request failed:", e)
        return None

    if r.status_code != 200:
        print("API BLOCKED:", r.status_code)
        print(r.text[:150])
        return None

    try:
        return r.json()
    except:
        print("NON-JSON RESPONSE")
        print(r.text[:150])
        return None


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

    data = safe_request(params)

    if not data:
        print("SKIPPED (no data)")
        return

    items = data.get("items", [])

    print("FOUND ITEMS:", len(items))

    sent = 0

    for item in items:

        try:
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

        except Exception as e:
            print("Item error:", e)

    print("SENT:", sent)


# ---------------- MAIN ----------------
def main():

    print("🚀 HYBRID VINTED BOT SAFE START")

    handle_commands()

    searches = load_json(SEARCH_FILE, [])
    seen = load_json(SEEN_FILE, [])

    if not searches:
        print("⚠️ No searches")
        return

    for s in searches:
        scrape(s, seen)

    save_json(SEEN_FILE, seen)

    print("DONE")


if __name__ == "__main__":
    main()