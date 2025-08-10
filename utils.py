# utils.py
import httpx
from bs4 import BeautifulSoup
import feedparser
import re
import json
from typing import List, Dict, Optional

# --- Utils ---
def normalize_language(lang: str) -> str:
    if not lang:
        return "en"
    lang = lang.lower()
    if lang.startswith("hi"):
        return "hi"
    if lang.startswith("en"):
        return "en"
    return "en"

# Load purchasingpower.json
with open("purchasingpower.json", "r") as f:
    _PPP = json.load(f).get("cities", [])

def find_cities_in_ppp(query: str, max_results: int = 2):
    q = query.lower()
    matches = []
    for c in _PPP:
        name = c["city"].lower()
        words = re.findall(r"[a-zA-Z]+", q)
        for w in words:
            if w in name and c not in matches:
                matches.append(c)
                break
        if len(matches) >= max_results:
            break
    return matches

async def fetch_gold_price(city: str = None) -> Optional[Dict[str, str]]:
    base_url = "https://www.goodreturns.in/gold-rates/"
    url = base_url
    if city:
        city_slug = city.lower().replace(" ", "")
        url = f"{base_url}{city_slug}.html"

    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(url, headers={"User-Agent": "GullakAI/1.0"})
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        prices = {}
        # Try to find span with ids 24K-price, 22K-price, 18K-price
        for karat in ["24K", "22K", "18K"]:
            span = soup.find("span", id=f"{karat}-price")
            if span and span.text.strip():
                prices[f"{karat}_price"] = span.text.strip()

        if prices:
            return prices

        # Fallback: extract main content paragraph
        fallback_p = soup.select_one("#gr_top_intro_content > div > p:nth-child(1)")
        if fallback_p:
            return {"raw": fallback_p.get_text(strip=True)}

        # As a last resort, return a snippet of page text
        main = soup.find("div", {"class": "gold-rates-table"}) or soup
        text = main.get_text(separator=" ").strip()[:400]
        return {"raw": text}

    return None

async def fetch_financial_news(limit: int = 5) -> List[Dict[str,str]]:
    url = "https://news.google.com/rss/search?q=finance+india&hl=en-IN&gl=IN&ceid=IN:en"
    feed = feedparser.parse(url)
    items = []
    for e in feed.entries[:limit]:
        items.append({
            "title": e.get("title"),
            "link": e.get("link"),
            "published": e.get("published"),
            "summary": e.get("summary", "")
        })
    return items

def simple_ppp_compare(city_data_list):
    if not city_data_list:
        return "No city data available."
    if len(city_data_list) == 1:
        c = city_data_list[0]
        return f"{c['city']}: Local Purchasing Power Index = {c['local_purchasing_power_index']}"
    c1, c2 = city_data_list[0], city_data_list[1]
    p1, p2 = c1['local_purchasing_power_index'], c2['local_purchasing_power_index']
    if p1 == p2:
        return f"{c1['city']} and {c2['city']} have similar purchasing power ({p1})."
    if p1 > p2:
        diff = p1 - p2
        return f"{c1['city']} has higher purchasing power ({p1}) than {c2['city']} ({p2}) by {diff:.1f} points."
    else:
        diff = p2 - p1
        return f"{c2['city']} has higher purchasing power ({p2}) than {c1['city']} ({p1}) by {diff:.1f} points."
