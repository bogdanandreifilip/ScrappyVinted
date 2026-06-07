import requests
import os
import json
import time
from bs4 import BeautifulSoup

# ================= CONFIG =================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

HEADERS = {"User-Agent": "Mozilla/5.0"}

SEARCHES_FILE = "searches.json"
SEEN_FILE = "seen.json"

MAX_PAGES = 3
# ==========================================


# ================= STORAGE ==================
def load_json(file, default):
    if os.path.exists(file):
        try:
            with open(file, "r") as f:
                return json.load(f)
        except:
            return default
    return default


def save_json(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=2)


# ================= TELEGRAM ==================
def notify(text):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return

    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": text,
                "disable_web_page_preview": True
            },
            timeout=10
        )
    except:
        pass


def handle_commands():
    print("### TELEGRAM ACTIVE ###")

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
    r = requests.get(url, timeout=10)

    try:
        data = r.json()
    except:
        return

    searches = load_json(SEARCHES_FILE, [])

    for update in data.get("result", []):
        msg = update.get("message", {})
        text = msg.get("text", "")
        chat_id = msg.get("chat", {}).get("id")

        if str(chat_id) != str(TELEGRAM_CHAT_ID):
            continue

        # ---------- ADD ----------
        if text.startswith("/add"):
            parts = text.split()

            if len(parts) < 4:
                notify("❌ /add <name> <query...> <price>")
                continue

            name = parts[1]

            try:
                price = int(parts[-1])
            except:
                notify("❌ price must be number")
                continue

            query = " ".join(parts[2:-1])

            searches = [s for s in searches if s["name"] != name]
            searches.append({
                "name": name,
                "query": query,
                "price_to": price
            })

            save_json(SEARCHES_FILE, searches)
            notify(f"✅ Added: {name}")

        # ---------- LIST ----------
        elif text.startswith("/list"):
            if not searches:
                notify("⚠️ No searches")
            else:
                msg = "📋 SEARCHES:\n\n"
                for s in searches:
                    msg += f"{s['name']} | ≤ {s['price_to']}\n{s['query']}\n\n"
                notify(msg)

        # ---------- REMOVE ----------
        elif text.startswith("/remove"):
            name = text.replace("/remove", "").strip().lower()

            new_list = []
            removed = False

            for s in searches:
                if s["name"].lower() == name:
                    removed = True
                    continue
                new_list.append(s)

            save_json(SEARCHES_FILE, new_list)

            notify("🗑 Removed" if removed else "⚠️ Not found")


# ================= FILTER ==================
def is_good_item(title):
    title = title.lower()

    # must be watch brand
    brands = ["seiko", "citizen", "casio", "rolex", "omega"]
    if not any(b in title for b in brands):
        return False

    # block obvious non-watch items
    noise = ["tricou", "bluza", "geaca", "pantofi", "haina", "mobila"]
    if any(n in title for n in noise):
        return False

    return True


# ================= SCRAPER ==================
def scrape(search, seen):
    print(f"🔎 {search['name']}")

    sent = 0

    for page in range(1, MAX_PAGES + 1):

        url = (
            "https://www.olx.ro/oferte/q-"
            + search["query"].replace(" ", "-")
            + f"/?page={page}&search%5Bfilter_float_price%3Ato%5D={search['price_to']}"
        )

        print("URL:", url)

        r = requests.get(url, headers=HEADERS, timeout=20)
        soup = BeautifulSoup(r.text, "html.parser")

        # 🔥 ROBUST SELECTOR (IMPORTANT FIX)
        cards = soup.select("div[data-testid='l-card'], div[data-cy='l-card'], article")

        print(f"PAGE {page} FOUND:", len(cards))

        if not cards:
            break

        for card in cards:

            # link fallback
            a = card.find("a", href=True)
            if not a:
                continue

            href = a["href"]
            if not href.startswith("http"):
                href = "https://www.olx.ro" + href

            if href in seen:
                continue

            # title fallback (VERY IMPORTANT FIX)
            title = None

            for tag in ["h6", "h5", "h4", "h3"]:
                t = card.find(tag)
                if t:
                    title = t.get_text(strip=True)
                    break

            if not title:
                title = card.get_text(" ", strip=True)[:120]

            price_el = card.find("p")
            price = price_el.get_text(strip=True) if price_el else "?"

            if not title:
                continue

            if not is_good_item(title):
                continue

            notify(
                f"⌚ {search['name']}\n"
                f"{title}\n"
                f"💰 {price}\n"
                f"{href}"
            )

            seen.add(href)
            sent += 1

        time.sleep(2)

    print("SENT:", sent)


# ================= MAIN ==================
def main():
    print("🚀 OLX BOT START")

    handle_commands()

    searches = load_json(SEARCHES_FILE, [])
    if not searches:
        print("⚠️ No searches")
        return

    seen = set(load_json(SEEN_FILE, []))

    for s in searches:
        scrape(s, seen)

    save_json(SEEN_FILE, list(seen))

    print("DONE")


if __name__ == "__main__":
    main()