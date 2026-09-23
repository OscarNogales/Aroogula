"use strict";

// Ticker candlestick chart rendering.

function setTickerHeaderVisible(visible) {
  const ohlc = document.querySelector(".ohlc");
  if (ohlc) ohlc.style.display = visible ? "flex" : "none";
}

function updateLatestOhlc(candle) {
  if (!candle) return;

  document.getElementById("openPrice").textContent = Number(
    candle.open,
  ).toFixed(2);
  document.getElementById("highPrice").textContent = Number(
    candle.high,
  ).toFixed(2);
  document.getElementById("lowPrice").textContent = Number(candle.low).toFixed(
    2,
  );
  document.getElementById("closePrice").textContent = Number(
    candle.close,
  ).toFixed(2);
  document.getElementById("closePrice").className =
    candle.close >= candle.open ? "green-text" : "red-text";
}

function updateVolumeLabel(value, formatter) {
  if (!Number.isFinite(Number(value))) return;
  document.getElementById("volumeLabel").textContent = formatter.format(
    Number(value),
  );
}

async function restoreTickerChartAddons() {
  const restoreEma = state.indicators.ema20;
  const restoreVolume = state.indicators.lowerPanel === "volume";

  if (restoreEma) {
    await ema20();
  }

  const volumeLabelContainer = document.getElementById("volumeLabelContainer");
  if (restoreVolume) {
    await volumeSeriesGraph();
  } else if (volumeLabelContainer) {
    volumeLabelContainer.hidden = true;
  }

  if (typeof renderActiveTechnicalIndicators === "function") {
    renderActiveTechnicalIndicators();
  }
}

async function loadCandles(ticker, timeframe) {
  state.chartKind = "ticker";
  document.getElementById("chartTicker").textContent = ticker;
  document.getElementById("chartTimeframe").textContent =
    timeframe.toUpperCase();
  document.getElementById("chartModeLabel").textContent = "Price";
  setTickerHeaderVisible(true);

  try {
    const response = await apiPost("/api/graphs/ticker_graph", {
      ticker,
      period: timeframe,
      mean: false,
    });

    const candles = normalizeTickerCandles(response);
    if (!candles.length) {
      setChartMessage(`No valid candles were returned for ${ticker}.`);
      return;
    }

    state.candles = candles;
    const chart = createBaseChart();
    activeSeries = addCandlestickSeriesCompat(chart, {
      upColor: "#24d26c",
      downColor: "#f15b5b",
      borderUpColor: "#24d26c",
      borderDownColor: "#f15b5b",
      wickUpColor: "#24d26c",
      wickDownColor: "#f15b5b",
    });
    activeSeries.setData(candles);

    await restoreTickerChartAddons();

    const volumeFormatter = new Intl.NumberFormat("en-US", {
      notation: "compact",
      maximumFractionDigits: 1,
    });

    const latest = candles[candles.length - 1];
    updateLatestOhlc(latest);
    if (volumeSeries !== null) updateVolumeLabel(latest.volume, volumeFormatter);

    chart.subscribeCrosshairMove((param) => {
      if (!param.time || !activeSeries) return;
      const candle = param.seriesData.get(activeSeries);
      if (!candle || candle.open === undefined) return;

      updateLatestOhlc(candle);
      if (volumeSeries !== null) {
        const volumePoint = param.seriesData.get(volumeSeries);
        if (volumePoint && volumePoint.value !== undefined) {
          updateVolumeLabel(volumePoint.value, volumeFormatter);
        }
      }
    });

    chart.timeScale().fitContent();
  } catch (error) {
    console.error("Error rendering ticker chart:", error);
    setChartMessage(
      `Could not load ${ticker}.<br><small>${String(error)}</small>`,
    );
  }
}
