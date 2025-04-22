import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import time

SUPABASE_URL = "https://mmhzdntjwkkpflglwchy.supabase.co"
SUPABASE_API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im1taHpkbnRqd2trcGZsZ2x3Y2h5Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc0NTMxNzA4NywiZXhwIjoyMDYwODkzMDg3fQ.KHCCOUENSAPJuxfJTdcT6a-zESt8HumumDzCz08zwHs"
TABLE_NAME = "bilbasen_cars"

def extract_car_id(link):
    return link.rstrip("/").split("/")[-1]

def get_existing_ids():
    res = requests.get(
        f"{SUPABASE_URL}/rest/v1/{TABLE_NAME}?select=id",
        headers={
            "apikey": SUPABASE_API_KEY,
            "Authorization": f"Bearer {SUPABASE_API_KEY}"
        }
    )
    if res.status_code == 200:
        return {row['id'] for row in res.json()}
    return set()

def scrape_brand_model(brand, model):
    base_url = "https://www.bilbasen.dk"
    existing_ids = get_existing_ids()
    MAX_PAGES = 50

    for page in range(1, MAX_PAGES + 1):
        url = f"{base_url}/brugt/bil/{brand}/{model}?page={page}"
        res = requests.get(url)
        soup = BeautifulSoup(res.text, "html.parser")
        cars = soup.select(".bb-listing")

        if not cars:
            break

        for car in cars:
            link_el = car.select_one("a.listing-heading")
            if not link_el or not link_el.has_attr("href"):
                continue

            link = urljoin(base_url, link_el['href'])
            car_id = extract_car_id(link)
            if car_id in existing_ids:
                continue

            title = car.select_one(".listing-heading").get_text(strip=True) if car.select_one(".listing-heading") else ""
            price = car.select_one(".listing-price").get_text(strip=True) if car.select_one(".listing-price") else ""
            data_items = car.select(".listing-data li")
            year = data_items[0].get_text(strip=True) if len(data_items) > 0 else ""
            km = data_items[1].get_text(strip=True) if len(data_items) > 1 else ""
            motor = data_items[2].get_text(strip=True) if len(data_items) > 2 else ""
            equipment = car.select_one(".listing-equipment").get_text(strip=True) if car.select_one(".listing-equipment") else ""

            data = {
                "id": car_id,
                "title": title,
                "link": link,
                "price": price,
                "year": year,
                "km": km,
                "motor": motor,
                "brand": brand,
                "model": model,
                "equipment": equipment
            }

            response = requests.post(
                f"{SUPABASE_URL}/rest/v1/{TABLE_NAME}",
                json=data,
                headers={
                    "apikey": SUPABASE_API_KEY,
                    "Authorization": f"Bearer {SUPABASE_API_KEY}",
                    "Content-Type": "application/json",
                    "Prefer": "return=representation"
                }
            )

            print(f"✅ Gemt: {brand} {model} → {car_id}")

def run_all():
    brands_and_models = [
        ("skoda", "octavia"),
        ("audi", "a4"),
        ("audi", "a6"),
        ("bmw", "3-serie"),
        ("mercedes", "c-klasse"),
        ("volkswagen", "golf"),
        ("toyota", "yaris"),
        ("ford", "focus"),
        # Tilføj flere mærker og modeller her...
    ]

    while True:
        for brand, model in brands_and_models:
            print(f"🔍 Henter {brand} {model}")
            scrape_brand_model(brand, model)
            time.sleep(5)  # Vent mellem modeller

        print("⏳ Venter 30 min før næste runde...\n")
        time.sleep(1800)

if __name__ == "__main__":
    run_all()
