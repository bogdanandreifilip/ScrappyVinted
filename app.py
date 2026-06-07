import requests
import json
import os

API_URL = "https://www.vinted.ro/api/v2/catalog/items"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json"
}

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


# ---------- utils ----------
def load_json(file, default):
    try:
        with open(file, "r") as f:
            return json.load(f)
    except:
        return default


def save_json(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=2)


# ---------- notify ----------
def notify(text):
    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        try:
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                json={
                    "chat_id": TELEGRAM_CHAT_ID,
                    "text": text
                },
                timeout=10
            )
            print("📨 SENT:", text)
        except Exception as e:
            print("❌ TELEGRAM ERROR:", e)


# ---------- scrape ----------
def scrape(search, sent_ids):

    params = {
        "search_text": search["params"]["search_text"],
        "price_to": search["params"]["price_to"],
        "per_page": 20,
        "page": 1,
        "order": "newest_first"
    }

    try:
        r = requests.get(API_URL, headers=HEADERS, params=params, timeout=15)
        print("STATUS:", r.status_code)
        print("URL:", r.url)
    except Exception as e:
        print("REQUEST ERROR:", e)
        return

    try:
        data = r.json()
    except Exception as e:
        print("JSON ERROR:", e)
        return

    items = data.get("items", [])

    print(f"ITEMS FOUND for {search['name']}: {len(items)}")

    if not items:
        return

    for item in items:
        item_id = str(item["id"])

        if item_id in sent_ids:
            continue

        title = item.get("title", "No title")
        price = item["price"]["amount"]
        currency = item["price"]["currency_code"]
        url = item.get("url", "")

        message = (
            f"🛒 {search['name']}\n"
            f"{title}\n"
            f"💰 {price} {currency}\n"
            f"{url}"
        )

        notify(message)
        sent_ids.append(item_id)


# ---------- main ----------
def main():
    print("START SCRAPER")

    searches = load_json("searches.json", [])
    sent_ids = load_json("sent_items.json", [])

    print("SEARCH COUNT:", len(searches))
    print("SENT IDS:", len(sent_ids))

    for search in searches:
        print(f"\n🔎 Searching: {search['name']}")
        scrape(search, sent_ids)

    save_json("sent_items.json", sent_ids)

    print("DONE")


if __name__ == "__main__":
    main()