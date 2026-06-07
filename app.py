import os
import json
from playwright.sync_api import sync_playwright

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def notify(text):
    import requests
    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": text}
        )
        print("SENT:", text)


def load_json(file, default):
    try:
        with open(file, "r") as f:
            return json.load(f)
    except:
        return default


def save_json(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=2)


def scrape(page, search, sent_ids):

    query = search["params"]["search_text"]
    price_to = search["params"]["price_to"]

    url = f"https://www.vinted.ro/catalog?search_text={query}&price_to={price_to}"

    page.goto(url, timeout=60000)
    page.wait_for_timeout(5000)

    items = page.query_selector_all("a[href*='/items/']")

    print(f"FOUND LINKS: {len(items)}")

    for item in items:
        try:
            href = item.get_attribute("href")
            if not href:
                continue

            full_url = "https://www.vinted.ro" + href

            if full_url in sent_ids:
                continue

            title = item.inner_text()[:80]

            message = f"""🛒 {search['name']}
{title}
{full_url}"""

            notify(message)
            sent_ids.append(full_url)

        except:
            continue


def main():
    print("START PLAYWRIGHT SCRAPER")

    searches = load_json("searches.json", [])
    sent_ids = load_json("sent_items.json", [])

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        for search in searches:
            print("Searching:", search["name"])
            scrape(page, search, sent_ids)

        browser.close()

    save_json("sent_items.json", sent_ids)
    print("DONE")


if __name__ == "__main__":
    main()