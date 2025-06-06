from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import os
import requests
import time
from datetime import datetime

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_API_KEY = os.getenv("SUPABASE_API_KEY")
TABLE_NAME = "bilbasen_cars"

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

def scrape_bilbasen():
    existing_ids = get_existing_ids()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage"])
        page = browser.new_page()

        print("🚗 Starter scraping...")

        try:
            page.goto("https://www.bilbasen.dk/brugt/bil?includeengroscvr=true&includeleasing=false&sortby=date&sortorder=desc", timeout=30000)
        except Exception as e:
            print("❌ Fejl ved åbningsside:", e)
            return

        try:
            page.click("button:has-text('Accepter alle')", timeout=3000)
        except:
            pass

        try:
            page.wait_for_selector("section.srp_results__2UEV_", timeout=15000)
        except Exception as e:
            print("❌ Timeout på oversigtsside:", e)
            return

        html = page.content()
        soup = BeautifulSoup(html, "html.parser")
        cars = soup.select("article.Listing_listing__XwaYe")
        print(f"🔍 Fundet {len(cars)} biler")

        for car in cars:
            link_el = car.select_one("a.Listing_link__6Z504")
            if not link_el:
                continue

            link = link_el["href"]
            full_link = "https://www.bilbasen.dk" + link if not link.startswith("http") else link
            car_id = extract_car_id(full_link)

            if car_id in existing_ids:
                continue

            # Prøv 2 gange at åbne bilen
            success = False
            for attempt in range(2):
                try:
                    page.goto(full_link, timeout=30000, wait_until="domcontentloaded")
                    time.sleep(2)
                    success = True
                    break
                except Exception as e:
                    print(f"⚠️ Goto-fejl på forsøg {attempt+1}/2: {full_link} - {e}")
            if not success:
                continue

            try:
                page.wait_for_selector("main.bas-MuiVipPageComponent-main", timeout=20000)
            except:
                print(f"❌ Timeout på bilside: {full_link}")
                continue

            car_html = page.content()
            car_soup = BeautifulSoup(car_html, "html.parser")

            title_el = car_soup.select_one("h1.bas-MuiCarHeaderComponent-title")
            brand_model = title_el.get_text(strip=True) if title_el else ""
            brand = brand_model.split(" ")[0] if brand_model else ""
            model = " ".join(brand_model.split(" ")[1:]) if brand_model else ""

            price_el = car_soup.select_one('span.bas-MuiCarPriceComponent-value[data-e2e="car-retail-price"]')
            price = price_el.get_text(strip=True) if price_el else ""

            desc_el = car_soup.select_one("div[aria-label='beskrivelse'] .bas-MuiAdDescriptionComponent-descriptionText")
            description = desc_el.get_text(" ", strip=True) if desc_el else ""

            image_tags = car_soup.select("img.bas-MuiGalleryImageComponent-image")
            image_urls = [img["src"] for img in image_tags if img.has_attr("src")]
            images_combined = ", ".join(image_urls[:3])

            details_rows = car_soup.select("div[aria-label='Detaljer'] tr")
            details = {row.select_one("th").get_text(strip=True): row.select_one("td").get_text(strip=True) for row in details_rows if row.select_one("th") and row.select_one("td")}
            year = details.get("Modelår", "")
            km = details.get("Kilometertal", "")
            motor = details.get("Drivmiddel", "")

            model_info_rows = car_soup.select("div[aria-label='Generelle modeloplysninger*'] tr")
            model_info = {row.select_one("th").get_text(strip=True): row.select_one("td").get_text(strip=True) for row in model_info_rows if row.select_one("th") and row.select_one("td")}

            equipment_rows = car_soup.select("div[aria-label='Udstyr og tilbehør'] tr")
            equipment_items = []
            for row in equipment_rows:
                th = row.select_one("th[data-e2e='car-equipment-item']")
                td = row.select_one("td[data-e2e='car-equipment-item']")
                if th:
                    equipment_items.append(th.get_text(strip=True))
                if td:
                    equipment_items.append(td.get_text(strip=True))
            equipment = ", ".join(equipment_items)

            listed_el = car_soup.find(string=lambda t: "Oprettet" in t)
            listed_raw = listed_el.replace("Oprettet", "").strip() if listed_el else ""
            try:
                listed_date_obj = datetime.strptime(listed_raw, "%d.%m.%Y")
                listed_date = listed_date_obj.date().isoformat()
                days_listed = (datetime.today().date() - listed_date_obj.date()).days
            except:
                listed_date = ""
                days_listed = None

            horsepower = next((val for key, val in details.items() if "Ydelse" in key or "Hk" in key), "")
            transmission = next((val for key, val in details.items() if "Gear" in key), "")
            location = details.get("By", "")
            seller_type = "Privat" if "Privat sælger" in car_html else "Forhandler" if "Forhandler" in car_html else ""

            scraped_at = datetime.today().date().isoformat()

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
                "equipment": equipment,
                "images": images_combined,
                "description": description,
                "category": model_info.get("Kategori", ""),
                "type": model_info.get("Type", ""),
                "weight": model_info.get("Vægt", ""),
                "width": model_info.get("Bredde", ""),
                "doors": model_info.get("Døre", ""),
                "listed_date": listed_date,
                "days_listed": days_listed,
                "seller_type": seller_type,
                "horsepower": horsepower,
                "transmission": transmission,
                "location": location,
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
        scrape_bilbasen()
        print("⏳ Venter 10 min...")
        time.sleep(600)