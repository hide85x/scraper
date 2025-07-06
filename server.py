import os
import time
import re
import tempfile
from urllib.parse import urljoin, urlparse
from pathlib import Path

import requests
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

app = Flask(__name__)
CORS(app)

def scroll_page(driver):
    last_height = driver.execute_script("return document.body.scrollHeight")
    while True:
        driver.execute_script("window.scrollBy(0, 1000);")
        time.sleep(2)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height

    images = driver.find_elements("tag name", "img")
    for img in images:
        try:
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", img)
            time.sleep(0.2)
        except Exception as e:
            print(f"Skipping image due to error: {e}")

def trigger_slider(driver):
    try:
        next_buttons = driver.find_elements("class name", "slick-next")
        for btn in next_buttons:
            for _ in range(5):
                btn.click()
                time.sleep(1)
    except Exception as e:
        print(f"Error interacting with slider: {e}")

def clean_and_generate_urls(url):
    url = url.replace("/thumbs/", "/").replace("/thumb/", "/")
    url = re.sub(r'/\d+x\d+/', '/', url)
    variations = [
        url,
        re.sub(r'/thumbs?/\d+x\d+/', '/uploads/', url),
        re.sub(r'/thumbs?/\d+x\d+/', '/', url),
        url.replace('/thumbs/', '/uploads/'),
        url.replace('/thumb/', '/uploads/'),
        url.replace('/thumbs/', '/'),
        url.replace('/thumb/', '/')
    ]
    return list(dict.fromkeys(variations))

def prioritize_jpg(url):
    original_url = re.sub(r'/\d+x\d+/', '/', url)
    if ".webp" in original_url:
        jpg_url = original_url.replace(".webp", ".jpeg")
        jpg_alt_url = original_url.replace(".webp", ".jpg")
        response = requests.head(jpg_url)
        if response.status_code == 200:
            return jpg_url
        response = requests.head(jpg_alt_url)
        if response.status_code == 200:
            return jpg_alt_url
    elif ".jpeg" in original_url or ".jpg" in original_url:
        response = requests.head(original_url)
        if response.status_code == 200:
            return original_url
    return url

def download_image(url, folder, base_url):
    try:
        url = urljoin(base_url, url)
        full_size_urls = clean_and_generate_urls(url)
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0.4472.124 Safari/537.36'}

        for full_size_url in full_size_urls:
            response = requests.get(full_size_url, headers=headers, stream=True)
            if response.status_code == 200:
                filename = sanitize_filename(os.path.basename(urlparse(full_size_url).path))
                if not filename:
                    filename = "image_" + str(int(time.time())) + ".jpg"

                file_path = os.path.join(folder, filename)
                with open(file_path, 'wb') as f:
                    for chunk in response.iter_content(1024):
                        f.write(chunk)
                return filename
        return None
    except Exception as e:
        print(f"Failed to download {url}: {e}")
        return None

def get_highest_resolution_image(srcset):
    try:
        src_list = [s.strip() for s in srcset.split(",")]
        url_res_pairs = []
        for src in src_list:
            parts = src.split(" ")
            if len(parts) == 2:
                url, res = parts
                res_value = int(re.sub("[^0-9]", "", res))
                url_res_pairs.append((url, res_value))
        if url_res_pairs:
            url_res_pairs.sort(key=lambda x: x[1], reverse=True)
            return url_res_pairs[0][0]
    except Exception as e:
        print(f"Error processing srcset: {e}")
    return None

def extract_full_res_images(driver):
    image_urls = set()
    links = driver.find_elements("tag name", "a")
    for link in links:
        href = link.get_attribute("href")
        img_tag = link.find_elements("tag name", "img")
        if href and (".jpg" in href or ".jpeg" in href or ".png" in href or ".webp" in href):
            prioritized_url = prioritize_jpg(href)
            image_urls.add(prioritized_url)
        if img_tag:
            img_src = img_tag[0].get_attribute("src")
            if img_src:
                prioritized_url = prioritize_jpg(img_src)
                image_urls.add(prioritized_url)

    images = driver.find_elements("tag name", "img")
    for img in images:
        data_srcset = img.get_attribute("data-srcset")
        srcset = img.get_attribute("srcset")
        src = img.get_attribute("src")

        if data_srcset:
            best_image = get_highest_resolution_image(data_srcset)
            if best_image:
                prioritized_url = prioritize_jpg(best_image)
                image_urls.add(prioritized_url)
        elif srcset:
            best_image = get_highest_resolution_image(srcset)
            if best_image:
                prioritized_url = prioritize_jpg(best_image)
                image_urls.add(prioritized_url)
        elif src:
            prioritized_url = prioritize_jpg(src)
            image_urls.add(prioritized_url)

    return image_urls

