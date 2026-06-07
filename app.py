import os
import json
import requests
from playwright.sync_api import sync_playwright

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
            print("Telegram error:", e)


# ---------- scraping ----------
def scrape(page, search, sent_ids):

    params = search["params"]
    keywords = [k.lower() for k in params["keywords"]]
    price_to = params["price_to"]

    url = (
        "https://www.vinted.ro/catalog?"
        f"search_text={'%20'.join(keywords)}"
        f"&price_to={price_to}"
        "&order=newest_first"
    )

    print("URL:", url)

    page.goto(url, timeout=60000)
    page.wait_for_timeout(5000)

    items = page.query_selector_all("a[href*='/items/']")

    print(f"FOUND ITEMS: {len(items)}")

    for item in items:
        try:
            href = item.get_attribute("href")
            if not href:
                continue

            full_url = "https://www.vinted.ro" + href

            if full_url in sent_ids:
                continue

            title = item.inner_text().lower()

            # 🔥 FILTER REAL (anti bijuterii / haine random)
            if not any(k in title for k in keywords):
                continue

            message = f"""🛒 {search['name']}
{title[:80]}
{full_url}"""

            notify(message)
            sent_ids.append(full_url)

        except:
            continue


# ---------- main ----------
def main():
    print("START VINTED BOT")

    searches = load_json("searches.json", [])
    sent_ids = load_json("sent_items.json", [])

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        for search in searches:
            print("\nSEARCH:", search["name"])
            scrape(page, search, sent_ids)

        browser.close()

    save_json("sent_items.json", sent_ids)
    print("DONE")


if __name__ == "__main__":
    main()