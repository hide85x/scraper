// popup.js
document.getElementById("scrapeButton").addEventListener("click", () => {
  let button = document.getElementById("scrapeButton");
  button.classList.add("clicked");
  
  setTimeout(() => {
    button.classList.remove("clicked");
  }, 300);

  // Get the current tab's URL
  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    let url = tabs[0].url;

    // Let the user know we’re initiating the background scrape
    document.getElementById("status").innerText =
      "Scraping images... Please wait.";

    // Send a message to background.js with the URL
    chrome.runtime.sendMessage({ type: "START_SCRAPE", url: url }, (response) => {
      if (chrome.runtime.lastError) {
        console.error("No response from background:", chrome.runtime.lastError.message);
        document.getElementById("status").innerText =
          "Error: no response from background script.";
        return;
      }

      if (response && response.ok) {
        console.log("Background accepted the scrape job.");
      } else {
        console.error("Error from background script:", response && response.error);
        document.getElementById("status").innerText =
          "Error: " + (response ? response.error : "Unknown");
      }
    });
  });
});

// Listen for final status message from background script
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "SCRAPE_COMPLETE") {
    document.getElementById("status").innerText = message.message;
  }
});
