# Bruger Playwrights officielle image med Python og Chromium installeret
FROM mcr.microsoft.com/playwright/python:v1.52.0-jammy

# Angiv arbejdsmappe i containeren
WORKDIR /app

# Kopiér requirements og installer Python-dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Kopiér resten af projektet
COPY . .

# Kør din scraper
CMD ["python", "main.py"]