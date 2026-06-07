import requests
import json
import time
import os

API_URL = "https://www.vinted.ro/api/v2/catalog/items"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept": "application/json"
}

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")


def load_json(file, default):
    try:
        with open(file, "r") as f:
            return json.load(f)
    except:
        return default


def save_json(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=2)


def notify(message):
    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": message}
        )

    if DISCORD_WEBHOOK:
        requests.post(
            DISCORD_WEBHOOK,
            json={"content": message}
        )


def scrape(search, sent_ids):
    params = {
        **search["params"],
        "per_page": 10,
        "page": 1
    }

    r = requests.get(API_URL, headers=HEADERS, params=params, timeout=15)
    data = r.json()

    for item in data.get("items", []):
        item_id = str(item["id"])
        if item_id in sent_ids:
            continue

        title = item["title"]
        price = item["price"]["amount"]
        currency = item["price"]["currency_code"]
        url = item["url"]

        text = (
            f"🛒 {search['name']}\n"
            f"{title}\n"
            f"💰 {price} {currency}\n"
            f"{url}"
        )

        notify(text)
        sent_ids.append(item_id)


def main():
    searches = load_json("searches.json", [])
    sent_ids = load_json("sent_items.json", [])

    for search in searches:
        scrape(search, sent_ids)
        time.sleep(6)  # anti-ban

    save_json("sent_items.json", sent_ids)


if __name__ == "__main__":
    main()