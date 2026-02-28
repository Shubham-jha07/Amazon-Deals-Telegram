import requests
from bs4 import BeautifulSoup
import time
import json
import os
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from urllib.parse import unquote
import re

TOKEN = "8400618658:AAE5Ba8tezzydLQJhD8Gc_TXQWlsR_yjBL4"
CHAT_ID = "-1003615865605"
AMAZON_TAG = "mahadeals1010-21"

URL = "https://indiadesire.com/lootdeals"
DB_FILE = "posted_deals.json"

CATEGORIES = {
    "Beauty & Skincare": [
        "face", "cream", "serum", "makeup", "shampoo", "lotion", "perfume", "deo",
        "sunscreen", "lipstick", "foundation", "moisturizer", "conditioner", "scrub", 
        "mask", "eyeliner", "kajal", "hair oil", "facewash"
    ],
    "Fashion & Footwear": [
        "t-shirt", "shirt", "jeans", "shoe", "sneaker", "watch", "sunglasses",
        "kurta", "kurti", "dress", "jacket", "hoodie", "saree", "bag", "wallet", 
        "belt", "trousers", "sandal", "flip flop", "heels", "socks"
    ],
    "Electronics & Tech": [
        "earbuds", "speaker", "charger", "power bank", "smartwatch", "tablet", "laptop",
        "cable", "headphone", "mouse", "keyboard", "ssd", "hard drive", "monitor", 
        "gaming", "cpu", "pendrive", "adapter", "router", "webcam"
    ],
    "Home & Kitchen": [
        "bottle", "container", "box", "kitchen", "mop", "kettle", "mixer", "grinder",
        "hanger", "storage", "flask", "cookware", "bedsheet", "curtain", "lamp", 
        "decor", "towel", "pillow", "cushion", "vessel", "pan", "tawa"
    ],
    "Health & Fitness": [
        "protein", "vitamin", "capsule", "tablet", "massager", "weighing scale",
        "fitness", "supplement", "omega", "creatine", "yoga", "dumbbell", "bp monitor",
        "thermometer", "multivitamin", "shaker"
    ],
    "Personal Care & Grooming": [
        "trimmer", "shaver", "dryer", "toothbrush", "epilator", "straightener", "razor",
        "blade", "sanitary", "beard oil", "hair wax", "comb"
    ],
    "Home Decor & Lighting": [
        "wall art", "clock", "vase", "diya", "fairylight", "led strip", "painting",
        "sticker", "showpiece", "artificial plant", "candle"
    ],
    "Office & Stationery": [
        "pen", "notebook", "diary", "desk", "chair", "stapler", "marker", "calculator",
        "file", "folder", "highlighter", "pencil"
    ],
    "Baby & Kids": [
        "diaper", "baby", "feeding", "wipes", "powder", "toy", "puzzle", "stroller",
        "tricycle", "soft toy", "board game", "walker"
    ],
    "Pet Care": [
        "dog food", "cat food", "pedigree", "whiskas", "leash", "pet shampoo", 
        "aquarium", "bird food", "pet bed"
    ],
    "Automotive Accessories": [
        "car", "bike", "helmet", "tyre", "cleaner", "vacuum", "polish", "dashcam",
        "car perfume", "microfiber", "seat cover"
    ],
    "Groceries & Pantry": [
        "tea", "coffee", "biscuit", "snack", "chocolate", "oil", "ghee", "dry fruit",
        "almond", "cashew", "maggie", "pasta", "honey"
    ]
}

def detect_category(title):
    title_lower = title.lower()

    for category, keywords in CATEGORIES.items():
        for word in keywords:
            if word in title_lower:
                return category

    return "Other"

def shorten_title(title, max_words=5):
    """
    Shortens long Amazon titles to improve readability.
    """
    words = title.split()
    return " ".join(words[:max_words])

# =========================
# TELEGRAM POST FUNCTION
# =========================
def send_to_telegram(message):
    api_url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID, 
        "text": message,
        "parse_mode": "HTML" # Enables bold/links
    }
    requests.post(api_url, data=payload)

# =========================
# LOAD / SAVE POSTED DEALS
# =========================
def load_posted():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            return set(json.load(f))
    return set()

