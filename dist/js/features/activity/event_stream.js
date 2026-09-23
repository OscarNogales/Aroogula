"use strict";

let botEventSource = null;

function activityFromPayload(type, payload = {}) {
  const eventType =
    type === "trade_executed"
      ? payload.side || "BUY"
      : type === "risk_halt"
        ? "RISK"
        : type === "ai_error"
          ? "ERROR"
          : type === "cycle_complete"
            ? "SCAN"
            : "AI";

  return {
    type: eventType,
    ticker: payload.ticker || "--",
    title: payload.title || payload.message || type,
    summary:
      payload.summary ||
      payload.reason ||
      payload.reasoning ||
      payload.message ||
      "",
    ttl_seconds: payload.ttl_seconds ?? 30,
  };
}

function startBusyStatusDot() {
  const statusDot = document.getElementById("bot-status-dot");
  statusDot.classList.add("busy");
}

function stopBusyStatusDot() {
  const statusDot = document.getElementById("bot-status-dot");
  statusDot.classList.remove("busy");
}

async function refreshTradingViews() {
  await Promise.all([
    fetchEquitySummary(),
    loadPortfolio(),
    loadTradeJournal(),
  ]);

  if (state.chartKind === "portfolio") {
    await loadEquityChart();
  }
}

function renderCycleSummaryFromEvent(payload = {}) {
  const summary = payload.cycle_summary || {};

  addActivityEvent({
    type: "SCAN",
    ticker: "--",
    title: "News check completed",
    summary:
      `Scanned: ${summary.news_scanned ?? 0} | ` +
      `FinBERT rejected: ${summary.finbert_rejected ?? 0} | ` +
      `LLM wait: ${summary.llm_wait ?? 0} | ` +
      `Buys: ${summary.buys_executed ?? 0} | ` +
      `Errors: ${summary.errors ?? 0}`,
    ttl_seconds: 45,
  });
}

function connectBotEventStream() {
  if (botEventSource) {
    return botEventSource;
  }

  const source = new EventSource("/api/events/stream");
  botEventSource = source;

  source.addEventListener("cycle_started", (event) => {
    const botEvent = JSON.parse(event.data);

    addActivityEvent({
      type: "SCAN",
      ticker: "--",
      title: "News check started",
      summary: botEvent.payload?.message || "AI is scanning news.",
      ttl_seconds: 20,
    });

    startBusyStatusDot();

  });

  

  source.addEventListener("risk_check_started", (event) => {
    const botEvent = JSON.parse(event.data);
    const payload = botEvent.payload || {};

    addActivityEvent({
      type: "RISK",
      ticker: "--",
      title: "Checking positions",
      summary: payload.message || "Risk engine is checking open positions.",
      ttl_seconds: 15,
    });

    startBusyStatusDot();
  });

  source.addEventListener("risk_check_completed", async (event) => {
    const botEvent = JSON.parse(event.data);
    const payload = botEvent.payload || {};

    addActivityEvent({
      type: "RISK",
      ticker: "--",
      title: "Risk check completed",
      summary: payload.message || "Position check finished.",
      ttl_seconds: 30,
    });
    stopBusyStatusDot();
    await refreshTradingViews();
    await loadScheduler();
  });

  source.addEventListener("ai_activity", (event) => {
    const botEvent = JSON.parse(event.data);
    addActivityEvent(activityFromPayload("ai_activity", botEvent.payload));
  });

  source.addEventListener("finbert_approved", (event) => {
    const botEvent = JSON.parse(event.data);

    addActivityEvent({
      type: "AI",
      ticker: botEvent.payload?.ticker || "--",
      title: "FinBERT approved",
      summary: botEvent.payload?.message || "News passed FinBERT filter.",
      ttl_seconds: 25,
    });
  });

  source.addEventListener("ai_rejected_batch", (event) => {
    const botEvent = JSON.parse(event.data);

    addActivityEvent({
      type: "WAIT",
      ticker: "--",
      title: botEvent.payload?.kind === "llm" ? "LLM rejected batch" : "FinBERT rejected batch",
      summary: botEvent.payload?.message || "Rejected batch received.",
      ttl_seconds: 30,
    });
  });

  source.addEventListener("llm_started", (event) => {
    const botEvent = JSON.parse(event.data);

    addActivityEvent({
      type: "AI",
      ticker: botEvent.payload?.ticker || "--",
      title: "LLM analyzing",
      summary: botEvent.payload?.message || "Running deeper AI decision.",
      ttl_seconds: 20,
    });
  });

  source.addEventListener("llm_completed", (event) => {
    const botEvent = JSON.parse(event.data);
    const payload = botEvent.payload || {};

    addActivityEvent({
      type: payload.signal === "BUY" ? "BUY" : "WAIT",
      ticker: payload.ticker || "--",
      title: `LLM decided ${payload.signal || "WAIT"}`,
      summary: `Confidence: ${payload.confidence ?? "--"}`,
      ttl_seconds: 30,
    });
  });

  source.addEventListener("trade_executed", async (event) => {
    const botEvent = JSON.parse(event.data);
    const payload = botEvent.payload || {};

    addActivityEvent({
      type: payload.side || "BUY",
      ticker: payload.ticker || "--",
      title: `${payload.side || "BUY"} executed`,
      summary:
        `Confidence: ${payload.confidence ?? "--"} | ` +
        `${payload.reasoning || payload.message || ""}`,
      ttl_seconds: 60,
    });

    await refreshTradingViews();
  });

  source.addEventListener("portfolio_changed", async () => {
    await refreshTradingViews();
    await loadScheduler();
  });

  source.addEventListener("risk_halt", (event) => {
    const botEvent = JSON.parse(event.data);

    addActivityEvent({
      type: "RISK",
      ticker: "--",
      title: "RiskGuard halted buys",
      summary: botEvent.payload?.reason || botEvent.payload?.message || "Risk halt.",
      ttl_seconds: 60,
    });
  });

  source.addEventListener("ai_error", (event) => {
    const botEvent = JSON.parse(event.data);

    addActivityEvent({
      type: "ERROR",
      ticker: botEvent.payload?.ticker || "--",
      title: "AI pipeline error",
      summary: botEvent.payload?.message || "Unknown error.",
      ttl_seconds: 60,
    });
  });

  source.addEventListener("cycle_complete", async (event) => {
    const botEvent = JSON.parse(event.data);

    renderCycleSummaryFromEvent(botEvent.payload);
    await refreshTradingViews();
    await loadScheduler();
    stopBusyStatusDot();
  });

  

  source.onerror = (error) => {
    console.warn("Bot event stream disconnected or unavailable.", error);
  };

  console.log("Bot event stream connected.");
  return source;
}