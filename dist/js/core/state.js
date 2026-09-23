"use strict";

// Shared runtime state for the dashboard.
// The project is still loaded with browser script tags, so this object is intentionally global.

const state = {
  ticker: "MSFT",
  timeframe: "1d",
  mode: "equity",
  chartKind: "portfolio",
  compareWithSPY: false,
  candles: [],
  positions: [],
  tradeJournal: [],
  activityEvents: [],
  schedulerOpen: false,
  cash: 0,
  equity: 0,
  indicators: {
    ema20: false,
    bollinger: false,
    lowerPanel: null,
  },
};
