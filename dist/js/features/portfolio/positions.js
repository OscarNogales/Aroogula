"use strict";

// Portfolio position loading and rendering.
// This file handles the left portfolio table and the sell-position dropdown.


// Portfolio-local compatibility wrappers.
// These keep the portfolio rendering even if the browser cached an older helpers.js.
const portfolioNormalizeTicker = (value) => {
  if (typeof window.normalizeTicker === "function") return window.normalizeTicker(value);
  return String(value || "").trim().toUpperCase();
};

const portfolioMoney = (value) => {
  if (typeof window.money === "function") return window.money(value);
  const numeric = Number(value || 0);
  const sign = numeric < 0 ? "-" : "";
  return `${sign}$${Math.abs(numeric).toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
};

const portfolioPct = (value) => {
  if (typeof window.pct === "function") return window.pct(value);
  const numeric = Number(value || 0);
  const sign = numeric >= 0 ? "+" : "";
  return `${sign}${numeric.toFixed(2)}%`;
};

const portfolioGetTickerClass = (ticker) => {
  if (typeof window.getTickerClass === "function") return window.getTickerClass(ticker);
  return portfolioNormalizeTicker(ticker).toLowerCase().replace(/[^a-z0-9_-]/g, "-");
};

const portfolioProfileFor = (ticker) => {
  const cleanTicker = portfolioNormalizeTicker(ticker);
  if (typeof window.profileFor === "function") return window.profileFor(cleanTicker);

  const logoTicker = cleanTicker === "BRK-B" ? "BRK.B" : cleanTicker === "BRK-A" ? "BRK.A" : cleanTicker;
  const clientId = "1idTwwKeUgTw4-hQF9N".trim();

  return {
    name: `${cleanTicker} Corp.`,
    short: cleanTicker,
    sector: "Unknown",
    logoUrl: logoTicker && clientId ? `https://cdn.brandfetch.io/ticker/${encodeURIComponent(logoTicker)}?c=${clientId}` : "",
    logo: cleanTicker.slice(0, 2),
  };
};

function extractPositions(result) {
  const visited = new Set();
  const queue = [result];

  while (queue.length) {
    const current = queue.shift();

    if (current == null) continue;
    if (typeof current === "object") {
      if (visited.has(current)) continue;
      visited.add(current);
    }

    if (Array.isArray(current)) {
      if (current.length === 0) return [];
      if (
        current.some(
          (item) => item && (item.ticker || item.symbol || item.trade_id),
        )
      ) {
        return current;
      }
      current.forEach((item) => queue.push(item));
      continue;
    }

    if (typeof current !== "object") continue;

    for (const key of [
      "positions",
      "portfolio",
      "trades",
      "data",
      "payload",
      "result",
    ]) {
      if (key in current) queue.push(current[key]);
    }
  }

  return [];
}

function normalizePosition(position) {
  const ticker = portfolioNormalizeTicker(position.ticker || position.symbol);
  const profile = portfolioProfileFor(ticker);
  const currentPrice = Number(
    position.current_price ??
      position.current ??
      position.market_price ??
      position.buy_price ??
      0,
  );
  const buyPrice = Number(position.buy_price ?? position.entry_price ?? 0);
  const shares = Number(position.shares ?? position.qty ?? 0);
  const pnlDollars = Number(
    position.pnl_dollars ??
      position.unrealized_pl ??
      (currentPrice - buyPrice) * shares,
  );
  const pnlPct = Number(
    position.pnl_pct ??
      position.unrealized_plpc ??
      ((currentPrice - buyPrice) / Math.max(Math.abs(buyPrice), 0.01)) * 100,
  );

  return {
    ...position,
    ticker,
    name: position.name || profile.short,
    company: position.company || profile.name,
    current_price: Number.isFinite(currentPrice) ? currentPrice : 0,
    buy_price: Number.isFinite(buyPrice) ? buyPrice : 0,
    shares: Number.isFinite(shares) ? shares : 0,
    pnl_dollars: Number.isFinite(pnlDollars) ? pnlDollars : 0,
    pnl_pct: Number.isFinite(pnlPct) ? pnlPct : 0,
    sector: position.sector || profile.sector,
    logoUrl: profile.logoUrl,
    logo: profile.logo,
  };
}

