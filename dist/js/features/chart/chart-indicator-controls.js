"use strict";

// ============================================================
// 1. EMA 20 CONTROL
// ============================================================

async function ema20() {
  const ticker = state.ticker;
  const timeframe = state.timeframe;

  if (state.chartKind !== "ticker") {
    showToast("MA 20 is available only for ticker charts.");
    return;
  }

  const response = await apiPost("/api/graphs/ticker_graph", {
    ticker,
    period: timeframe,
    mean: true,
  });

  const emaPoints = response.Date.map((date, index) => ({
    time: parseChartTime(date, index),
    value: Number(response.EMA_20[index]),
  })).filter((point) => Number.isFinite(point.value));

  ema20Series = addLineSeriesCompat(chartElement, {
    lineWidth: 2,
    color: "#277DF5",
    title: "EMA 20",
  });

  ema20Series.setData(emaPoints);
}

function removeEma20() {
  if (chartElement && ema20Series) {
    chartElement.removeSeries(ema20Series);
  }

  ema20Series = null;
}

async function toggleEma20() {
  if (state.indicators.ema20 === false) {
    await ema20();
    state.indicators.ema20 = true;
    return;
  }

  state.indicators.ema20 = false;
  removeEma20();
}


// ============================================================
// 2. VOLUME CONTROL
// ============================================================

async function volumeSeriesGraph() {
  const ticker = state.ticker;
  const period = state.timeframe;

  if (state.chartKind !== "ticker") {
    showToast("Volume is available only for ticker charts.");
    return;
  }

  const response = await apiPost("/api/graphs/ticker_graph", {
    ticker,
    period,
    mean: false,
  });

  const volumePoints = response.Date.map((date, index) => ({
    time: parseChartTime(date, index),
    value: Number(response.Volume[index]),
  })).filter((point) => Number.isFinite(point.value));

  volumeSeries = addHistogramSeriesCompat(chartElement, {
    color: "#24d26c",
    priceFormat: {
      type: "volume",
    },
    priceScaleId: "",
  });

  volumeSeries.setData(volumePoints);

  const volumeLabelContainer = document.getElementById("volumeLabelContainer");
  if (volumeLabelContainer) {
    volumeLabelContainer.hidden = false;
  }

  volumeSeries.priceScale().applyOptions({
    scaleMargins: {
      top: 0.7,
      bottom: 0,
    },
  });
}

async function toggleVolumePanel() {
  if (state.chartKind !== "ticker") {
    showToast("Volume chart is only available for ticker graphs.");
    return;
  }

  const nextPanel = state.indicators.lowerPanel === "volume" ? null : "volume";
  await setLowerPanel(nextPanel);
}


// ============================================================
// 3. SPY DATA FETCHING
// ============================================================

async function fetchSPYCandles() {
  const response = await apiPost("/api/graphs/ticker_graph", {
    ticker: "SPY",
    period: state.timeframe,
    mean: false,
  });

  return normalizeTickerCandles(response);
}


// ============================================================
// 4. TIME + VALUE NORMALIZATION HELPERS
// ============================================================

function toUnixSeconds(time) {
  if (time === null || time === undefined) {
    return null;
  }

  if (typeof time === "number") {
    return time > 1_000_000_000_000
      ? Math.floor(time / 1000)
      : Math.floor(time);
  }

  if (
    typeof time === "object" &&
    "year" in time &&
    "month" in time &&
    "day" in time
  ) {
    return Math.floor(
      Date.UTC(time.year, time.month - 1, time.day) / 1000,
    );
  }

  const parsed = Date.parse(String(time));

  if (Number.isNaN(parsed)) {
    return null;
  }

  return Math.floor(parsed / 1000);
}

function getPointValue(point, valueKeys) {
  const keys = Array.isArray(valueKeys) ? valueKeys : [valueKeys];

  for (const key of keys) {
    const value = Number(point?.[key]);

    if (Number.isFinite(value)) {
      return value;
    }
  }

  return null;
}

