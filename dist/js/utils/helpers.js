"use strict";

// Shared helpers used across the dashboard.
// Keep this file free of feature-specific DOM rendering logic.

function normalizeTicker(ticker) {
  return String(ticker || "").trim().toUpperCase();
}

function normalizeLogoTicker(ticker) {
  const cleanTicker = normalizeTicker(ticker);

  // Brandfetch/market-data providers often use dot notation for Berkshire.
  if (cleanTicker === "BRK-B") return "BRK.B";
  if (cleanTicker === "BRK-A") return "BRK.A";

  return cleanTicker;
}

function money(value) {
  const numeric = Number(value || 0);
  const sign = numeric < 0 ? "-" : "";
  return `${sign}$${Math.abs(numeric).toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function pct(value) {
  const numeric = Number(value || 0);
  const sign = numeric >= 0 ? "+" : "";
  return `${sign}${numeric.toFixed(2)}%`;
}

function formatDateTime(value) {
  if (!value) return "--";

  const dateObj = new Date(value);
  if (Number.isNaN(dateObj.getTime())) return "--";

  return dateObj.toLocaleString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function getTickerClass(ticker) {
  return normalizeTicker(ticker).toLowerCase().replace(/[^a-z0-9_-]/g, "-");
}

function companyLogoUrl(ticker) {
  const clientId = "1idTwwKeUgTw4-hQF9N".trim();
  const logoTicker = normalizeLogoTicker(ticker);

  if (!logoTicker || !clientId) return "";

  return `https://cdn.brandfetch.io/ticker/${encodeURIComponent(logoTicker)}?c=${clientId}`;
}

function defaultCompanyProfile(ticker) {
  const cleanTicker = normalizeTicker(ticker);
  const logoTicker = normalizeLogoTicker(cleanTicker);

  return {
    ticker: cleanTicker,
    name: `${cleanTicker} Corp.`,
    short: cleanTicker,
    sector: "Unknown",
    industry: "Unknown",
    cap: "N/A",
    market_cap_label: "N/A",
    revenue: "N/A",
    revenue_trend: "N/A",
    risk: "N/A",
    risk_level: "N/A",
    outlook: "N/A",
    founded: "N/A",
    summary: "",
    logoTicker,
    logo_ticker: logoTicker,
    logoUrl: companyLogoUrl(logoTicker),
    logo: cleanTicker.slice(0, 2) || "--",
  };
}

function normalizeCompanyProfile(rawProfile, ticker) {
  const cleanTicker = normalizeTicker(ticker || rawProfile?.ticker);
  const fallback = defaultCompanyProfile(cleanTicker);
  const localProfile = companyProfiles?.[cleanTicker] || {};
  const profile = rawProfile || {};
  const logoTicker =
    profile.logo_ticker ||
    profile.logoTicker ||
    localProfile.logo_ticker ||
    localProfile.logoTicker ||
    fallback.logoTicker;

  return {
    ticker: cleanTicker,
    name: profile.name ?? localProfile.name ?? fallback.name,
    short: profile.short ?? localProfile.short ?? profile.name ?? localProfile.name ?? fallback.short,
    sector: profile.sector ?? localProfile.sector ?? fallback.sector,
    industry: profile.industry ?? localProfile.industry ?? fallback.industry,
    cap: profile.market_cap_label ?? profile.cap ?? localProfile.cap ?? fallback.cap,
    market_cap_label: profile.market_cap_label ?? profile.cap ?? localProfile.cap ?? fallback.market_cap_label,
    revenue: profile.revenue_trend ?? profile.revenue ?? localProfile.revenue ?? fallback.revenue,
    revenue_trend: profile.revenue_trend ?? profile.revenue ?? localProfile.revenue ?? fallback.revenue_trend,
    risk: profile.risk_level ?? profile.risk ?? localProfile.risk ?? fallback.risk,
    risk_level: profile.risk_level ?? profile.risk ?? localProfile.risk ?? fallback.risk_level,
    outlook: profile.outlook ?? localProfile.outlook ?? fallback.outlook,
    founded: profile.founded ?? localProfile.founded ?? fallback.founded,
    summary: profile.summary ?? localProfile.summary ?? fallback.summary,
    logoTicker,
    logo_ticker: logoTicker,
    logoUrl: companyLogoUrl(logoTicker),
    logo: profile.logo ?? localProfile.logo ?? fallback.logo,
  };
}

// Synchronous local profile lookup. Use this for list rows and anything that must render immediately.
function profileFor(ticker) {
  const cleanTicker = normalizeTicker(ticker);
  return normalizeCompanyProfile(companyProfiles?.[cleanTicker], cleanTicker);
}

// Async backend profile lookup. Use this only where awaiting is safe, such as modal opening.
async function fetchCompanyProfile(ticker) {
  const cleanTicker = normalizeTicker(ticker);

  if (!cleanTicker) return defaultCompanyProfile(cleanTicker);

  const response = await apiGet(
    `/api/dossiers/profile/${encodeURIComponent(cleanTicker)}`,
    {
      status: "error",
      payload: null,
    },
  );

  return normalizeCompanyProfile(response?.payload, cleanTicker);
}

function showToast(message) {
  const stack = document.getElementById("toastStack");
  if (!stack) return;

  const toast = document.createElement("div");
  toast.className = "toast";
  toast.textContent = message;
  stack.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateX(12px)";
    setTimeout(() => toast.remove(), 250);
  }, 2600);
}


// Expose shared helpers explicitly for classic-script loading.
// This avoids ReferenceError issues when another script expects helpers on window.
Object.assign(globalThis, {
  normalizeTicker,
  normalizeLogoTicker,
  money,
  pct,
  formatDateTime,
  getTickerClass,
  companyLogoUrl,
  defaultCompanyProfile,
  normalizeCompanyProfile,
  profileFor,
  fetchCompanyProfile,
  showToast,
});
