"use strict";

// App bootstrap.
// All feature-level event binding happens here, then the initial backend data is loaded.

function initUiControls() {
  initCompareFeature();
  initPortfolioSearch();
  initTradingControls();
  initSettingsControls();
  initTradeAnalyzerControls();
}

async function loadInitialDashboardData() {
  await fetchEquitySummary();
  await loadPortfolio();
  await loadTradeJournal();
  await loadActivity();
  await loadScheduler();

  supportedCompanies = await getCompanies();
}

function startPolling() {
  setInterval(fetchEquitySummary, POLLING_INTERVALS.equitySummaryMs);
}

async function init() {
  initUiControls();
  connectBotEventStream();
  await loadInitialDashboardData();

  // The initial chart is the portfolio equity chart. Clicking a position switches
  // the main chart to that ticker's candlesticks.
  await renderCurrentChart();
  startPolling();
}

init().catch((error) => {
  console.error("Dashboard initialization failed:", error);
  showToast("Dashboard initialization failed. Check the console for details.");
});

// Optional real-time polling hooks for later:
// setInterval(loadActivity, POLLING_INTERVALS.activityMs);
// setInterval(loadScheduler, POLLING_INTERVALS.schedulerMs);
// setInterval(loadPortfolio, POLLING_INTERVALS.portfolioMs);
