"use strict";

// Chart runtime state.
// These globals are intentionally centralized because the project is still loaded
// with browser script tags instead of ES modules.

let chartElement = null;
let activeSeries = null;
let ema20Series = null;
let volumeSeries = null;
let chartResizeObserver = null;
let SPY = null;
let Equity = null;
let seriesMarkersApi = null;

const chartUiState = {
  gridVisible: true,
  theme: "dark",
};

const portfolioSeriesConfig = {
  equity: {
    fields: ["equity", "total_equity", "balance"],
    label: "Equity",
    color: "#24d26c",
  },
  assets: {
    fields: ["portfolio_assets", "assets", "asset_value", "positions_value"],
    label: "Assets",
    color: "#ffb84d",
  },
  cash: {
    fields: ["cash", "wallet_cash", "buying_power"],
    label: "Cash",
    color: "#3a92ff",
  },
};
