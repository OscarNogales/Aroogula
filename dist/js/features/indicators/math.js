"use strict";

// Technical indicator math helpers.
// These functions are intentionally DOM/chart-free so they can be tested in isolation.

const INDICATOR_PRICE_FORMAT = {
  type: "price",
  precision: 4,
  minMove: 0.0001,
};

const INDICATOR_COLORS = {
  rsi: "#a78bfa",
  bollingerUpper: "rgba(234, 179, 8, 0.70)",
  bollingerMiddle: "rgba(250, 204, 21, 0.92)",
  bollingerLower: "rgba(234, 179, 8, 0.70)",
  macd: "#60a5fa",
  signal: "#f59e0b",
  histogram: "#10b981",
  atr: "#fb7185",
  spy: "#94a3b8"
};

function average(values) {
  if (!Array.isArray(values) || values.length === 0) return null;
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function standardDeviation(values, mean = average(values)) {
  if (!Array.isArray(values) || values.length === 0 || mean === null)
    return null;

  const variance =
    values.reduce((sum, value) => {
      return sum + Math.pow(value - mean, 2);
    }, 0) / values.length;

  return Math.sqrt(variance);
}

function getCloseArray(candles = state.candles) {
  if (!Array.isArray(candles)) return [];

  return candles
    .map((candle) => ({
      time: candle.time,
      value: Number(candle.close),
    }))
    .filter(
      (point) => point.time !== undefined && Number.isFinite(point.value),
    );
}

function getATRArray(candles = state.candles) {
  if (!Array.isArray(candles)) return [];

  return candles
    .map((candle) => ({
      time: candle.time,
      high: Number(candle.high),
      low: Number(candle.low),
      close: Number(candle.close),
    }))
    .filter(
      (point) =>
        point.time !== undefined &&
        Number.isFinite(point.high) &&
        Number.isFinite(point.low) &&
        Number.isFinite(point.close),
    );
}

function showIndicatorDataWarning(indicatorName) {
  console.warn(`Not enough candles to calculate ${indicatorName}.`);
  showToast(
    `❌ Not enough candles to calculate ${indicatorName}. Please select another timeframe...`,
  );
}

function buildPriceScaleOptions(scaleId) {
  return {
    scaleId,
    mainScale: {
      scaleMargins: {
        top: 0.08,
        bottom: 0.3,
      },
    },
    indicatorScale: {
      scaleMargins: {
        top: 0.74,
        bottom: 0.05,
      },
      borderVisible: false,
    },
  };
}
