"use strict";

// Chooses the current chart renderer based on app state.

function clearActivePortfolioSelection() {
  document
    .querySelectorAll(".portfolio-item")
    .forEach((item) => item.classList.remove("active-stock"));
}

async function renderCurrentChart() {
  updateButtons();
  const compareIsActive = comparedCompanies.length > 0;

  if (compareIsActive) {
    return graphComparedTickers(comparedCompanies);
  }

  if (state.chartKind === "portfolio") {
    clearActivePortfolioSelection();
    return loadEquityChart();
  }

  return loadCandles(state.ticker, state.timeframe);
}
