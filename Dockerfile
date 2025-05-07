FROM mcr.microsoft.com/playwright/python:v1.52.0-jammy

# Sæt arbejdsmappe
WORKDIR /app

# Kopiér kode og installér afhængigheder
COPY . .

# Installer Python-afhængigheder
RUN pip install --no-cache-dir -r requirements.txt

# 👇 Installer Playwright-browsere
RUN playwright install --with-deps

# Kør scraperen
CMD ["python", "main.py"]