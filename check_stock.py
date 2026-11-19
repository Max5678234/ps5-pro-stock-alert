"""PS5 Pro stock checker.

Checks each retailer, compares with the last saved status in state.json,
and sends a Telegram alert only when a retailer goes from out of stock
to in stock, sold by the retailer itself, at or under the price limit.

Run:  python3 check_stock.py           (normal check)
      python3 check_stock.py --dry-run (check and print, no Telegram, no saving)
"""

import json
import re
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup

import notify

STATE_FILE = Path(__file__).parent / "state.json"
PRICE_LIMIT = {"GBP": 800.00, "EUR": 910.00}
SYMBOL = {"GBP": "£", "EUR": "€"}
# Anything cheaper than this can't be a real PS5 Pro console (it's an accessory price
# picked up by mistake), so we ignore it.
MIN_REAL_PRICE = {"GBP": 400.00, "EUR": 450.00}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept-Language": "en-GB,en;q=0.9",
}


class CheckFailed(Exception):
    """The page couldn't be read reliably (blocked, changed, timed out)."""


def parse_price(text):
    """'£1,489.99' / '€899,99' / '899.99' -> 899.99"""
    if not text:
        return None
    digits = re.sub(r"[^\d.,]", "", text)
    if not digits:
        return None
    # European style "1.234,56" or "899,99"
    if "," in digits and (digits.rfind(",") > digits.rfind(".")):
        digits = digits.replace(".", "").replace(",", ".")
    else:
        digits = digits.replace(",", "")
    try:
        return float(digits)
    except ValueError:
        return None


# ---------------------------------------------------------------- PlayStation Direct

def check_playstation_direct(url):
    r = requests.get(url, headers=HEADERS, timeout=30)
    if r.status_code != 200:
        raise CheckFailed(f"HTTP {r.status_code}")
    html = r.text

    # Make sure we're on the PS Direct listing of the standard PS5 Pro console.
    m = re.search(r'"invariantName":"([^"]+)"', html)
    name = m.group(1) if m else ""
    if "PS5PROCHASASIRSE" not in html or "Pro Console" not in name:
        raise CheckFailed("PS5 Pro product data not found on page")

    m = re.search(r'"offers":\{"@type":"Offer","price":"([\d.]+)","priceCurrency":"(\w+)",'
                  r'"availability":"https://schema.org/(\w+)"', html)
    if not m:
        raise CheckFailed("price/availability data not found")
    price, currency, availability = float(m.group(1)), m.group(2), m.group(3)

    # The buy button: "UNAVAILABLE" when sold out, "ADD_TO_CART" etc. when buyable.
    cta = re.search(r'"activeCtaId":"([A-Z_]+):', html)
    cta_type = cta.group(1) if cta else ""

    in_stock = availability == "InStock" or "ADD_TO_CART" in cta_type or "BUY" in cta_type
    return {
        "in_stock": in_stock,
        "price": price,
        "currency": currency,
        "seller": "PlayStation Direct",  # this product ID is Sony's own PS Direct listing
        "sold_by_retailer": True,
        "detail": f"availability={availability}, button={cta_type or 'none'}",
    }


# ---------------------------------------------------------------- Amazon

def check_amazon(url, currency):
    domain = "amazon.co.uk" if "amazon.co.uk" in url else "amazon.de"
    session = requests.Session()
    session.headers.update(HEADERS)
    session.cookies.set("i18n-prefs", currency, domain="." + domain)  # show prices in £/€
    r = session.get(url, timeout=30)
    if r.status_code != 200:
        raise CheckFailed(f"HTTP {r.status_code}")
    if "captcha" in r.text.lower() and "productTitle" not in r.text:
        raise CheckFailed("Amazon showed a CAPTCHA (blocked this time)")

    soup = BeautifulSoup(r.text, "html.parser")
    title_el = soup.find(id="productTitle")
    if not title_el:
        raise CheckFailed("product title not found")
    title = title_el.get_text(" ", strip=True)
    if not re.search(r"(playstation|ps)\s*®?\s*5\s*pro", title, re.I):
        raise CheckFailed(f"unexpected product: {title[:60]}")

    has_buy_button = soup.find(id="add-to-cart-button") is not None

    price = None
    price_el = soup.select_one("#corePrice_feature_div .a-offscreen")
    if price_el:
        price = parse_price(price_el.get_text())

    seller = ""
    seller_el = (soup.select_one("#merchantInfoFeature_feature_div .offer-display-feature-text-message")
                 or soup.select_one("#merchantInfoFeature_feature_div .offer-display-feature-text"))
    if seller_el:
        seller = seller_el.get_text(" ", strip=True)
    else:
        old = soup.find(id="merchant-info")  # older page layout
        if old:
            seller = old.get_text(" ", strip=True)
    sold_by_amazon = bool(re.match(r"^amazon\b", seller, re.I)) or bool(
        re.search(r"(dispatched from and sold by|versand und verkauf durch)\s+amazon", seller, re.I))

    in_stock = has_buy_button and price is not None
    return {
        "in_stock": in_stock,
        "price": price,
        "currency": currency,
        "seller": seller or "unknown",
        "sold_by_retailer": sold_by_amazon,
        "detail": title[:60],
    }


