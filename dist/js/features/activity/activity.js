"use strict";

// Scheduler, live activity, trade journal, drawer, and trade modal.
// Keep list rendering synchronous; only the modal awaits backend-only details.


// Local compatibility wrappers.
// They prevent this file from crashing if the browser cached an older helpers.js.
const activityNormalizeTicker = (value) => {
  if (typeof window.normalizeTicker === "function") return window.normalizeTicker(value);
  return String(value || "").trim().toUpperCase();
};

const activityFormatDateTime = (value) => {
  if (typeof window.formatDateTime === "function") return window.formatDateTime(value);
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
};

const activityMoney = (value) => {
  if (typeof window.money === "function") return window.money(value);
  const numeric = Number(value || 0);
  const sign = numeric < 0 ? "-" : "";
  return `${sign}$${Math.abs(numeric).toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
};

const activityPct = (value) => {
  if (typeof window.pct === "function") return window.pct(value);
  const numeric = Number(value || 0);
  const sign = numeric >= 0 ? "+" : "";
  return `${sign}${numeric.toFixed(2)}%`;
};

async function activityFetchCompanyProfile(ticker) {
  const cleanTicker = activityNormalizeTicker(ticker);

  if (typeof window.fetchCompanyProfile === "function") {
    return window.fetchCompanyProfile(cleanTicker);
  }

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
    logo: cleanTicker.slice(0, 2),
  };
}

// Scheduler status panel.

function schedulerJobByIdOrLabel(jobs, id, labelFragment) {
  return (
    jobs.find((job) => job.id === id) ||
    jobs.find((job) => String(job.label || "").includes(labelFragment)) ||
    null
  );
}

async function loadScheduler() {
  const result = await apiGet("/api/scheduler/status", demoScheduler);
  const data = result.data || result;

  const botStatusLabel = document.getElementById("botStatusLabel");
  if (botStatusLabel) botStatusLabel.textContent = data.bot_status || "PAUSED";

  if (data.bot_status === "ACTIVE") {
    const startStopBtn = document.getElementById("startStopBtn");
    startStopBtn.classList.add("on-btn");
    startStopBtn.textContent = "STOP NEWS BOT";
    showToast("🤖 News Bot: ON");
  } else {
    showToast("🤖 News Bot: PAUSED");
  }

  const statusDot = document.getElementById("bot-status-dot");
  if (statusDot) {
    const isActive = data.bot_status === "ACTIVE";
    statusDot.classList.toggle("on", isActive);
    statusDot.classList.toggle("off", !isActive);
  }

  const jobs = data.jobs || [];
  const nextNews = schedulerJobByIdOrLabel(jobs, "check_news_loop", "News");
  const nextRisk = schedulerJobByIdOrLabel(jobs, "check_stock_loop", "Risk");

  const nextNewsLabel = document.getElementById("nextNewsLabel");
  const nextRiskLabel = document.getElementById("nextRiskLabel");
  if (nextNewsLabel) nextNewsLabel.textContent = activityFormatDateTime(nextNews?.next_run_time);
  if (nextRiskLabel) nextRiskLabel.textContent = activityFormatDateTime(nextRisk?.next_run_time);

  const rows = document.getElementById("schedulerRows");
  if (!rows) return;

  rows.innerHTML = jobs
    .map(
      (job) => `
        <div class="schedule-row">
          <b>${job.label || job.id}</b>
          <span>${activityFormatDateTime(job.next_run_time)}</span>
          <span class="pill ${job.status === "paused" ? "pill-warning" : "pill-success"}">${job.status || "scheduled"}</span>
        </div>
      `,
    )
    .join("");
}

const schedulerBtn = document.getElementById("schedulerBtn");
if (schedulerBtn) {
  schedulerBtn.addEventListener("click", () => {
    document.getElementById("schedulerPopover")?.classList.toggle("open");
  });
}

// Live activity and trade journal rendering.

function badgeForType(type) {
  const normalized = String(type || "").toUpperCase();
  if (normalized === "BUY") return `<span class="pill pill-success">BUY</span>`;
  if (normalized === "SELL") return `<span class="pill pill-danger">SELL</span>`;
  if (normalized === "RISK") return `<span class="pill pill-warning">RISK</span>`;
  if (normalized === "LIQUIDATE") return `<span class="pill pill-danger">LIQ</span>`;
  if (normalized === "WAIT") return `<span class="pill pill-muted">WAIT</span>`;
  if (normalized === "MACRO") return `<span class="pill pill-warning">MACRO</span>`;
  if (normalized === "ERROR") return `<span class="pill pill-danger">ERR</span>`;
  return `<span class="pill pill-muted">${normalized.slice(0, 5) || "LOG"}</span>`;
}

function normalizeTradeType(trade) {
  return String(trade?.type || trade?.action || "RISK").toUpperCase();
}

function tradeReason(trade) {
  return (
    trade.reasoning ||
    trade.news_summary ||
    trade.buy_reason ||
    trade.sell_reason ||
    trade.exit_trigger ||
    trade.summary ||
    ""
  );
}

function tradeTitle(type) {
  if (type === "BUY") return "Position opened";
  if (type === "SELL") return "Position closed";
  if (type === "LIQUIDATE") return "Position liquidated";
  return "Risk action";
}

async function loadActivity() {
  const result = await apiGet("/api/events/live", {
    status: "success",
    data: { events: [] },
  });
  state.activityEvents = result.data?.events || result.events || [];
  renderActivity();
}

function activityRow(event) {
  const row = document.createElement("div");
  row.className = "activity-event";
  row.dataset.id = event.id;
  row.innerHTML = `
    ${badgeForType(event.type)}
    <div class="event-main">
      <div class="event-title">
        <span>${event.ticker || "--"}</span>
        <span>${event.title || "Activity"}</span>
      </div>
      <div class="event-summary">${event.summary || ""}</div>
    </div>
    <span class="event-time">${event.time || "now"}</span>
  `;

  if (event.ttl_seconds) {
    setTimeout(() => {
      row.classList.add("fading");
      setTimeout(() => row.remove(), 720);
    }, event.ttl_seconds * 1000);
  }

  return row;
}

function renderActivity() {
  const container = document.getElementById("activityScroll");
  if (!container) return;

  container.replaceChildren();
  state.activityEvents.forEach((event) => container.appendChild(activityRow(event)));
}

function addActivityEvent(event) {
  const newEvent = {
    id: `ACT-${Date.now()}`,
    time: "Now",
    ...event,
  };

  state.activityEvents.unshift(newEvent);

  const container = document.getElementById("activityScroll");
  if (container) container.prepend(activityRow(newEvent));
}

async function loadTradeJournal() {
  const result = await apiGet("/api/trade-journal", {
    status: "success",
    data: { trades: [] },
  });

  state.tradeJournal = result.data?.trades ?? result.trades ?? [];
  renderTradeJournal();
  renderJournalDrawer();
}

function renderTradeJournal() {
  const container = document.getElementById("tradeJournalScroll");
  if (!container) return;

  container.replaceChildren();
  state.tradeJournal.forEach((trade) => {
    container.appendChild(createJournalRow(trade));
  });
}

function createJournalRow(trade) {
  const type = normalizeTradeType(trade);
  const ticker = activityNormalizeTicker(trade.ticker) || "--";
  const row = document.createElement("button");
  row.className = "journal-row";
  row.dataset.type = type;
  row.dataset.ticker = ticker;

  row.innerHTML = `
    ${badgeForType(type)}
    <div class="journal-main">
      <div class="journal-title">
        <span>${ticker}</span>
        <span>${tradeTitle(type)}</span>
      </div>
      <div class="journal-summary">${tradeReason(trade)}</div>
    </div>
    <span class="journal-time">${activityFormatDateTime(trade.timestamp)}</span>
  `;

  row.addEventListener("click", () => openTradeModal({ ...trade, type, ticker }));
  return row;
}

// Activity tabs.

document.querySelectorAll("[data-activity-view]").forEach((button) => {
  button.addEventListener("click", () => {
    document
      .querySelectorAll("[data-activity-view]")
      .forEach((btn) => btn.classList.remove("active"));
    button.classList.add("active");

    const view = button.dataset.activityView;
    document.getElementById("liveActivitySection")?.classList.toggle("active", view === "live");
    document.getElementById("tradeJournalSection")?.classList.toggle("active", view === "journal");
  });
});

// Full trade-journal drawer.

const drawerOverlay = document.getElementById("drawerOverlay");
const journalDrawer = document.getElementById("journalDrawer");

function openDrawer() {
  drawerOverlay?.classList.add("open");
  journalDrawer?.classList.add("open");
}

function closeDrawer() {
  drawerOverlay?.classList.remove("open");
  journalDrawer?.classList.remove("open");
}

const openJournalDrawerBtn = document.getElementById("openJournalDrawer");
const closeJournalDrawerBtn = document.getElementById("closeJournalDrawer");

if (openJournalDrawerBtn) openJournalDrawerBtn.addEventListener("click", openDrawer);
if (closeJournalDrawerBtn) closeJournalDrawerBtn.addEventListener("click", closeDrawer);
if (drawerOverlay) drawerOverlay.addEventListener("click", closeDrawer);

function renderJournalDrawer(filter = "ALL") {
  const body = document.getElementById("journalDrawerBody");
  if (!body) return;

  body.replaceChildren();

  state.tradeJournal
    .filter((trade) => filter === "ALL" || normalizeTradeType(trade) === filter)
    .forEach((trade) => body.appendChild(createJournalRow(trade)));
}

document.querySelectorAll(".journal-filter").forEach((button) => {
  button.addEventListener("click", () => {
    document
      .querySelectorAll(".journal-filter")
      .forEach((btn) => btn.classList.remove("active"));
    button.classList.add("active");
    renderJournalDrawer(button.dataset.journalFilter);
  });
});

// Trade detail modal.

const modalOverlay = document.getElementById("tradeModalOverlay");

function setModalBadge(type) {
  const badge = document.getElementById("modalBadge");
  if (!badge) return;

  const normalized = String(type || "BUY").toUpperCase();
  badge.className = "decision-badge";

  if (normalized === "BUY") badge.classList.add("buy");
  else if (normalized === "SELL") badge.classList.add("sell");
  else if (normalized === "RISK") badge.classList.add("risk");
  else badge.classList.add("liquidate");

  badge.textContent = normalized;
}

function setModalText(id, value) {
  const element = document.getElementById(id);
  if (element) element.textContent = value ?? "--";
}

function setSignedClass(id, value) {
  const element = document.getElementById(id);
  if (!element) return;

  element.classList.toggle("positive", value >= 0);
  element.classList.toggle("negative", value < 0);
}

function tradeEntryPrice(trade) {
  return Number(trade.buy_price ?? trade.entry_price ?? 0);
}

function tradeCurrentPrice(trade) {
  const entryPrice = tradeEntryPrice(trade);
  return Number(trade.current_price ?? trade.exit_price ?? entryPrice);
}

function tradePnlDollars(trade) {
  const fallback = (tradeCurrentPrice(trade) - tradeEntryPrice(trade)) * Number(trade.shares ?? 0);
  return Number(trade.gain ?? trade.pnl_dollars ?? fallback ?? 0);
}

function tradePnlPct(trade) {
  const entryPrice = tradeEntryPrice(trade);
  const fallback = ((tradeCurrentPrice(trade) - entryPrice) / Math.max(Math.abs(entryPrice), 0.01)) * 100;
  return Number(trade.pnl_pct ?? fallback ?? 0);
}

async function openTradeModal(trade) {
  const type = normalizeTradeType(trade);
  const ticker = activityNormalizeTicker(trade.ticker);
  const profile = await activityFetchCompanyProfile(ticker);

  const entryPrice = tradeEntryPrice(trade);
  const currentPrice = tradeCurrentPrice(trade);
  const pnlDollars = tradePnlDollars(trade);
  const pnlPct = tradePnlPct(trade);

  setModalText("modalTicker", ticker);
  setModalText("modalCompany", trade.company || profile.name);
  setModalText("modalBuy", activityMoney(entryPrice));
  setModalText("modalCurrent", activityMoney(currentPrice));
  setModalText("modalGain", activityMoney(pnlDollars));
  setModalText("modalPnl", activityPct(pnlPct));

  setSignedClass("modalGain", pnlDollars);
  setSignedClass("modalPnl", pnlPct);

  setModalText("modalNews", trade.news_summary || trade.summary || "No news summary attached.");
  setModalText("modalSource", `Source: ${trade.source || "AI / Risk engine"}`);
  setModalText("modalTimestamp", activityFormatDateTime(trade.timestamp));
  setModalText(
    "modalReasonTitle",
    type === "BUY"
      ? "Why the AI Bought"
      : type === "SELL"
        ? "Why the Position Was Sold"
        : "Why the Risk Engine Acted",
  );
  setModalText("modalReason", tradeReason(trade) || "No reasoning attached.");
  setModalText("modalConfidence", Number(trade.ai_confidence ?? 0).toFixed(2));

  const confidenceFill = document.getElementById("modalConfidenceFill");
  if (confidenceFill) {
    confidenceFill.style.width = `${Math.max(0, Math.min(1, Number(trade.ai_confidence ?? 0))) * 100}%`;
  }

  setModalText("modalTradeId", trade.trade_id || "--");
  setModalText("modalShares", trade.shares ?? "--");

  const currentBotSettings = await loadBotSettings();
  const targetGainPct = Number(currentBotSettings.trade_target_gain_pct ?? 0);
  const stopLossPct = Number(currentBotSettings.trade_stop_loss_pct ?? 0);

  setModalText(
    "modalStopLoss",
    trade.stop_loss ? activityMoney(trade.stop_loss) : activityMoney(entryPrice * (1 + stopLossPct)),
  );
  setModalText(
    "modalTakeProfit",
    trade.take_profit ? activityMoney(trade.take_profit) : activityMoney(entryPrice * (1 + targetGainPct)),
  );

  setModalText("modalSector", profile.sector);
  setModalText("modalCap", profile.cap);
  setModalText("modalRevenue", profile.revenue);
  setModalText("modalRisk", profile.risk);
  setModalText("modalOutlook", profile.outlook);
  setModalText("modalLogo", profile.logo);
  setModalText("modalCompanyShort", profile.short);
  setModalText("modalFounded", profile.founded);

  setModalBadge(type);
  modalOverlay?.classList.add("open");
}

function closeModal() {
  modalOverlay?.classList.remove("open");
}

const closeModalBtn = document.getElementById("closeModal");
const modalCloseBottomBtn = document.getElementById("modalCloseBottom");
const modalChartBtn = document.getElementById("modalChartBtn");

if (closeModalBtn) closeModalBtn.addEventListener("click", closeModal);
if (modalCloseBottomBtn) modalCloseBottomBtn.addEventListener("click", closeModal);
if (modalOverlay) {
  modalOverlay.addEventListener("click", (event) => {
    if (event.target === modalOverlay) closeModal();
  });
}

if (modalChartBtn) {
  modalChartBtn.addEventListener("click", () => {
    const ticker = activityNormalizeTicker(document.getElementById("modalTicker")?.textContent);
    state.ticker = ticker;
    state.chartKind = "ticker";
    document
      .querySelectorAll(".balance-mode-button")
      .forEach((btn) => btn.classList.remove("active"));
    document.getElementById("chartTicker").textContent = ticker;
    loadCandles(ticker, state.timeframe);
    closeModal();
    closeDrawer();
  });
}

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    closeModal();
    closeDrawer();
  }
});
