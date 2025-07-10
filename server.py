import os
import time
import re
import tempfile
import shutil
import certifi
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
                    response = requests.get(full_size_url, headers=headers, stream=True, timeout=15, verify=verify_ssl)
                    if response.status_code == 200:
                        filename = sanitize_filename(os.path.basename(urlparse(full_size_url).path)) or f"image_{int(time.time())}.jpg"
                        file_path = os.path.join(folder, filename)
                        with open(file_path, 'wb') as f:
                            for chunk in response.iter_content(1024):
                                f.write(chunk)
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

# --- (pozostała część kodu się nie zmienia, bo nie dotyczy problemu SSL) ---
