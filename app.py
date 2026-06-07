import os
import json
import requests
from playwright.sync_api import sync_playwright

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

SEARCH_FILE = "searches.json"
SEEN_FILE = "seen.json"


# ---------------- JSON ----------------
def load(file, default):
    try:
        with open(file, "r") as f:
            return json.load(f)
    except:
        return default


def save(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=2)


# ---------------- TELEGRAM ----------------
def send(text):
    if not TELEGRAM_TOKEN:
        return

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


# ---------------- SMART CATEGORY FILTER (FIXED) ----------------
def category_match(category, title):

    title = title.lower()

    rules = {
        "watch": ["seiko", "casio", "omega", "rolex", "watch", "automatic", "diver"],
        "sneaker": ["jordan", "nike", "adidas", "sneaker", "air"],
        "jewelry": ["ring", "necklace", "bracelet", "gold", "silver"]
    }

    if category not in rules:
        return True

    # soft match (NU blocăm agresiv)
    return any(w in title for w in rules[category])


# ---------------- KEYWORD MATCH (FIXED) ----------------
def keyword_match(keywords, title):

    title = title.lower()

    # trebuie măcar 1 keyword să apară
    return any(k.lower() in title for k in keywords)


# ---------------- SCRAPER ----------------
def scrape(page, search, seen):

    params = search["params"]
    keywords = params["keywords"]
    price_to = params["price_to"]
    category = search["category"]

    query = "%20".join(keywords)

    url = (
        "https://www.vinted.ro/catalog?"
        f"search_text={query}"
        f"&price_to={price_to}"
        "&order=newest_first"
    )

    print(f"\n🔎 SEARCH: {search['name']}")
    print("URL:", url)

    page.goto(url, timeout=60000)
    page.wait_for_timeout(4000)

    items = page.query_selector_all("a[href*='/items/']")

    print("FOUND:", len(items))

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

            # ---------------- DEBUG (IMPORTANT) ----------------
            print("TITLE:", title[:60])

            # ---------------- FILTERS ----------------
            if not category_match(category, title):
                continue

            if not keyword_match(keywords, title):
                continue

            # ---------------- SEND ----------------
            msg = f"""🛒 {search['name']}
🛍 {title[:90]}
🔗 {full_url}"""

            send(msg)

            seen.append(full_url)
            sent += 1

        except Exception as e:
            print("Error:", e)

    print("SENT THIS RUN:", sent)


# ---------------- MAIN ----------------
def main():

    print("🚀 PRO V2 START")

    searches = load(SEARCH_FILE, [])
    seen = load(SEEN_FILE, [])

    if not searches:
        print("⚠️ No searches found. Add via /add in Telegram.")
        return

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        for s in searches:
            scrape(page, s, seen)

        browser.close()

    save(SEEN_FILE, seen)

    print("DONE")


if __name__ == "__main__":
    main()