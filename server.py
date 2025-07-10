import os
import time
import re
import tempfile
import shutil
import certifi
import urllib3
from urllib.parse import urljoin, urlparse
from pathlib import Path

import requests
from requests.exceptions import SSLError, ConnectionError
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
import chromedriver_autoinstaller
import zipfile

# Wyłączanie ostrzeżeń o niezweryfikowanych certyfikatach
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)
CORS(app)

chromedriver_autoinstaller.install()

def clear_download_folder():
    base_folder = 'downloaded_images'
    if os.path.exists(base_folder):
        shutil.rmtree(base_folder)
    os.makedirs(base_folder, exist_ok=True)

def scroll_page(driver):
    last_height = driver.execute_script("return document.body.scrollHeight")
    while True:
        driver.execute_script("window.scrollBy(0, 1000);")
        time.sleep(2)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height

    images = driver.find_elements(By.TAG_NAME, "img")
    for img in images:
        try:
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", img)
            time.sleep(0.2)
        except Exception as e:
            print(f"Skipping image due to error: {e}")

def trigger_slider(driver):
    try:
        next_buttons = driver.find_elements(By.CLASS_NAME, "slick-next")
        for btn in next_buttons:
            if not btn.is_displayed():
                continue
            for _ in range(5):
                try:
                    driver.execute_script("arguments[0].click();", btn)
                    time.sleep(1)
                except Exception as e:
                    print(f"Slider click error: {e}")
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

    if original_url.startswith('//'):
        original_url = 'https:' + original_url

    for verify_ssl in [certifi.where(), False]:
        try:
            response = requests.head(original_url, timeout=7, verify=verify_ssl)
            if response.status_code == 200:
                return original_url
        except (SSLError, ConnectionError) as ssl_err:
            if not verify_ssl:
                print(f"❌ HEAD failed (SSL bypass failed): {original_url} — {ssl_err}")
            else:
                print(f"⚠️ HEAD SSL verify failed: {original_url}, retrying without verify...")
        except Exception as e:
            print(f"❌ HEAD general error: {original_url} — {e}")

    for verify_ssl in [certifi.where(), False]:
        try:
            response = requests.get(original_url, stream=True, timeout=7, verify=verify_ssl)
            if response.status_code == 200:
                return original_url
        except Exception as e:
            print(f"❌ GET retry failed: {original_url} — {e}")

    print(f"Skipping broken URL: {original_url}")
    return None
    
