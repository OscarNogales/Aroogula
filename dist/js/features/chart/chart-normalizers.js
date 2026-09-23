"use strict";

// Data normalization utilities for backend responses.

function unwrapResponse(value) {
  let current = value;
  for (let i = 0; i < 4; i++) {
    if (!current || typeof current !== "object" || Array.isArray(current)) {
      break;
    }
    if (current.data !== undefined) {
      current = current.data;
      continue;
    }
    if (current.payload !== undefined) {
      current = current.payload;
      continue;
    }
    break;
  }
  return current;
}

function parseChartTime(raw, fallbackIndex = 0) {
  if (typeof raw === "number" && Number.isFinite(raw)) {
    return raw > 10_000_000_000 ? Math.floor(raw / 1000) : Math.floor(raw);
  }

  if (raw instanceof Date && !Number.isNaN(raw.getTime())) {
    return Math.floor(raw.getTime() / 1000);
  }

  if (raw !== null && raw !== undefined) {
    const parsed = Date.parse(String(raw));
    if (!Number.isNaN(parsed)) return Math.floor(parsed / 1000);
  }

  return Math.floor(Date.now() / 1000) + fallbackIndex;
}

function sortAndDeduplicateByTime(points) {
  const sorted = points
    .filter((point) => Number.isFinite(point.time))
    .sort((a, b) => a.time - b.time);

  const unique = [];
  for (const point of sorted) {
    if (unique.length && unique[unique.length - 1].time === point.time) {
      unique[unique.length - 1] = point;
    } else {
      unique.push(point);
    }
  }
  return unique;
}

function normalizeTickerCandles(response) {
  const source = unwrapResponse(response) || {};
  const directCandles = Array.isArray(source)
    ? source
    : source.candles || source.records || source.logs;

  let rows = [];
  if (Array.isArray(directCandles)) {
    rows = directCandles;
  } else {
    const times =
      source.Date ||
      source.Datetime ||
      source.Time ||
      source.date ||
      source.datetime ||
      source.time ||
      source.timestamp ||
      [];
    const opens = source.Open || source.open || [];
    const highs = source.High || source.high || [];
    const lows = source.Low || source.low || [];
    const closes = source.Close || source.close || [];
    const volumes = source.Volume || source.volume || [];
    const length = Math.max(
      times.length || 0,
      opens.length || 0,
      closes.length || 0,
    );

    rows = Array.from({ length }, (_, index) => ({
      time: times[index],
      open: opens[index],
      high: highs[index],
      low: lows[index],
      close: closes[index],
      volume: volumes[index],
    }));
  }

  const candles = rows
    .map((row, index) => {
      const open = Number(row.open ?? row.Open);
      const high = Number(row.high ?? row.High);
      const low = Number(row.low ?? row.Low);
      const close = Number(row.close ?? row.Close);
      const volume = Number(row.volume ?? row.Volume);
      const time = parseChartTime(
        row.time ??
          row.timestamp ??
          row.date ??
          row.datetime ??
          row.Date ??
          row.Datetime ??
          row.Time,
        index,
      );

      return { time, open, high, low, close, volume };
    })
    .filter(
      (candle) =>
        Number.isFinite(candle.open) &&
        Number.isFinite(candle.high) &&
        Number.isFinite(candle.low) &&
        Number.isFinite(candle.close),
    );

  return sortAndDeduplicateByTime(candles);
}

function rowsFromColumnObject(source) {
  const keys = Object.keys(source || {});
  const arrayKeys = keys.filter((key) => Array.isArray(source[key]));
  if (!arrayKeys.length) return [];

  const length = Math.max(...arrayKeys.map((key) => source[key].length));
  return Array.from({ length }, (_, index) => {
    const row = {};
    keys.forEach((key) => {
      row[key] = Array.isArray(source[key]) ? source[key][index] : source[key];
    });
    return row;
  });
}

function normalizeEquityRows(response) {
  let source = unwrapResponse(response);

  if (source && !Array.isArray(source) && typeof source === "object") {
    source = source.logs || source.records || source.equity_logs || source;
  }

  if (Array.isArray(source)) return source;
  if (source && typeof source === "object") {
    const columnRows = rowsFromColumnObject(source);
    return columnRows.length ? columnRows : [source];
  }
  return [];
}

function filterPointsByTimeframe(points, timeframe) {
  if (!points.length || timeframe === "max") return points;

  const latestSeconds = points[points.length - 1].time;
  const latest = new Date(latestSeconds * 1000);
  let cutoff = null;

  const day = 24 * 60 * 60 * 1000;
  const durations = {
    "1d": day,
    "5d": 5 * day,
    "1mo": 31 * day,
    "3mo": 93 * day,
    "6mo": 186 * day,
    "1y": 366 * day,
    "2y": 2 * 366 * day,
    "5y": 5 * 366 * day,
    "10y": 10 * 366 * day,
  };

  if (timeframe === "ytd") {
    cutoff = new Date(latest.getFullYear(), 0, 1).getTime();
  } else if (durations[timeframe]) {
    cutoff = latest.getTime() - durations[timeframe];
  }

  if (cutoff === null) return points;
  const filtered = points.filter((point) => point.time * 1000 >= cutoff);
  return filtered.length ? filtered : points.slice(-1);
}

function firstNumericField(row, fields) {
  for (const field of fields) {
    const value = Number(row?.[field]);
    if (Number.isFinite(value)) return value;
  }
  return null;
}