function normalizeRawSeries(points, valueKeys) {
  if (!Array.isArray(points) || points.length === 0) {
    return [];
  }

  return points
    .map((point) => {
      const time = toUnixSeconds(
        point.time ??
        point.timestamp ??
        point.datetime ??
        point.Date ??
        point.Datetime,
      );

      const rawValue = getPointValue(point, valueKeys);

      if (time === null || !Number.isFinite(rawValue)) {
        return null;
      }

      return {
        time,
        rawValue,
      };
    })
    .filter(Boolean)
    .sort((a, b) => a.time - b.time);
}

function getMaxLagSecondsForTimeframe(timeframe) {
  const lagByTimeframe = {
    "1d": 20 * 60,
    "5d": 60 * 60,
    "1mo": 3 * 60 * 60,
    "3mo": 3 * 60 * 60,
    "6mo": 4 * 60 * 60,
    "1y": 4 * 24 * 60 * 60,
    "2y": 4 * 24 * 60 * 60,
    "5y": 4 * 24 * 60 * 60,
    "10y": 4 * 24 * 60 * 60,
    "ytd": 4 * 24 * 60 * 60,
    "max": 7 * 24 * 60 * 60,
  };

  return lagByTimeframe[timeframe] ?? 24 * 60 * 60;
}


// ============================================================
// 5. BOT/SPY SERIES ALIGNMENT
// ============================================================

function alignByPreviousCandle(botRawSeries, spyRawSeries, maxLagSeconds) {
  const bot = [];
  const spy = [];

  if (!botRawSeries.length || !spyRawSeries.length) {
    return { bot, spy };
  }

  let spyIndex = 0;

  for (const botPoint of botRawSeries) {
    while (
      spyIndex + 1 < spyRawSeries.length &&
      spyRawSeries[spyIndex + 1].time <= botPoint.time
    ) {
      spyIndex += 1;
    }

    const spyPoint = spyRawSeries[spyIndex];

    if (!spyPoint) {
      continue;
    }

    const lagSeconds = botPoint.time - spyPoint.time;

    if (lagSeconds < 0 || lagSeconds > maxLagSeconds) {
      continue;
    }

    bot.push({
      time: botPoint.time,
      rawValue: botPoint.rawValue,
    });

    spy.push({
      time: botPoint.time,
      rawValue: spyPoint.rawValue,
    });
  }

  return { bot, spy };
}

function convertAlignedRawValuesToReturns(aligned) {
  if (!aligned.bot.length || !aligned.spy.length) {
    return {
      botPoints: [],
      spyPoints: [],
    };
  }

  const baseBot = aligned.bot[0].rawValue;
  const baseSPY = aligned.spy[0].rawValue;

  if (
    !Number.isFinite(baseBot) ||
    !Number.isFinite(baseSPY) ||
    baseBot === 0 ||
    baseSPY === 0
  ) {
    return {
      botPoints: [],
      spyPoints: [],
    };
  }

  const botPoints = aligned.bot.map((point) => ({
    time: point.time,
    value: Number(((point.rawValue / baseBot - 1) * 100).toFixed(4)),
  }));

  const spyPoints = aligned.spy.map((point) => ({
    time: point.time,
    value: Number(((point.rawValue / baseSPY - 1) * 100).toFixed(4)),
  }));

  return {
    botPoints,
    spyPoints,
  };
}

// ============================================================
// 6. EQUITY RESPONSE EXTRACTION
// ============================================================

function extractEquityPoints(response) {
  const payload =
    typeof unwrapResponse === "function"
      ? unwrapResponse(response)
      : response?.data ?? response?.payload ?? response;

  if (Array.isArray(payload)) {
    return payload;
  }

  return (
    payload?.points ??
    payload?.equity_points ??
    payload?.data?.points ??
    []
  );
}


// ============================================================
// 7. BOT VS SPY CHART
// ============================================================

