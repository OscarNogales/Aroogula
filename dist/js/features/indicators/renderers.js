"use strict";

// Technical indicator renderers.
// These functions only draw on the chart. They do not calculate indicator values.

let rsiSeries = null;
let atrSeries = null;

const bollingerSeries = {
  upper: null,
  middle: null,
  lower: null,
};

const macdSeries = {
  macd: null,
  signal: null,
  histogram: null,
};

function resetIndicatorSeries() {
  rsiSeries = null;
  atrSeries = null;
  bollingerSeries.upper = null;
  bollingerSeries.middle = null;
  bollingerSeries.lower = null;
  macdSeries.macd = null;
  macdSeries.signal = null;
  macdSeries.histogram = null;
}

function applyLowerPanelPriceScale(scaleId) {
  if (!chartElement) return;

  const options = buildPriceScaleOptions(scaleId);

  chartElement.priceScale("right").applyOptions(options.mainScale);
  chartElement.priceScale(scaleId).applyOptions(options.indicatorScale);
}

function renderRSI(rsiData) {
  if (!chartElement || !Array.isArray(rsiData) || rsiData.length === 0) return;

  rsiSeries = addLineSeriesCompat(chartElement, {
    title: "RSI 14",
    lineWidth: 2,
    color: INDICATOR_COLORS.rsi,
    priceScaleId: "rsi",
    priceFormat: INDICATOR_PRICE_FORMAT,
  });

  rsiSeries.setData(rsiData);
  applyLowerPanelPriceScale("rsi");

  rsiSeries.createPriceLine({
    price: 70,
    color: "#8d8d96",
    lineWidth: 1,
    lineStyle: LightweightCharts.LineStyle.Dashed,
    axisLabelVisible: true,
    title: "Overbought",
  });

  rsiSeries.createPriceLine({
    price: 30,
    color: "#8d8d96",
    lineWidth: 1,
    lineStyle: LightweightCharts.LineStyle.Dashed,
    axisLabelVisible: true,
    title: "Oversold",
  });
}

function renderBollinger(bollingerData) {
  if (!chartElement || !bollingerData) return;

  const bandConfig = {
    upper: {
      title: "Bollinger upper",
      color: INDICATOR_COLORS.bollingerUpper,
    },
    middle: {
      title: "Bollinger middle",
      color: INDICATOR_COLORS.bollingerMiddle,
    },
    lower: {
      title: "Bollinger lower",
      color: INDICATOR_COLORS.bollingerLower,
    },
  };

  Object.entries(bandConfig).forEach(([key, config]) => {
    if (!Array.isArray(bollingerData[key]) || bollingerData[key].length === 0)
      return;

    bollingerSeries[key] = addLineSeriesCompat(chartElement, {
      title: config.title,
      color: config.color,
      lineWidth: 1,
      priceFormat: INDICATOR_PRICE_FORMAT,
    });

    bollingerSeries[key].setData(bollingerData[key]);
  });
}

function renderMACD(macdData) {
  if (!chartElement || !macdData) return;

  macdSeries.macd = addLineSeriesCompat(chartElement, {
    title: "MACD",
    lineWidth: 2,
    color: INDICATOR_COLORS.macd,
    priceScaleId: "macd",
    priceFormat: INDICATOR_PRICE_FORMAT,
  });
  macdSeries.macd.setData(macdData.macd || []);

  macdSeries.signal = addLineSeriesCompat(chartElement, {
    title: "Signal",
    lineWidth: 2,
    color: INDICATOR_COLORS.signal,
    priceScaleId: "macd",
    priceFormat: INDICATOR_PRICE_FORMAT,
  });
  macdSeries.signal.setData(macdData.signal || []);

  macdSeries.histogram = addHistogramSeriesCompat(chartElement, {
    title: "Histogram",
    color: INDICATOR_COLORS.histogram,
    priceScaleId: "macd",
    priceFormat: INDICATOR_PRICE_FORMAT,
  });
  macdSeries.histogram.setData(macdData.histogram || []);

  applyLowerPanelPriceScale("macd");
}

function renderATR(atrData) {
  if (!chartElement || !Array.isArray(atrData) || atrData.length === 0) return;

  atrSeries = addLineSeriesCompat(chartElement, {
    title: "ATR 14",
    lineWidth: 2,
    color: INDICATOR_COLORS.atr,
    priceScaleId: "atr",
    priceFormat: INDICATOR_PRICE_FORMAT,
  });

  atrSeries.setData(atrData);
  applyLowerPanelPriceScale("atr");
}