def save_posted(posted):
    with open(DB_FILE, "w") as f:
        json.dump(list(posted), f)

# =========================
# ADD AMAZON AFFILIATE TAG
# =========================
def add_amazon_affiliate(url):
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    query["tag"] = AMAZON_TAG
    new_query = urlencode(query, doseq=True)
    return urlunparse(parsed._replace(query=new_query))

# =========================
# EXTRACT REAL LINK FROM REDIRECT
# =========================
def extract_real_link(url):
    if "redirect=" in url:
        parsed = parse_qs(urlparse(url).query)
        real = parsed.get("redirect", [url])[0]
        return unquote(real)   # 🔥 decode encoded URL
    return url

def get_amazon_details(url):
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept-Language": "en-IN,en;q=0.9"
    }

    try:
        r = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")

        # Title
        title_tag = soup.find(id="productTitle")
        title = title_tag.get_text(strip=True) if title_tag else "Amazon Deal"

        # Current price
        price_tag = soup.select_one(".a-price-whole")
        price = price_tag.get_text(strip=True) if price_tag else ""

        # MRP
        mrp_tag = soup.select_one(".a-text-price .a-offscreen")
        mrp = mrp_tag.get_text(strip=True) if mrp_tag else ""

        # Discount %
        discount = ""
        discount_tag = soup.find(string=re.compile("% off"))
        if discount_tag:
            discount = discount_tag.strip()

        # Lightning deal detection
        lightning = False
        if soup.find(string=re.compile("Lightning Deal", re.I)):
            lightning = True

        return {
            "title": title,
            "price": price,
            "mrp": mrp,
            "discount": discount,
            "lightning": lightning
        }

    except Exception as e:
        print("Amazon scrape error:", e)
        return None

# =========================
# FETCH AMAZON DEALS
# =========================
def fetch_deals():
    headers = {"User-Agent": "Mozilla/5.0"}

    response = requests.get(URL, headers=headers, timeout=15)
    soup = BeautifulSoup(response.text, "html.parser")

    deals = []
    seen = set()

    links = soup.select(".content-logo a")

    for a in links:
        href = a.get("href")
        if not href:
            continue

        # 👉 keep only Amazon deals
        if "store=amazon" not in href.lower():
            continue

        # 👉 extract ASIN from redirect URL
        parsed = parse_qs(urlparse(href).query)
        asin = parsed.get("redirectpid1", [None])[0]

        if not asin:
            continue

        # 👉 build real Amazon product link
        real_link = f"https://www.amazon.in/dp/{asin}"

        # 👉 add affiliate tag
        real_link = add_amazon_affiliate(real_link)

        # 👉 remove duplicates
        if real_link in seen:
            continue

        seen.add(real_link)

        title = a.get_text(strip=True)
        if not title:
            title = "🔥 Amazon Loot Deal"

        deals.append((title, real_link))

    print("Amazon deals found:", len(deals))
    return deals

# =========================
# MAIN BOT LOGIC
# =========================
def main():
    posted = load_posted()
    deals = fetch_deals()

    grouped = {}
    new_found = 0

    for title, link in deals:

        # skip already posted
        if link in posted:
            continue

        details = get_amazon_details(link)
        if not details:
            continue

        title = details["title"]
        price = details["price"]
        mrp = details["mrp"]
        discount = details["discount"]

        short_title = shorten_title(title)

        price_line = f"₹{price}" if price else ""
        if mrp:
            price_line += f" (₹{mrp})"
        if discount:
            price_line += f" • {discount}"

        line = f"🔥 {short_title} — {price_line}\n🛒 {link}"

        category = detect_category(title)

        if category not in grouped:
            grouped[category] = []

        grouped[category].append(line)

        posted.add(link)
        new_found += 1

        # small delay to avoid Amazon blocking
        time.sleep(1.5)

    # ✅ send grouped messages
    for category, items in grouped.items():

        if not items:
            continue

        message = f"🛍 {category.upper()} DEALS\n\n"
        message += "\n".join(items)

        send_to_telegram(message)
        time.sleep(2)

    save_posted(posted)

    print(f"New deals sent: {new_found}")

if __name__ == "__main__":
    main()