function graphEquityVsSPYChart(aligned) {
  if (!aligned.botPoints.length || !aligned.spyPoints.length) {
    showToast("❌ Could not align Bot equity with SPY data.");
    return;
  }
  setTickerHeaderVisible(false);
  document.getElementById("chartModeLabel").textContent = "Bot vs SPY";

  const equityLine = addLineSeriesCompat(chartElement, {
    title: "Bot Equity",
    lineWidth: 3,
    color: state.color || "#22c55e",
    priceFormat: {
      type: "custom",
      formatter: (value) => pct(value),
    },
  });

  const spyLine = addLineSeriesCompat(chartElement, {
    title: "SPY",
    lineWidth: 2,
    color: INDICATOR_COLORS.spy || "#94a3b8",
    priceFormat: {
      type: "custom",
      formatter: (value) => pct(value),
    },
  });

  equityLine.setData(aligned.botPoints);
  spyLine.setData(aligned.spyPoints);

  chart.timeScale().fitContent();
}

async function loadEquityVsSPYChart() {
  const equityResponse = await apiGet(
    `/api/portfolio/equity?timeframe=${state.timeframe}`,
    {
      status: "error",
      data: { points: [] },
    },
  );

  const equityPoints = extractEquityPoints(equityResponse);

  if (!equityPoints.length) {
    showToast("❌ No equity data available.");
    return;
  }

  const spyCandles = await fetchSPYCandles();

  if (!spyCandles.length) {
    showToast("❌ No SPY data available.");
    return;
  }

  const botRawSeries = normalizeRawSeries(
    equityPoints,
    ["equity", "total_equity", "value"],
  );

  const spyRawSeries = normalizeRawSeries(
    spyCandles,
    ["close", "Close", "value"],
  );

  const maxLagSeconds = getMaxLagSecondsForTimeframe(state.timeframe);

  const alignedRaw = alignByPreviousCandle(
    botRawSeries,
    spyRawSeries,
    maxLagSeconds,
  );

  const alignedReturns = convertAlignedRawValuesToReturns(alignedRaw);

  console.log("Equity points:", equityPoints);
  console.log("SPY candles:", spyCandles);
  console.log("Bot raw series:", botRawSeries);
  console.log("SPY raw series:", spyRawSeries);
  console.log("Aligned raw:", alignedRaw);
  console.log("Aligned returns:", alignedReturns);

  if (!alignedReturns.botPoints.length || !alignedReturns.spyPoints.length) {
    showToast("❌ Could not align Bot equity with SPY data.");
    return;
  }

  graphEquityVsSPYChart(alignedReturns);
}


// ============================================================
// 8. SPY COMPARISON TOGGLE
// ============================================================

async function toggleEquityVsSPY() {
  if (state.chartKind !== "portfolio" || state.mode !== "equity") {
    return;
  }

  state.compareWithSPY = !Boolean(state.compareWithSPY);

  const equityVsSPYButton = document.getElementById("spy_compare_button");
  equityVsSPYButton?.classList.toggle("active", state.compareWithSPY);

  if (typeof updateButtons === "function") {
    updateButtons();
  }

  if (state.compareWithSPY) {
    await loadEquityVsSPYChart();
    return;
  }

  await loadEquityChart();
}


// ============================================================
// 9. INITIALIZATION
// ============================================================

function initChartIndicatorControls() {
  const ma20Button = document.getElementById("moving_average_button");
  const volumeButton = document.getElementById("volume_button");
  const equityVsSPYButton = document.getElementById("spy_compare_button");

  ma20Button?.addEventListener("click", toggleEma20);
  volumeButton?.addEventListener("click", toggleVolumePanel);
  equityVsSPYButton?.addEventListener("click", toggleEquityVsSPY);
}

Object.assign(window, {
  toggleEma20,
  toggleVolumePanel,
  toggleEquityVsSPY,
  loadEquityVsSPYChart,
});

initChartIndicatorControls();