def sanitize_filename(filename):
    return "".join(c if c.isalnum() or c in (' ', '.', '_') else '_' for c in filename)

def get_meta_title(driver):
    try:
        title = driver.title.strip()
        return sanitize_filename(title)
    except Exception as e:
        print(f"Error retrieving page title: {e}")
        return "Unknown_Page"

@app.route('/scrape', methods=['POST'])
def scrape_images():
    data = request.json
    website_url = data.get("url")
    if not website_url:
        return jsonify({"error": "No URL provided"}), 400

    chrome_options = Options()
    temp_dir = tempfile.mkdtemp()
    chrome_options.add_argument(f"--user-data-dir={temp_dir}")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--no-first-run")
    chrome_options.add_argument("--no-default-browser-check")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-application-cache")
    chrome_options.add_argument("--incognito")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36')

    try:
        driver = webdriver.Chrome(options=chrome_options)
        print("Headless Chrome wystartował.")
    except Exception as e:
        print(f"Błąd przy starcie Chrome: {e}")
        return jsonify({"error": "Chrome startup failed"}), 500

    try:
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        driver.execute_cdp_cmd('Network.setUserAgentOverride', {
            "userAgent": 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
            "acceptLanguage": "en-US,en;q=0.9"
        })
    except Exception as e:
        print(f"Błąd podczas ustawiania stealth: {e}")

    print(f"Processing: {website_url}")
    driver.set_page_load_timeout(30)

    try:
        driver.get(website_url)
        print("Strona załadowana, kontynuuję scrapowanie.")
        driver.save_screenshot("/tmp/screenshot.png")
        print("Screenshot zapisany zaraz po załadowaniu strony.")
    except Exception as e:
        print(f"Błąd ładowania strony: {e}")
        driver.save_screenshot("/tmp/screenshot.png")
        print("Screenshot zapisany przy błędzie ładowania strony.")
        driver.quit()
        return jsonify({"error": "Timeout or loading error"}), 500

    time.sleep(10)
    scroll_page(driver)
    trigger_slider(driver)

    page_title = get_meta_title(driver)
    image_urls = extract_full_res_images(driver)
    print(f"Znaleziono {len(image_urls)} obrazów.")
    print(f"Serwer: Strona załadowana, tytuł: {page_title}")

    if not image_urls:
        driver.save_screenshot("/tmp/screenshot.png")
        print("Screenshot zapisany przed zakończeniem (brak zdjęć).")
        driver.quit()
        return jsonify({"message": "No images found", "images": []})

    driver.save_screenshot("/tmp/screenshot.png")
    print("Screenshot zapisany przed zakończeniem (z obrazkami).")

    folder_name = os.path.join("downloaded_images", page_title)
    os.makedirs(folder_name, exist_ok=True)

    for img_url in image_urls:
        download_image(img_url, folder_name, website_url)

    saved_files = [f for f in os.listdir(folder_name) if os.path.isfile(os.path.join(folder_name, f))]
    count = len(saved_files)

    driver.quit()

    response = jsonify({
        "message": f"Scraping complete, downloaded {count} images",
        "images": saved_files,
        "folder": folder_name
    })
    return response

@app.route('/screenshot')
def get_screenshot():
    screenshot_path = "/tmp/screenshot.png"
    if not os.path.exists(screenshot_path):
        return jsonify({"error": "Screenshot not found"}), 404
    return send_file(screenshot_path, mimetype='image/png')

if __name__ == "__main__":
    app.run(debug=True, port=5000)
