"use strict";

// Manual trading actions.
// These handlers call Rust commands, refresh portfolio/equity state, and redraw charts.

async function refreshAfterTrade() {
  await Promise.all([fetchEquitySummary(), loadPortfolio()]);
  if (state.chartKind === "portfolio") await renderCurrentChart();
}

function readBuyForm() {
  const ticker = document
    .getElementById("buyTickerInput")
    .value.trim()
    .toUpperCase();
  const amount = Number(
    String(document.getElementById("buyAmountInput").value).replace(/[$,]/g, ""),
  );

  return { ticker, amount };
}

function initControlTabs() {
  document.querySelectorAll(".control-tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      document
        .querySelectorAll(".control-tab")
        .forEach((button) => button.classList.remove("active"));
      tab.classList.add("active");

      const selectedPanelId = `${tab.dataset.tab}Panel`;
      document.querySelectorAll(".control-tab-panel").forEach((panel) => {
        panel.classList.toggle("active", panel.id === selectedPanelId);
      });
    });
  });
}

function initQuickBuyButtons() {
  document.querySelectorAll("[data-buy-ticker]").forEach((button) => {
    button.addEventListener("click", () => {
      document.getElementById("buyTickerInput").value = button.dataset.buyTicker;
    });
  });
}

function initBuyButton() {
  const buyButton = document.getElementById("buyBtn");
  if (!buyButton) return;

  buyButton.addEventListener("click", async () => {
    const { ticker, amount } = readBuyForm();

    if (!ticker || !Number.isFinite(amount) || amount <= 0) {
      showToast("Enter a ticker and valid amount.");
      return;
    }

    try {
      const response = await apiPost("/api/broker/buy", { ticker, amount });
      const succeeded = response.status === "success";

      addActivityEvent({
        type: succeeded ? "BUY" : "ERROR",
        ticker,
        title: succeeded ? "Manual buy request" : "Buy failed",
        summary: response.message || "Request sent.",
        ttl_seconds: null,
      });
      showToast(response.message || "Buy request sent.");

      if (succeeded) await refreshAfterTrade();
    } catch (error) {
      console.error("Error buying from Rust:", error);
      showToast(`Could not buy ${ticker}.`);
    }
  });
}

function initSellButton() {
  const sellButton = document.getElementById("sellBtn");
  if (!sellButton) return;

  sellButton.addEventListener("click", async () => {
    const select = document.getElementById("sellAssetSelect");
    const tradeId = select.value;
    const option = select.options[select.selectedIndex];
    const ticker = option?.dataset.ticker || "--";

    if (!tradeId) {
      showToast("No position selected.");
      return;
    }

    try {
      const response = await apiPost("/api/broker/sell", { trade_id: tradeId });
      const succeeded = response.status === "success";

      addActivityEvent({
        type: succeeded ? "SELL" : "ERROR",
        ticker,
        title: succeeded ? "Manual sell request" : "Sell failed",
        summary: response.message || "Request sent.",
        ttl_seconds: null,
      });
      showToast(response.message || "Sell request sent.");

      if (succeeded) await refreshAfterTrade();
    } catch (error) {
      console.error("Error selling from Rust:", error);
      showToast(`Could not sell ${ticker}.`);
    }
  });
}

function initLiquidateButton() {
  const liquidateButton = document.getElementById("liquidateBtn");
  if (!liquidateButton) return;

  liquidateButton.addEventListener("click", async () => {
    try {
      const response = await apiPost("/api/broker/liquidation");
      const succeeded = response.status === "success";

      addActivityEvent({
        type: succeeded ? "LIQUIDATE" : "ERROR",
        ticker: "--",
        title: succeeded ? "Liquidate all request" : "Liquidation failed",
        summary: response.message || "Request sent.",
        ttl_seconds: null,
      });
      showToast(response.message || "Liquidation request sent.");

      if (succeeded) await refreshAfterTrade();
    } catch (error) {
      console.error("Error liquidating from Rust:", error);
      showToast("Could not liquidate the portfolio.");
    }
  });
}

function initTradingControls() {
  initControlTabs();
  initQuickBuyButtons();
  initBuyButton();
  initSellButton();
  initLiquidateButton();
}
