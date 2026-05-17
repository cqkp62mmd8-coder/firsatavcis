
import re
from html import escape
from difflib import SequenceMatcher

NOISE = [
    "#işbirliği",
    "fırsata git",
    "ürüne git",
    "stoklar eriyor",
    "google’da karşılaştır",
]

def normalize_price(raw):
    raw = raw.replace("₺","").replace("TL","").replace("tl","")
    raw = raw.replace(".","").replace(",",".").strip()
    try:
        return float(raw)
    except:
        return None

def confidence_score(title, price):
    score = 0.0
    if title and len(title) > 8:
        score += 0.5
    if price:
        score += 0.4
    return min(score, 1.0)

def similar(a,b):
    return SequenceMatcher(None,a,b).ratio()

def split_products(text):
    lines = [x.strip() for x in text.splitlines() if x.strip()]
    cleaned = []

    for line in lines:
        lower = line.lower()
        if any(n in lower for n in NOISE):
            continue
        cleaned.append(line)

    blocks = []
    current = []

    for line in cleaned:
        if line.startswith(("🔥","📦","👚","🔻","✅")) and current:
            blocks.append(current)
            current = [line]
        else:
            current.append(line)

    if current:
        blocks.append(current)

    unique = []
    for b in blocks:
        txt = " ".join(b)
        if not any(similar(txt, " ".join(x)) > 0.90 for x in unique):
            unique.append(b)

    return unique[:2]

def extract_products(text):
    blocks = split_products(text)
    products = []

    for block in blocks:
        joined = "\n".join(block)

        title = None
        for line in block:
            if len(line) > 10 and "http" not in line:
                title = line
                break

        prices = re.findall(r"(?:₺\s*)?[0-9\.,]+\s*(?:TL)?", joined)
        urls = re.findall(r"https?://\S+", joined)

        current_price = normalize_price(prices[0]) if prices else None

        confidence = confidence_score(title, current_price)

        if confidence < 0.5:
            continue

        products.append({
            "title": escape(title or "Fırsat"),
            "price": current_price,
            "url": urls[0] if urls else None,
            "confidence": confidence
        })

    return products[:2]
