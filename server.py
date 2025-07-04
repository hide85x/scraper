import os
import time
import re
import platform
import subprocess
import tempfile
from urllib.parse import urljoin, urlparse
from pathlib import Path
from threading import Thread

import requests
from flask import Flask, request, jsonify
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

app = Flask(__name__)
from flask_cors import CORS
CORS(app)

# --- Wszystkie Twoje funkcje bez zmian ---
# (Tu wstawiasz całą część z funkcjami scroll_page, trigger_slider, download_image itd. — nie trzeba ich zmieniać)

# ⬆️ Wszystko z Twojego kodu zostaje IDENTYCZNE aż do endpointa ⬇️

@app.route('/scrape', methods=['POST'])
def scrape_images():
    data = request.json
    website_url = data.get("url")
    if not website_url:
        return jsonify({"error": "No URL provided"}), 400

    # KONIEC KLUCZOWEJ ZMIANY — UNIKALNY user-data-dir
    chrome_options = Options()

    # Tworzymy unikalny tymczasowy katalog dla każdej sesji
    temp_dir = tempfile.mkdtemp()
    chrome_options.add_argument(f"--user-data-dir={temp_dir}")

    # Obowiązkowe opcje dla Docker + Chrome
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

    print(f"Processing: {website_url}")
    driver.get(website_url)

    time.sleep(5)
    scroll_page(driver)
    trigger_slider(driver)

    page_title = get_meta_title(driver)
    image_urls = extract_full_res_images(driver)
    driver.quit()

    if not image_urls:
        return jsonify({"message": "No images found", "images": []})

    folder_name = os.path.join("downloaded_images", page_title)
    os.makedirs(folder_name, exist_ok=True)

    # Download images (one by one)
    for img_url in image_urls:
        download_image(img_url, folder_name, website_url)

    # Now count the actual files saved in the folder
    saved_files = [f for f in os.listdir(folder_name) if os.path.isfile(os.path.join(folder_name, f))]
    count = len(saved_files)

    response = jsonify({
        "message": f"Scraping complete, downloaded {count} images",
        "images": saved_files,
        "folder": folder_name
    })
    return response

if __name__ == "__main__":
    app.run(debug=True, port=5000)
