// offscreen.js

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === "OFFSCREEN_SCRAPE") {
    const targetUrl = msg.url;
    console.log("Offscreen: Received OFFSCREEN_SCRAPE for URL:", targetUrl);

    doScrapeAndPoll(targetUrl)
      .then(() => {
        console.log("Offscreen: Scrape + poll complete.");
        sendResponse({ success: true });
      })
      .catch(err => {
        console.error("Offscreen: Error scraping:", err);
        sendResponse({ success: false, error: err.toString() });
      });

    return true; // indicate async response
  }
});

async function doScrapeAndPoll(url) {
  const startRes = await fetch("http://localhost:5000/scrape", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url })
  });

  if (!startRes.ok) {
    throw new Error("Error scraping: " + startRes.statusText);
  }

  const startData = await startRes.json();
  console.log("Offscreen: Scrape complete:", startData);

  chrome.runtime.sendMessage({
    type: "SCRAPE_COMPLETE",
    message: startData.message
  });
}

function pollJobStatus(jobId) {
  return new Promise((resolve, reject) => {
    const interval = setInterval(async () => {
      try {
        const statusRes = await fetch("https://scrape-master-ymzg.onrender.com/job_status?job_id=" + jobId);
        const data = await statusRes.json();

        if (data.status === "finished") {
          clearInterval(interval);
          console.log("Offscreen: job finished, preparing to download ZIP.");

          // Assume the server returns an "images" array; use its length.
          const imagesCount = data.imagesCount || 0;

          if (data.zip_filename) {
            const dlUrl = "https://scrape-master-ymzg.onrender.com/download_result?job_id=" + jobId;

            // Instead of directly downloading here, send a message to background:
            chrome.runtime.sendMessage({
              type: "DOWNLOAD_ZIP",
              url: dlUrl,
              imagesCount: imagesCount
            });
          }
          resolve();
        }
        else if (data.status === "error") {
          clearInterval(interval);
          console.error("Offscreen: job error:", data.error);
          reject(new Error(data.error || "Unknown job error"));
        }
        else {
          console.log("Offscreen: job in progress...");
        }
      } catch (err) {
        clearInterval(interval);
        console.error("Offscreen: poll error:", err);
        reject(err);
      }
    }, 5000);
  });
}
