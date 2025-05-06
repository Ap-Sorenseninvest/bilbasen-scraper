from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import os
import requests
from flask import Flask
from threading import Thread

app = Flask(__name__)

# 🔐 Supabase credentials fra env
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_API_KEY = os.getenv("SUPABASE_API_KEY")
TABLE_NAME = "bilbasen_cars"

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
        print("⚠️ Fejl ved hentning af eksisterende IDs:", res.status_code, res.text)
    except Exception as e:
        print("❌ Undtagelse i get_existing_ids:", e)
    return set()

def scrape_bilbasen():
    print("🚀 Starter scraper...")
    existing_ids = get_existing_ids()
    print(f"📋 Hentet {len(existing_ids)} eksisterende IDs")

    with sync_playwright() as p:
        print("✅ Playwright startet")
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        print("🌍 Går til Bilbasen oversigt...")
        page.goto("https://www.bilbasen.dk/brugt/bil?includeengroscvr=true&includeleasing=false&sortby=date&sortorder=desc")

        try:
            page.click("button:has-text('Accepter alle')", timeout=3000)
            print("✅ Cookie-popup accepteret (oversigt)")
        except:
            print("ℹ️ Ingen cookie-popup (oversigt)")

        try:
            page.wait_for_selector("section.srp_results__2UEV_", timeout=15000)
        except:
            print("❌ Kunne ikke finde bil-oversigt!")
            return

        html = page.content()
        soup = BeautifulSoup(html, "html.parser")
        cars = soup.select("article.Listing_listing__XwaYe")
        print(f"\n🚗 Fundet {len(cars)} biler på Bilbasen")

        for car in cars:
            link_el = car.select_one("a.Listing_link__6Z504")
            if not link_el:
                continue

            link = link_el["href"]
            full_link = link if link.startswith("http") else "https://www.bilbasen.dk" + link
            car_id = extract_car_id(full_link)

            if car_id in existing_ids:
                print(f"⏩ Springer over eksisterende bil {car_id}")
                continue

            page.goto(full_link)
            try:
                page.click("button:has-text('Accepter alle')", timeout=3000)
                print("✅ Cookie-popup accepteret (bilside)")
            except:
                pass

            try:
                page.wait_for_selector("main.bas-MuiVipPageComponent-main", timeout=20000)
            except:
                print(f"❌ Timeout på bilside: {full_link}")
                continue

            car_html = page.content()
            car_soup = BeautifulSoup(car_html, "html.parser")

            # Parse details
            price_el = car_soup.select_one('span.bas-MuiCarPriceComponent-value[data-e2e="car-retail-price"]')
            price = price_el.get_text(strip=True) if price_el else ""

            title_el = car_soup.select_one("h1.bas-MuiCarHeaderComponent-title")
            brand_model = title_el.get_text(strip=True) if title_el else ""
            brand = brand_model.split(" ")[0] if brand_model else ""
            model = " ".join(brand_model.split(" ")[1:]) if brand_model else ""

            image_tags = car_soup.select("img.bas-MuiGalleryImageComponent-image")
            image_urls = [img["src"] for img in image_tags if img.has_attr("src")]
            images_combined = ", ".join(image_urls[:3])

            desc_el = car_soup.select_one("div[aria-label='beskrivelse'] .bas-MuiAdDescriptionComponent-descriptionText")
            description = desc_el.get_text(" ", strip=True) if desc_el else ""

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
                "doors": model_info.get("Døre", "")
            }

            print(f"📤 Sender data til Supabase for bil: {brand_model} ({car_id})")
            response = requests.post(
                f"{SUPABASE_URL}/rest/v1/{TABLE_NAME}",
                json=data,
                headers=headers
            )
            print(f"🔁 Supabase respons: {response.status_code} - {response.text}")

@app.route("/")
def index():
    return "✅ Bilbasen scraper kører!"

def run_scraper():
    scrape_bilbasen()

if __name__ == "__main__":
    Thread(target=run_scraper).start()
    app.run(host="0.0.0.0", port=10000)