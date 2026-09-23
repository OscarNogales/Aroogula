"use strict";

// Portfolio summary cards.
// Fetches the backend equity summary and renders the two top-level cards:
// Total Equity and Today's Gain.


const summaryMoney = (value) => {
  if (typeof window.money === "function") return window.money(value);
  const numeric = Number(value || 0);
  const sign = numeric < 0 ? "-" : "";
  return `${sign}$${Math.abs(numeric).toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
};

const summaryPct = (value) => {
  if (typeof window.pct === "function") return window.pct(value);
  const numeric = Number(value || 0);
  const sign = numeric >= 0 ? "+" : "";
  return `${sign}${numeric.toFixed(2)}%`;
};

function getPerformanceCardElements(kind) {
  const isGainCard = kind === "gain";

  return {
    card: document.getElementById(isGainCard ? "todayGainCard" : "equityCard"),
    icon: document.getElementById(isGainCard ? "todayGainIcon" : "equityIcon"),
    value: document.getElementById(isGainCard ? "todayGainValue" : "equityValue"),
    percent: document.getElementById(isGainCard ? "todayGainPct" : "equityPct"),
  };
}

/**
 * Updates a mini performance card using a dollar value and a percentage change.
 * The visual direction is based on the percentage, not the absolute value, because
 * total equity is almost always positive even on losing days.
 */
function setPerformanceCard(kind, value, percent) {
  const elements = getPerformanceCardElements(kind);
  if (!elements.card || !elements.icon || !elements.value || !elements.percent) {
    console.warn(`Missing performance card elements for: ${kind}`);
    return;
  }

  const numericPercent = Number(percent);
  const isPositive = Number.isFinite(numericPercent) ? numericPercent >= 0 : true;

  elements.card.classList.toggle("positive-card", isPositive);
  elements.card.classList.toggle("negative-card", !isPositive);
  elements.icon.textContent = isPositive ? "↗" : "↘";
  elements.value.textContent = summaryMoney(value);
  elements.percent.textContent = summaryPct(percent);
  elements.percent.className = `mini-pill ${isPositive ? "green-pill" : "red-pill"}`;
}

function normalizeEquitySummaryResponse(response) {
  const data = unwrapResponse(response) || {};

  return {
    cash: Number(data.cash ?? 0),
    portfolioAssets: Number(data.portfolio_assets ?? 0),
    totalEquity: Number(data.total_equity ?? 0),
    equityGainPct: Number(data.equity_gain_pct ?? data.today_gain_pct ?? 0),
    todayGain: Number(data.today_gain ?? 0),
    todayGainPct: Number(data.today_gain_pct ?? data.equity_gain_pct ?? 0),
  };
}

/**
 * Pulls the current equity summary from Rust/Python and refreshes dashboard cards.
 * This should run on app start, after manual trades, and on a low-frequency timer.
 */
async function fetchEquitySummary() {
  try {
    const response = await apiGet("/api/portfolio/equity_summary");
    const summary = normalizeEquitySummaryResponse(response);

    setPerformanceCard("equity", summary.totalEquity, summary.equityGainPct);
    setPerformanceCard("gain", summary.todayGain, summary.todayGainPct);

    state.cash = summary.cash;
    state.equity = summary.totalEquity;
    state.portfolioAssets = summary.portfolioAssets;

    return summary;
  } catch (error) {
    console.error("Error fetching equity summary from Rust:", error);
    showToast("Could not refresh equity summary.");
    return null;
  }
}
