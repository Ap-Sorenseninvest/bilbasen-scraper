from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import os
import requests
import time
from datetime import datetime

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_API_KEY = os.getenv("SUPABASE_API_KEY")
TABLE_NAME = "bilhandel_cars"

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

        try:
            page.wait_for_selector(".MuiGrid-root.MuiGrid-container.css-1d3bbye", timeout=15000)
        except Exception as e:
            print("❌ Timeout ved indlæsning af biloversigt:", e)
            return

        html = page.content()
        soup = BeautifulSoup(html, "html.parser")
        cars = soup.select(".MuiGrid-root.MuiGrid-container.css-1d3bbye")
        print(f"🔍 Fundet {len(cars)} biler")

        for car in cars:
            link_el = car.select_one('[data-sentry-element="Link"]')
            if not link_el:
                continue

            link = link_el["href"]
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

            brand_model = car_soup.select_one("h1.MuiTypography-body1.css-1azqjhe")
            brand_model = brand_model.get_text(strip=True) if brand_model else ""

            price = car_soup.select_one("h5.MuiTypography-body1.css-12s5272")
            price = price.get_text(strip=True) if price else ""

            specs = car_soup.select('[tooltoptitle]')
            year = km = motor = hp = gear = ""
            for spec in specs:
                title = spec.get("tooltoptitle", "").lower()
                value = spec.get_text(strip=True)
                if "registrering" in title:
                    year = value
                elif "km" in title:
                    km = value
                elif "drivmiddel" in title:
                    motor = value
                elif "ydelse" in title:
                    hp = value
                elif "gear" in title:
                    gear = value

            description = car_soup.select_one(".MuiBox-root.css-leu9o3")
            description = description.get_text(" ", strip=True) if description else ""

            image_tags = car_soup.select(".image-gallery-swipe img")
            image_urls = [img["src"] for img in image_tags if img.has_attr("src")]
            images_combined = ", ".join(image_urls[:3])

            scraped_at = datetime.today().date().isoformat()

            data = {
                "id": car_id,
                "title": brand_model,
                "link": full_link,
                "price": price,
                "year": year,
                "km": km,
                "motor": motor,
                "brand": brand_model.split(" ")[0] if brand_model else "",
                "model": " ".join(brand_model.split(" ")[1:]) if brand_model else "",
                "equipment": "",
                "images": images_combined,
                "description": description,
                "category": "",
                "type": "",
                "weight": "",
                "width": "",
                "doors": "",
                "listed_date": "",           # ikke brugt
                "days_listed": None,         # ikke brugt
                "seller_type": "",
                "horsepower": hp,
                "transmission": gear,
                "location": "",
                "scraped_at": scraped_at     # her får du altid dagens dato
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