// Ensure offscreen doc is created
async function ensureOffscreenDocument() {
  const alreadyExists = await chrome.offscreen.hasDocument();
  if (!alreadyExists) {
    await chrome.offscreen.createDocument({
      url: 'offscreen.html',
      reasons: ['DOM_PARSER'],
      justification: 'Parsing HTML in an offscreen context for scraping.'
    });
    console.log("Background: Offscreen document created.");
  } else {
    console.log("Background: Offscreen document already exists.");
  }
}

// Listen for messages from popup/offscreen
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "START_SCRAPE") {
    const targetUrl = message.url;
    console.log("Background: START_SCRAPE for URL:", targetUrl);

    ensureOffscreenDocument()
      .then(() => {
        // Forward the request to the offscreen doc
        chrome.runtime.sendMessage(
          { type: "OFFSCREEN_SCRAPE", url: targetUrl },
          (resp) => {
            if (chrome.runtime.lastError) {
              console.error("Background: offscreen error:", chrome.runtime.lastError.message);
              sendResponse({ ok: false, error: chrome.runtime.lastError.message });
              return;
            }
            console.log("Background: Offscreen doc response:", resp);
            if (resp && resp.success) {
              sendResponse({ ok: true });
            } else {
              sendResponse({ ok: false, error: resp ? resp.error : "Unknown error" });
            }
          }
        );
      })
      .catch(err => {
        console.error("Background: Error creating offscreen doc:", err);
        sendResponse({ ok: false, error: err.toString() });
      });

    return true; // async response
  }

  else if (message.type === "SCRAPE_COMPLETE") {
    console.log("Background: Received SCRAPE_COMPLETE.");

    const dlUrl = message.url;
    const imagesCount = message.imagesCount || 0;

    if (imagesCount > 0) {
      console.log("Background: Starting ZIP download for:", dlUrl);
      // Use chrome.downloads.download to trigger the file download
      chrome.downloads.download({ url: dlUrl }, (downloadId) => {
        console.log("Background: Download started, ID:", downloadId);
        // After initiating download, send a message to update the popup UI (if open)
        chrome.runtime.sendMessage({
          type: "ZIP_DOWNLOADING",
          message: `Pobieranie ZIP rozpoczęte. Pobieranych obrazów: ${imagesCount}`
        });
      });
    } else {
      console.log("Background: No images found, ZIP download skipped.");
      chrome.runtime.sendMessage({
        type: "ZIP_DOWNLOADING",
        message: "Brak zdjęć do pobrania."
      });
    }

    sendResponse({ success: true });
  }
});
