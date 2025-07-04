// offscreen.js

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === "OFFSCREEN_SCRAPE") {
    const targetUrl = msg.url;
    console.log("Offscreen: Received OFFSCREEN_SCRAPE for URL:", targetUrl);

    doScrape(targetUrl)
      .then(() => {
        console.log("Offscreen: Scrape complete.");
        sendResponse({ success: true });
      })
      .catch(err => {
        console.error("Offscreen: Error scraping:", err);
        sendResponse({ success: false, error: err.toString() });
      });

    return true; // async response
  }
});

async function doScrape(url) {
  const apiUrl = 'https://scraper-master-z5mg.onrender.com/scrape';

  console.log("Wysyłam request do:", apiUrl, "dla URL:", url);

  const response = await fetch(apiUrl, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url })
  });

  console.log("Fetch status:", response.status);

  if (!response.ok) {
    throw new Error(`HTTP error! Status: ${response.status}`);
  }

  const responseData = await response.json();
  console.log("Odpowiedź z serwera:", responseData);

  chrome.runtime.sendMessage({
    type: "SCRAPE_COMPLETE",
    message: responseData.message
  });
}
