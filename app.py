import os
import json
import re
import time
import random
import requests
from playwright.sync_api import sync_playwright

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

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

    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": text},
            timeout=10
        )
    except:
        pass


# ---------------- AI FILTER ----------------
def normalize(text):
    text = text.lower()
    text = re.sub(r"[^a-z0-9 ]", " ", text)
    return " ".join(text.split())


def match(title, keywords):

    if not title:
        return False

    title = normalize(title)
    keywords = normalize(keywords)

    title_tokens = set(title.split())
    keyword_tokens = keywords.split()

    score = 0

    for k in keyword_tokens:
        if k in title_tokens:
            score += 3

    for k in keyword_tokens:
        for t in title_tokens:
            if k in t or t in k:
                score += 1

    brands = ["seiko", "casio", "rolex", "omega", "jordan", "nike", "adidas"]
    for b in brands:
        if b in title_tokens and b in keyword_tokens:
            score += 2

    noise = ["lot", "bundle", "kids", "broken", "parts"]
    for n in noise:
        if n in title_tokens:
            score -= 2

    return score >= 2


# ---------------- FEED SCRAPER ----------------
def scrape_feed(page, seen, filters):

    print("\n🌍 FEED MODE ACTIVE")

    url = "https://www.vinted.ro/catalog?order=newest_first"

    page.goto(url, timeout=60000)

    # scroll infinite feed
    last_height = 0

    for _ in range(12):
        page.mouse.wheel(0, 5000)
        page.wait_for_timeout(random.randint(800, 1500))

        height = page.evaluate("document.body.scrollHeight")

        if height == last_height:
            break

        last_height = height

    items = page.query_selector_all("article")

    print("FEED ITEMS:", len(items))

    sent = 0

    for item in items:

        try:
            link = item.query_selector("a[href*='/items/']")
            if not link:
                continue

            href = link.get_attribute("href")
            if not href:
                continue

            full_url = "https://www.vinted.ro" + href

            if full_url in seen:
                continue

            text = item.inner_text().lower()

            # extract title rough
            title = text.split("\n")[0]

            # 🔥 AI FILTER AGAINST MULTIPLE KEYWORDS
            for f in filters:

                if match(title, f):
                    send(f"""🛒 MATCH FOUND
🧠 {f}
🛍 {title[:100]}
🔗 {full_url}""")

                    sent += 1
                    seen.append(full_url)
                    break

        except:
            continue

    print("SENT:", sent)


# ---------------- MAIN ----------------
def main():

    print("🚀 VINTED FEED BOT START")

    seen = load_json(SEEN_FILE, [])

    # 🔥 MULTIPLE SEARCH INTENTS (AI STYLE)
    filters = [
        "seiko watch",
        "seiko automatic",
        "casio watch",
        "rolex watch",
        "jordan sneakers"
    ]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        scrape_feed(page, seen, filters)

        browser.close()

    save_json(SEEN_FILE, seen)

    print("DONE")


if __name__ == "__main__":
    main()