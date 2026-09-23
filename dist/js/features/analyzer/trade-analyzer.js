"use strict";

// Trade analyzer controls.
// START NEWS BOT runs news_check immediately and then repeats it on a timer.
// CHECK NEWS NOW and CHECK POSITIONS NOW are manual one-shot controls.

const startStopBtn = document.getElementById("startStopBtn");
const checkNewsBtn = document.getElementById("checkNewsBtn");
const checkStockBtn = document.getElementById("checkStockBtn");

let tradeAnalyzerToggle = false;
let newsTimerInterval = null;

function setButtonBusy(button, isBusy, busyText) {
  if (!button) return;
  if (isBusy) {
    button.dataset.originalText = button.textContent;
    button.textContent = busyText;
    button.disabled = true;
    return;
  }

  button.disabled = false;
  if (button.dataset.originalText) button.textContent = button.dataset.originalText;
}

async function runNewsCheck() {
  try {
    console.log("Starting news_check...");
    const response = await apiPost("/api/trade_analyzer/news_check");
    const message = response?.message || "News check completed";

    addActivityEvent({
      type: response?.status === "error" ? "ERROR" : "SCAN",
      ticker: "--",
      title: "News check",
      summary: message,
      ttl_seconds: 18,
    });

    showToast(`✅ ${message}`);
    console.log("News check completed:", response);

    await refreshTradingViews();
    
    return response;
  } catch (error) {
    console.error("Error during news_check:", error);
    showToast("❌ News check could not be completed");
    addActivityEvent({
      type: "ERROR",
      ticker: "--",
      title: "News check failed",
      summary: String(error?.message || error),
      ttl_seconds: 24,
    });
    return null;
  }
}

async function runStockCheck() {
  try {
    console.log("Starting check_stock...");
    const response = await apiPost("/api/broker/stock");
    const message = response?.message || "Position risk check completed";

    addActivityEvent({
      type: response?.status === "error" ? "ERROR" : "RISK",
      ticker: "--",
      title: "Position risk check",
      summary: message,
      ttl_seconds: 20,
    });

    showToast(`✅ ${message}`);
    await Promise.all([fetchEquitySummary(), loadPortfolio()]);
    if (state.chartKind === "portfolio") await renderCurrentChart();
    return response;
  } catch (error) {
    console.error("Error during check_stock:", error);
    showToast("❌ Position risk check could not be completed");
    addActivityEvent({
      type: "ERROR",
      ticker: "--",
      title: "Position check failed",
      summary: String(error?.message || error),
      ttl_seconds: 24,
    });
    return null;
  }
}

async function stopNewsAnalyzer() {
  try {
    const response = await apiPost("/api/bot/toggle", {
      turn_on: false,
    });

    tradeAnalyzerToggle = false;

    if (startStopBtn) {
      startStopBtn.textContent = "START NEWS BOT";
      startStopBtn.classList.remove("on-btn");
    }

    showToast("🤖 News Bot: PAUSED");

    await loadScheduler();
  } catch (error) {
    console.error("Failed to stop news analyzer:", error);
    showToast("❌ Could not stop News Bot");
  }
}

async function startNewsAnalyzer() {
  try {
    const response = await apiPost("/api/bot/toggle", {
      turn_on: true,
    });

    if (response.status === "rejected") {
      showToast(`❌ ${response.message}`);
      return;
    }

    tradeAnalyzerToggle = true;

    if (startStopBtn) {
      startStopBtn.textContent = "STOP NEWS BOT";
      startStopBtn.classList.add("on-btn");
    }

    showToast("🤖 News Bot: ON");

    
    await loadScheduler();


  } catch (error) {
    console.error("Failed to start news analyzer:", error);
    showToast("❌ Could not start News Bot");
  }
}



function initTradeAnalyzerControls() {
  startStopBtn.addEventListener("click", async () => {
    if (tradeAnalyzerToggle) {
      await stopNewsAnalyzer();
    } else {
      await startNewsAnalyzer();
    }
  });

  checkNewsBtn?.addEventListener("click", async () => {
    setButtonBusy(checkNewsBtn, true, "CHECKING...");
    await runNewsCheck();
    setButtonBusy(checkNewsBtn, false);
  });

  checkStockBtn?.addEventListener("click", async () => {
    setButtonBusy(checkStockBtn, true, "CHECKING...");
    await runStockCheck();
    setButtonBusy(checkStockBtn, false);
  });
}
