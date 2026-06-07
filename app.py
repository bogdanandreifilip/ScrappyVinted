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
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": text
            }
        )
        print("SENDING MESSAGE:", text)


# ---------- scrape ----------
def scrape(search, sent_ids):
    params = {
        "search_text": search["params"]["search_text"],
        "price_to": search["params"]["price_to"],
        "per_page": 10,
        "page": 1
    }
  

    r = requests.get(API_URL, headers=HEADERS, params=params, timeout=15)

    try:
        data = r.json()
    except:
        print("API error / rate limit")
        return

    for item in data.get("items", []):
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

        print(data)
        print(len(data.get("items", [])))

        notify(message)
        sent_ids.append(item_id)


# ---------- main ----------
def main():
    print("START SCRAPER")

    searches = load_json("searches.json", [])
    sent_ids = load_json("sent_items.json", [])

    for search in searches:
        print(f"Searching: {search['name']}")
        scrape(search, sent_ids)

    save_json("sent_items.json", sent_ids)
    print("DONE")


if __name__ == "__main__":
    main()