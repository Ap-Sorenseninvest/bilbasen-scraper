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
            page.wait_for_selector(".MuiGrid-root.MuiGrid-container.css-1d3bbye", timeout=15000)
        except Exception as e:
            print("❌ Timeout eller fejl ved indlæsning af oversigt:", e)
            return

        html = page.content()
        soup = BeautifulSoup(html, "html.parser")
        cars = soup.select("a[data-sentry-element='Link']")
        print(f"🔍 Fundet {len(cars)} biler")

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
            soup = BeautifulSoup(car_html, "html.parser")

            def get_text_by_tooltip(title):
                el = soup.find(attrs={"tooltoptitle": title})
                return el.get_text(strip=True) if el else ""

            brand_model_el = soup.select_one("h1.MuiTypography-root.MuiTypography-body1.css-1azqjhe")
            price_el = soup.select_one(".MuiTypography-root.MuiTypography-body1.css-12s5272")
            motor_el = soup.select_one(".MuiTypography-root.MuiTypography-body1.css-1b1eawi")
            description_el = soup.select_one(".MuiBox-root.css-leu9o3")
            specs_els = soup.select(".MuiGrid-root.MuiGrid-item.MuiGrid-grid-xs-6.css-1s50f5r")
            specs = [el.get_text(strip=True) for el in specs_els]
            equipment_els = soup.select(".MuiGrid-root.MuiGrid-item.MuiGrid-grid-xs-12.css-15j76c0")
            equipment = ", ".join(el.get_text(strip=True) for el in equipment_els)
            image_els = soup.select(".image-gallery-swipe img")
            images = ", ".join(img["src"] for img in image_els[:3] if img.has_attr("src"))

            listed_el = soup.find(string=lambda t: "Oprettet" in t)
            listed_raw = listed_el.replace("Oprettet", "").strip() if listed_el else ""
            try:
                listed_date_obj = datetime.strptime(listed_raw, "%d.%m.%Y")
                listed_date = listed_date_obj.date().isoformat()
                days_listed = (date.today() - listed_date_obj.date()).days
            except:
                listed_date = ""
                days_listed = None

            data = {
                "id": car_id,
                "title": brand_model_el.get_text(strip=True) if brand_model_el else "",
                "link": full_link,
                "price": price_el.get_text(strip=True) if price_el else "",
                "year": get_text_by_tooltip("Første registrering"),
                "km": get_text_by_tooltip("Kørte km"),
                "motor": motor_el.get_text(strip=True) if motor_el else "",
                "brand": brand_model_el.get_text(strip=True).split(" ")[0] if brand_model_el else "",
                "model": " ".join(brand_model_el.get_text(strip=True).split(" ")[1:]) if brand_model_el else "",
                "equipment": equipment,
                "images": images,
                "description": description_el.get_text(strip=True) if description_el else "",
                "category": "",
                "type": "",
                "weight": "",
                "width": "",
                "doors": "",
                "listed_date": listed_date,
                "days_listed": days_listed,
                "seller_type": "Privat" if "Privat sælger" in car_html else ("Forhandler" if "Forhandler" in car_html else ""),
                "horsepower": get_text_by_tooltip("Ydelse"),
                "transmission": get_text_by_tooltip("Gear"),
                "location": get_text_by_tooltip("By"),
                "scraped_at": date.today().isoformat()
            }

            try:
                response = requests.post(f"{SUPABASE_URL}/rest/v1/{TABLE_NAME}", json=data, headers=headers)
                if response.status_code in [200, 201]:
                    print(f"✅ Gemt: {data['title']} - {data['price']}")
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