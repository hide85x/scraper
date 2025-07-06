import os
import time
import tempfile
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

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

def trigger_slider(driver):
    try:
        next_buttons = driver.find_elements("class name", "slick-next")
        for btn in next_buttons:
            for _ in range(5):
                btn.click()
                time.sleep(1)
    except Exception as e:
        print(f"Error interacting with slider: {e}")

def get_meta_title(driver):
    try:
        return driver.title.strip()
    except Exception as e:
        print(f"Error retrieving page title: {e}")
        return "Unknown_Page"

def extract_full_res_images(driver):
    images = driver.find_elements("tag name", "img")
    image_urls = []
    for img in images:
        src = img.get_attribute("src")
        if src:
            image_urls.append(src)
    return image_urls

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

    try:
        driver = webdriver.Chrome(options=chrome_options)
        print("Headless Chrome wystartował.")
    except Exception as e:
        print(f"Błąd przy starcie Chrome: {e}")
        return jsonify({"error": "Chrome startup failed"}), 500

    print(f"Processing: {website_url}")
    driver.set_page_load_timeout(15)

    try:
        driver.get(website_url)
        print("Strona załadowana, kontynuuję scrapowanie.")
    except Exception as e:
        print(f"Błąd ładowania strony: {e}")
        driver.save_screenshot("/tmp/screenshot.png")
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

    driver.quit()

    response = jsonify({
        "message": f"Scraping complete, found {len(image_urls)} images",
        "images": image_urls,
        "page_title": page_title
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