async function loadPortfolio() {
  try {
    const result = await apiGet("/api/portfolio/enriched_positions");
    const realPositions = extractPositions(result);

    if (realPositions.length > 0) {
      state.positions = realPositions;
    } else if (USE_DEMO_POSITIONS_WHEN_EMPTY) {
      state.positions = structuredClone(demoPositions);
      console.warn(
        "The backend returned zero positions; demo positions will be shown.",
      );
    } else {
      state.positions = [];
    }

    renderPortfolio();
    renderSellOptions();
  } catch (error) {
    console.error("Error loading positions:", error);

    state.positions = USE_DEMO_POSITIONS_WHEN_EMPTY
      ? structuredClone(demoPositions)
      : [];

    renderPortfolio();
    renderSellOptions();
    showToast(
      USE_DEMO_POSITIONS_WHEN_EMPTY
        ? "Backend returned no positions; showing demo data."
        : "Could not load real positions.",
    );
  }
}

function createPortfolioRow(position) {
  const row = document.createElement("button");
  row.className = `share-row portfolio-item ${position.ticker === state.ticker ? "active-stock" : ""}`;
  row.dataset.ticker = position.ticker;
  row.dataset.name = position.name;
  row.dataset.sector = position.sector;
  row.dataset.tradeId = position.trade_id || "";

  row.innerHTML = `
    <div class="company-cell">
      <div class="company-logo-wrap">
        <img
          class="company-logo-img"
          src="${position.logoUrl}"
          alt="${position.ticker} logo"
          loading="lazy"
          onerror="this.style.display='none'; this.nextElementSibling.style.display='grid';"
        />
        <div class="company-logo-fallback ${portfolioGetTickerClass(position.ticker)}" style="display: none;">
          ${position.logo}
        </div>
      </div>

      <span>${position.name} (${position.ticker})</span>
    </div>

    <span>${portfolioMoney(position.buy_price)}</span>
    <span>${portfolioMoney(position.current_price)}</span>
    <span class="${position.pnl_dollars >= 0 ? "profit-pill" : "loss-pill"}">
      ${portfolioPct(position.pnl_pct)} / ${portfolioMoney(position.pnl_dollars)}
    </span>
  `;

  row.addEventListener("click", () => {
    document
      .querySelectorAll(".portfolio-item")
      .forEach((item) => item.classList.remove("active-stock"));
    row.classList.add("active-stock");

    state.ticker = position.ticker;
    state.chartKind = "ticker";

    document
      .querySelectorAll(".balance-mode-button")
      .forEach((button) => button.classList.remove("active"));

    document.getElementById("chartTicker").textContent = state.ticker;
    document.getElementById("sharesHint").textContent = `(${state.ticker})`;

    renderCurrentChart();
  });

  return row;
}

function renderPortfolio() {
  const container = document.getElementById("sharesScroll");
  if (!container) return;

  const positions = state.positions.map(normalizePosition);
  container.replaceChildren();
  positions.forEach((position) => container.appendChild(createPortfolioRow(position)));
}

function renderSellOptions() {
  const select = document.getElementById("sellAssetSelect");
  if (!select) return;

  select.replaceChildren();
  state.positions.map(normalizePosition).forEach((position) => {
    const option = document.createElement("option");
    option.value = position.trade_id || "";
    option.textContent = `${position.ticker} - ${position.name} · ${position.shares} shares`;
    option.dataset.ticker = position.ticker;
    select.appendChild(option);
  });
}

function initPortfolioSearch() {
  const searchInput = document.getElementById("sharesSearch");
  if (!searchInput) return;

  searchInput.addEventListener("input", (event) => {
    const query = event.target.value.toLowerCase().trim();

    document.querySelectorAll(".portfolio-item").forEach((item) => {
      const matches =
        item.dataset.ticker.toLowerCase().includes(query) ||
        item.dataset.name.toLowerCase().includes(query) ||
        item.dataset.sector.toLowerCase().includes(query) ||
        item.textContent.toLowerCase().includes(query);

      item.style.display = matches ? "grid" : "none";
    });
  });
}
