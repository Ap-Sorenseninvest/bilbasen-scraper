import requests
from bs4 import BeautifulSoup

print("✅ Scriptet er startet...")

url = "https://www.bilbasen.dk/brugt/bil/skoda/octavia"

# Tilføj headers for at ligne en rigtig browser
headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0 Safari/537.36"
}

response = requests.get(url, headers=headers)
print(f"🌐 Statuskode fra Bilbasen: {response.status_code}")

# Print de første 500 tegn af HTML (så vi kan se om vi er blokeret)
print("\n🔍 Første 500 tegn af siden:\n")
print(response.text[:500])
print("\n———————————————\n")

# Parse HTML
soup = BeautifulSoup(response.text, "html.parser")
cars = soup.select(".bb-listing")
print(f"🚗 Antal biler fundet: {len(cars)}")

# Print titler på biler (hvis nogen)
for car in cars:
    title = car.select_one(".listing-heading")
    if title:
        print("•", title.get_text(strip=True))

print("✅ Scriptet er færdigt")
