from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import os
import requests
import time
from datetime import datetime, date

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
            page.wait_for_selector("a[data-sentry-component='VipLink']", timeout=15000)
        except Exception as e:
            print("❌ Timeout ved indlæsning af biloversigt:", e)
            return

        html = page.content()
        soup = BeautifulSoup(html, "html.parser")
        cars = soup.select("a[data-sentry-component='VipLink']")
        print(f"🔍 Fundet {len(cars)} biler")

        for car in cars:
            link = car["href"]
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
            brand = brand_model.split(" ")[0] if brand_model else ""
            model = " ".join(brand_model.split(" ")[1:]) if brand_model else ""

            price_el = car_soup.select_one(".MuiTypography-h5")
            price = price_el.get_text(strip=True) if price_el else ""

            desc_el = car_soup.select_one(".description")
            description = desc_el.get_text(" ", strip=True) if desc_el else ""

            image_tags = car_soup.select("img")
            image_urls = [img["src"] for img in image_tags if img.has_attr("src") and "uploads" in img["src"]]
            images_combined = ", ".join(image_urls[:3])

            year = km = motor = listed_date = seller_type = ""
            days_listed = None

            for p in car_soup.select("p.MuiTypography-body1"):
                text = p.get_text(strip=True).lower()
                if "km" in text and "000" in text:
                    km = text
                elif "diesel" in text or "benzin" in text or "el" in text:
                    motor = text
                elif "/" in text and len(text) == 7:
                    year = text
                elif "oprettet" in text:
                    listed_raw = text.replace("oprettet", "").strip()
                    try:
                        listed_date_obj = datetime.strptime(listed_raw, "%d.%m.%Y")
                        listed_date = listed_date_obj.date().isoformat()
                        days_listed = (date.today() - listed_date_obj.date()).days
                    except:
                        listed_date = ""
                        days_listed = None
                elif "privat sælger" in text:
                    seller_type = "Privat"
                elif "forhandler" in text:
                    seller_type = "Forhandler"

            scraped_at = date.today().isoformat()

            data = {
                "id": car_id,
                "title": brand_model,
                "link": full_link,
                "price": price,
                "year": year,
                "km": km,
                "motor": motor,
                "brand": brand,
                "model": model,
                "equipment": "",
                "images": images_combined,
                "description": description,
                "category": "",
                "type": "",
                "weight": "",
                "width": "",
                "doors": "",
                "listed_date": listed_date,
                "days_listed": days_listed,
                "seller_type": seller_type,
                "scraped_at": scraped_at
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