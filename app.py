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

    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        json={"chat_id": TELEGRAM_CHAT_ID, "text": text},
        timeout=10
    )


# ---------------- CATEGORY FILTER ----------------
def category_ok(category, title):

    title = title.lower()

    rules = {
        "watch": ["watch", "seiko", "casio", "omega", "rolex", "automatic"],
        "sneaker": ["jordan", "nike", "adidas", "sneaker"],
        "jewelry": ["ring", "necklace", "bracelet", "gold", "silver"]
    }

    if category not in rules:
        return True

    return any(k in title for k in rules[category])


# ---------------- SCORE ----------------
def score(title, keywords):

    title = title.lower()
    s = 0

    for k in keywords:
        if k in title:
            s += 2

    return s


# ---------------- SCRAPE ----------------
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

    print("\n🔎", search["name"])

    page.goto(url, timeout=60000)
    page.wait_for_timeout(4000)

    items = page.query_selector_all("a[href*='/items/']")

    print("FOUND:", len(items))

    for item in items:

        try:
            href = item.get_attribute("href")
            if not href:
                continue

            full_url = "https://www.vinted.ro" + href

            if full_url in seen:
                continue

            title = item.inner_text().strip()

            # FILTER
            if not category_ok(category, title):
                continue

            # SCORE FILTER (simplu)
            s = score(title, keywords)
            if s < 1:
                continue

            msg = f"""🛒 {search['name']}
⭐ Score: {s}
🛍 {title[:80]}
🔗 {full_url}"""

            send(msg)
            seen.append(full_url)

        except:
            continue


# ---------------- TELEGRAM COMMANDS ----------------
def handle_commands():

    import time

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
    r = requests.get(url).json()

    searches = load(SEARCH_FILE, [])

    for update in r.get("result", []):

        if "message" not in update:
            continue

        text = update["message"].get("text", "")
        chat_id = str(update["message"]["chat"]["id"])

        if chat_id != str(TELEGRAM_CHAT_ID):
            continue

        # /add watch seiko automatic 200
        if text.startswith("/add"):
            parts = text.split(" ")

            if len(parts) < 4:
                send("Format: /add name category keywords price")
                continue

            name = parts[1]
            category = parts[2]
            price = int(parts[-1])
            keywords = parts[3:-1]

            searches.append({
                "name": name,
                "category": category,
                "params": {
                    "keywords": keywords,
                    "price_to": price
                }
            })

            save(SEARCH_FILE, searches)
            send(f"Added: {name}")

        if text == "/list":
            msg = "SEARCHES:\n"
            for s in searches:
                msg += f"- {s['name']} ({s['category']})\n"
            send(msg)

        if text.startswith("/remove"):
            name = text.replace("/remove ", "")
            searches = [s for s in searches if s["name"] != name]
            save(SEARCH_FILE, searches)
            send(f"Removed: {name}")


# ---------------- MAIN ----------------
def main():

    print("🚀 PRO V2 START")

    handle_commands()

    searches = load(SEARCH_FILE, [])
    seen = load(SEEN_FILE, [])

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