def download_image(url, folder, base_url):
    try:
        url = urljoin(base_url, url)
        full_size_urls = clean_and_generate_urls(url)
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0.4472.124 Safari/537.36'}

        for full_size_url in full_size_urls:
            for verify_ssl in [certifi.where(), False]:
                try:
                    response = requests.get(full_size_url, headers=headers, timeout=15, verify=verify_ssl)
                    if response.status_code == 200:
                        filename = sanitize_filename(os.path.basename(urlparse(full_size_url).path)) or f"image_{int(time.time())}.jpg"
                        file_path = os.path.join(folder, filename)
                        with open(file_path, 'wb') as f:
                            f.write(response.content)
                        return filename
                except (SSLError, ConnectionError) as ssl_err:
                    if not verify_ssl:
                        print(f"❌ SSL bypass failed for {full_size_url}: {ssl_err}")
                    else:
                        print(f"⚠️ SSL verify failed for {full_size_url}, retrying without verify...")
                except Exception as e:
                    print(f"❌ General error downloading {full_size_url}: {e}")
        return None
    except Exception as e:
        print(f"❌ Failed to process {url}: {e}")
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
    links = driver.find_elements(By.TAG_NAME, "a")
    for link in links:
        href = link.get_attribute("href")
        img_tag = link.find_elements(By.TAG_NAME, "img")
        if href and (".jpg" in href or ".jpeg" in href or ".png" in href or ".webp" in href):
            prioritized_url = prioritize_jpg(href)
            if prioritized_url:
                image_urls.add(prioritized_url)
        if img_tag:
            img_src = img_tag[0].get_attribute("src")
            if img_src:
                prioritized_url = prioritize_jpg(img_src)
                if prioritized_url:
                    image_urls.add(prioritized_url)

    images = driver.find_elements(By.TAG_NAME, "img")
    for img in images:
        data_srcset = img.get_attribute("data-srcset")
        srcset = img.get_attribute("srcset")
        src = img.get_attribute("src")

        if data_srcset:
            best_image = get_highest_resolution_image(data_srcset)
            if best_image:
                prioritized_url = prioritize_jpg(best_image)
                if prioritized_url:
                    image_urls.add(prioritized_url)
        elif srcset:
            best_image = get_highest_resolution_image(srcset)
            if best_image:
                prioritized_url = prioritize_jpg(best_image)
                if prioritized_url:
                    image_urls.add(prioritized_url)
        elif src:
            prioritized_url = prioritize_jpg(src)
            if prioritized_url:
                image_urls.add(prioritized_url)

    pictures = driver.find_elements(By.TAG_NAME, "picture")
    for picture in pictures:
        sources = picture.find_elements(By.TAG_NAME, "source")
        for source in sources:
            srcset = source.get_attribute("srcset")
            if srcset:
                best_image = get_highest_resolution_image(srcset)
                if best_image:
                    prioritized_url = prioritize_jpg(best_image)
                    if prioritized_url:
                        image_urls.add(prioritized_url)

    og_image = driver.find_elements(By.XPATH, "//meta[@property='og:image']")
    for meta in og_image:
        content = meta.get_attribute("content")
        if content:
            prioritized_url = prioritize_jpg(content)
            if prioritized_url:
                image_urls.add(prioritized_url)

    lazy_images = driver.find_elements(By.TAG_NAME, "img")
    for img in lazy_images:
        for attr in img.get_property("attributes"):
            if "data-" in attr["name"] and (".jpg" in attr["value"] or ".jpeg" in attr["value"] or ".png" in attr["value"] or ".webp" in attr["value"]):
                prioritized_url = prioritize_jpg(attr["value"])
                if prioritized_url:
                    image_urls.add(prioritized_url)

    elements_with_bg = driver.find_elements(By.XPATH, "//*[contains(@style, 'background-image')]")
    for elem in elements_with_bg:
        style = elem.get_attribute('style')
        if 'background-image' in style:
            start = style.find('url(') + 4
            end = style.find(')', start)
            img_url = style[start:end].replace('"', '').replace("'", '')
            prioritized_url = prioritize_jpg(img_url)
            if prioritized_url:
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
    clear_download_folder()

    data = request.json
    website_url = data.get("url")
    if not website_url:
        return jsonify({"error": "No URL provided"}), 400

    chrome_options = Options()
    temp_dir = tempfile.mkdtemp()
    chrome_options.add_argument(f"--user-data-dir={temp_dir}")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--no-first-run")
    chrome_options.add_argument("--no-default-browser-check")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-application-cache")
    chrome_options.add_argument("--incognito")

    try:
        driver = webdriver.Chrome(options=chrome_options)
        print("Headless Chrome wystartował.")
    except Exception as e:
        print(f"Błąd przy starcie Chrome: {e}")
        return jsonify({"error": "Chrome startup failed"}), 500

    print(f"Processing: {website_url}")
    driver.set_page_load_timeout(60)

    try:
        driver.get(website_url)
        print("Strona załadowana, kontynuuję scrapowanie.")
    except Exception as e:
        print(f"Błąd ładowania strony: {e}")
        driver.quit()
        return jsonify({"error": "Timeout or loading error"}), 500

    time.sleep(6)
    scroll_page(driver)
    trigger_slider(driver)

    page_title = get_meta_title(driver)
    image_urls = extract_full_res_images(driver)
    driver.quit()
    print(f"Znaleziono {len(image_urls)} obrazów.")
    print(f"Serwer: Strona załadowana, tytuł: {page_title}")
    if not image_urls:
        return jsonify({"message": "No images found", "images": []})

    folder_name = os.path.join("downloaded_images", page_title)
    os.makedirs(folder_name, exist_ok=True)

    for img_url in image_urls:
        download_image(img_url, folder_name, website_url)

    saved_files = [f for f in os.listdir(folder_name) if os.path.isfile(os.path.join(folder_name, f))]
    count = len(saved_files)

    response = jsonify({
        "message": f"Scraping complete, downloaded {count} images",
        "images": saved_files,
        "folder": folder_name
    })
    return response

@app.route('/download_zip')
def download_zip():
    zipf = zipfile.ZipFile('/tmp/images.zip', 'w', zipfile.ZIP_DEFLATED)
    base_folder = 'downloaded_images'

    for root, dirs, files in os.walk(base_folder):
        for file in files:
            file_path = os.path.join(root, file)
            zipf.write(file_path, arcname=file)

    zipf.close()
    print("ZIP gotowy do pobrania.")

    return send_file('/tmp/images.zip', mimetype='application/zip', as_attachment=True)

if __name__ == "__main__":
    app.run(debug=True, port=5000)
