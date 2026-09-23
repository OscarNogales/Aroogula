"use strict";

// Lightweight Charts compatibility wrappers.
// They support both v4-style addLineSeries/addCandlestickSeries and v5 addSeries.

function addCandlestickSeriesCompat(chart, options) {
  if (
    typeof chart.addSeries === "function" &&
    LightweightCharts.CandlestickSeries
  ) {
    return chart.addSeries(LightweightCharts.CandlestickSeries, options);
  }
  if (typeof chart.addCandlestickSeries === "function") {
    return chart.addCandlestickSeries(options);
  }
  throw new Error(
    "The loaded Lightweight Charts version does not support candlesticks.",
  );
}

function addLineSeriesCompat(chart, options) {
  if (typeof chart.addSeries === "function" && LightweightCharts.LineSeries) {
    return chart.addSeries(LightweightCharts.LineSeries, options);
  }
  if (typeof chart.addLineSeries === "function") {
    return chart.addLineSeries(options);
  }
  throw new Error(
    "The loaded Lightweight Charts version does not support line series.",
  );
}

function addHistogramSeriesCompat(chart, options) {
  if (
    typeof chart.addSeries === "function" &&
    LightweightCharts.HistogramSeries
  ) {
    return chart.addSeries(LightweightCharts.HistogramSeries, options);
  }

  if (typeof chart.addHistogramSeries === "function") {
    return chart.addHistogramSeries(options);
  }

  throw new Error(
    "The loaded Lightweight Charts version does not support histograms.",
  );
}
