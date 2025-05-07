FROM mcr.microsoft.com/playwright/python:v1.52.0-jammy

WORKDIR /app
COPY . .

# 👇 Installer Playwright-browsere
RUN playwright install --with-deps

CMD ["python", "main.py"]