import os
import asyncio
import re
import hashlib
import heapq

from telethon import TelegramClient, events
from telethon.sessions import StringSession

# ─────────────────────────────
# CONFIG
# ─────────────────────────────
API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "")
SESSION_STRING = os.environ.get("SESSION_STRING", "")
CHANNEL_ID = os.environ.get("CHANNEL_ID", "")
MIN_INDIRIM = int(os.environ.get("MIN_INDIRIM", "40"))

client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

# ─────────────────────────────
# STATE
# ─────────────────────────────
seen = set()
queue = []

# ─────────────────────────────
# UTIL
# ─────────────────────────────
def extract_discount(text):
    vals = re.findall(r"%\s*(\d+)", (text or "").lower())
    return max([int(v) for v in vals], default=0)


def extract_price(text):
    vals = re.findall(r"(\d+[.,]?\d*)\s*tl", (text or "").lower())
    return vals[0] if vals else None


def extract_link(text):
    links = re.findall(r"https?://\S+", text or "")
    return links[0] if links else None


def extract_title(text):
    for line in (text or "").split("\n"):
        if len(line) > 10 and "http" not in line:
            return line[:80]
    return "Fırsat"


def store_detect(text):
    t = (text or "").lower()
    if "amazon" in t: return "Amazon TR"
    if "hepsiburada" in t: return "Hepsiburada"
    if "trendyol" in t: return "Trendyol"
    return "E-Ticaret"


# ─────────────────────────────
# CORE INTELLIGENCE
# ─────────────────────────────
def trust_score(text):
    t = (text or "").lower()
    score = 5
    if "amazon" in t: score += 3
    if "hepsiburada" in t: score += 3
    if "trendyol" in t: score += 2
    return max(1, min(score, 10))


def deal_score(discount, trust, has_price, has_link):
    score = 0
    score += min(discount * 0.06, 6)
    score += trust * 0.7
    if has_price: score += 1.2
    if has_link: score += 1.5
    return round(min(score, 10), 2)


def viral_score(discount):
    if discount >= 80: return 3
    if discount >= 60: return 2
    if discount >= 40: return 1
    return 0


def final_score(base, viral):
    return round(base + viral, 2)


# ─────────────────────────────
# FILTER
# ─────────────────────────────
def is_valid(text, discount, link):
    blacklist = ["çorap", "kalem", "sticker"]

    if discount < MIN_INDIRIM:
        return False
    if not link:
        return False
    if any(b in (text or "").lower() for b in blacklist):
        return False

    return True


# ─────────────────────────────
# DEDUPE
# ─────────────────────────────
def fingerprint(text, price):
    return hashlib.md5((str(text) + str(price)).lower().encode()).hexdigest()


# ─────────────────────────────
# FORMAT
# ─────────────────────────────
def format_message(title, price, discount, store, score, link):
    return f"""
🔥 <b>{title}</b>

💰 {price or 'Bilinmiyor'} TL
📉 %{discount} İNDİRİM
⭐ Skor: {score}/10

🏪 {store}

🔗 <a href="{link}">Fırsatı Gör</a>
"""


# ─────────────────────────────
# QUEUE
# ─────────────────────────────
def push(score, payload):
    heapq.heappush(queue, (-score, payload))


async def worker():
    while True:
        if queue:
            score, message = heapq.heappop(queue)[1]
            delay = 5 if score >= 8 else 60 if score >= 6 else 180
            await asyncio.sleep(delay)
            await client.send_message(CHANNEL_ID, message, parse_mode="html")
        await asyncio.sleep(2)


# ─────────────────────────────
# HANDLER
# ─────────────────────────────
@client.on(events.NewMessage)
async def handler(event):
    text = event.raw_text or ""

    discount = extract_discount(text)
    link = extract_link(text)
    price = extract_price(text)

    if not is_valid(text, discount, link):
        return

    fp = fingerprint(text, price)
    if fp in seen:
        return
    seen.add(fp)

    trust = trust_score(text)
    base = deal_score(discount, trust, bool(price), bool(link))
    viral = viral_score(discount)
    score = final_score(base, viral)

    if score < 5:
        return

    msg = format_message(
        extract_title(text),
        price,
        discount,
        store_detect(text),
        score,
        link
    )

    push(score, (score, msg))


# ─────────────────────────────
# START
# ─────────────────────────────
async def main():
    await client.start()
    asyncio.create_task(worker())
    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
