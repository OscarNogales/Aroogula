"use strict";

// Local chart data generator used only as a development fallback.

function hashTicker(ticker) {
  return ticker.split("").reduce((acc, char) => acc + char.charCodeAt(0), 0);
}

function generateDemoCandles(ticker, timeframe, mode) {
  const seed = hashTicker(ticker + timeframe + mode);
  const countMap = {
    "1d": 50,
    "5d": 70,
    "1mo": 90,
    "3mo": 100,
    "6mo": 120,
    "1y": 140,
    "2y": 160,
    "5y": 180,
    "10y": 200,
    ytd: 130,
    max: 220,
  };
  const count = countMap[timeframe] || 60;
  const baseMap = {
    MSFT: 30,
    AAPL: 192,
    NVDA: 941,
    TSLA: 207,
    ADBE: 80,
    MCD: 7,
    ASML: 716,
    XOM: 146,
  };
  let price = baseMap[ticker] || 30 + (seed % 200);
  const candles = [];

  for (let i = 0; i < count; i++) {
    const drift = Math.sin((i + seed / 10) * 0.18) * 0.9;
    const noise = (((i * 13 + seed) % 17) - 8) / 14;
    const open = price;
    const close = Math.max(0.5, open + drift + noise);
    const high = Math.max(open, close) + Math.abs(noise) * 1.4 + 0.3;
    const low = Math.min(open, close) - Math.abs(noise) * 1.1 - 0.3;
    const volume = 100000 + ((i * seed) % 900000);
    price = close;

    candles.push({
      date: `T-${count - i}`,
      open,
      high,
      low,
      close,
      volume,
    });
  }

  return candles;
}