# ---------------------------------------------------------------- Retailer list
# Dropped (they block automated checks): Argos, Currys, Game, Smyths,
# MediaMarkt, Saturn, Otto. See README.md.

RETAILERS = [
    {
        "id": "psdirect_uk",
        "name": "PlayStation Direct UK",
        "url": "https://direct.playstation.com/en-gb/buy-consoles/playstation5-pro-console-2-tb",
        "check": lambda url: check_playstation_direct(url),
    },
    {
        "id": "psdirect_de",
        "name": "PlayStation Direct DE",
        "url": "https://direct.playstation.com/de-de/buy-consoles/playstation5-pro-console-2-tb",
        "check": lambda url: check_playstation_direct(url),
    },
    {
        "id": "amazon_uk_cfi7021",
        "name": "Amazon UK",
        "url": "https://www.amazon.co.uk/dp/B0DJH2NS6R",
        "check": lambda url: check_amazon(url, "GBP"),
    },
    {
        "id": "amazon_uk_2025",
        "name": "Amazon UK",
        "url": "https://www.amazon.co.uk/dp/B0FR94FV8J",
        "check": lambda url: check_amazon(url, "GBP"),
    },
    {
        "id": "amazon_de_cfi7021",
        "name": "Amazon DE",
        "url": "https://www.amazon.de/dp/B0DHSV68YZ",
        "check": lambda url: check_amazon(url, "EUR"),
    },
    {
        "id": "amazon_de_cfi7121",
        "name": "Amazon DE",
        "url": "https://www.amazon.de/dp/B0FRYBZR91",
        "check": lambda url: check_amazon(url, "EUR"),
    },
]


# ---------------------------------------------------------------- Main logic

def is_alertable(result):
    """In stock AND sold by the retailer itself AND at/under the price limit."""
    if not result["in_stock"] or not result["sold_by_retailer"]:
        return False
    price, cur = result["price"], result["currency"]
    if price is None or cur not in PRICE_LIMIT:
        return False
    return MIN_REAL_PRICE[cur] <= price <= PRICE_LIMIT[cur]


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}


def main():
    dry_run = "--dry-run" in sys.argv
    only = [a for a in sys.argv[1:] if not a.startswith("--")]
    state = load_state()

    for shop in RETAILERS:
        if only and shop["id"] not in only:
            continue
        try:
            result = shop["check"](shop["url"])
        except (CheckFailed, requests.RequestException) as e:
            # Can't read it this time: keep the old status so we don't send false alerts.
            print(f"[SKIP] {shop['name']} ({shop['id']}): {e}")
            continue

        alertable = is_alertable(result)
        was_alertable = state.get(shop["id"], {}).get("alertable", False)
        price_txt = (f"{SYMBOL.get(result['currency'], '')}{result['price']:.2f}"
                     if result["price"] is not None else "no price")
        print(f"[{'IN ' if result['in_stock'] else 'OUT'}] {shop['name']} ({shop['id']}): "
              f"{price_txt}, seller: {result['seller']}, alert-worthy: {alertable} "
              f"[{result['detail']}]")

        if alertable and not was_alertable:
            message = (f"🎮 <b>PS5 Pro in stock!</b>\n"
                       f"<b>{shop['name']}</b>\n"
                       f"Price: {price_txt}\n"
                       f"{shop['url']}")
            if dry_run:
                print("   -> would send alert (dry run)")
            else:
                notify.send_message(message)
                print("   -> alert sent")

        # Only store what decides alerts, so the file only changes when stock changes.
        state[shop["id"]] = {"alertable": alertable, "in_stock": result["in_stock"]}

    if not dry_run:
        STATE_FILE.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
