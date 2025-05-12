from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import os
import requests
import time

print("✅ main_bilhandel.py er startet")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_API_KEY = os.getenv("SUPABASE_API_KEY")
TABLE_NAME = "bilhandel_cars"

print("SUPABASE_URL =", SUPABASE_URL)
print("SUPABASE_API_KEY is set =", bool(SUPABASE_API_KEY))

headers = {
    "apikey": SUPABASE_API_KEY,
    "Authorization": f"Bearer {SUPABASE_API_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

def extract_car_id(link):
    return link.rstrip("/").split("/")[-1]

def get_existing_ids():
    try:
        res = requests.get(f"{SUPABASE_URL}/rest/v1/{TABLE_NAME}?select=id", headers=headers)
        if res.status_code == 200:
            return {row['id'] for row in res.json()}
        return set()
    except Exception as e:
        print("❌ Kunne ikke hente eksisterende IDs:", e)
        return set()

def scrape_bilhandel():
    print("▶️ Kører scrape_bilhandel()")
    existing_ids = get_existing_ids()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page()

        print("🚗 Starter scraping af Bilhandel.dk...")

        try:
            page.goto("https://bilhandel.dk/s/alle-biler?sort=nyest&link=yes", timeout=30000)
        except Exception as e:
            print("❌ Fejl ved åbningsside:", e)
            return

        time.sleep(5)  # Vent på at JavaScript loader bilerne

        html = page.content()
        soup = BeautifulSoup(html, "html.parser")
        cars = soup.select("a[href^='/'][class*='listing']")
        print(f"🔍 Fundet {len(cars)} biler")

        if not cars:
            print("⚠️ Ingen biler fundet - tjek selector eller ventetid!")

        for car in cars:
            link = car.get("href")
            if not link:
                continue

            full_link = "https://bilhandel.dk" + link
            car_id = extract_car_id(full_link)

            if car_id in existing_ids:
                continue

            try:
                page.goto(full_link, timeout=30000, wait_until='domcontentloaded')
                time.sleep(2)
            except Exception as e:
                print(f"❌ Fejl ved goto på {full_link}: {e}")
                continue

            car_html = page.content()
            car_soup = BeautifulSoup(car_html, "html.parser")

            title_el = car_soup.select_one("h1")
            brand_model = title_el.get_text(strip=True) if title_el else ""

            price_el = car_soup.select_one(".price")
            price = price_el.get_text(strip=True) if price_el else ""

            specs = car_soup.select(".car-data li")
            year = km = motor = ""
            for spec in specs:
                txt = spec.get_text(strip=True).lower()
                if "årg" in txt:
                    year = txt
                elif "km" in txt:
                    km = txt
                elif "benzin" in txt or "diesel" in txt or "el" in txt:
                    motor = txt

            desc_el = car_soup.select_one(".description")
            description = desc_el.get_text(" ", strip=True) if desc_el else ""

            image_tags = car_soup.select("img")
            image_urls = [img["src"] for img in image_tags if img.has_attr("src") and "uploads" in img["src"]]
            images_combined = ", ".join(image_urls[:3])

            data = {
                "id": car_id,
                "title": brand_model,
                "link": full_link,
                "price": price,
                "year": year,
                "km": km,
                "motor": motor,
                "brand": brand_model.split(" ")[0],
                "model": " ".join(brand_model.split(" ")[1:]),
                "equipment": "",
                "images": images_combined,
                "description": description,
                "category": "",
                "type": "",
                "weight": "",
                "width": "",
                "doors": ""
            }

            try:
                response = requests.post(f"{SUPABASE_URL}/rest/v1/{TABLE_NAME}", json=data, headers=headers)
                if response.status_code in [200, 201]:
                    print(f"✅ Gemt: {brand_model} - {price}")
                else:
                    print(f"⚠️ Kunne ikke gemme {car_id}: {response.status_code}")
            except Exception as e:
                print(f"❌ Fejl ved post til Supabase: {e}")

if __name__ == "__main__":
    while True:
        print("🔁 Starter scraping...")
        scrape_bilhandel()
        print("⏳ Venter 10 min...")
        time.sleep(600)