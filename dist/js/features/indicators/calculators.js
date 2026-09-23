"use strict";

// Technical indicator calculators.
// Public functions keep the names used by the rest of the app:
// rsiCalculator, bollingerCalculator, EMA, MACDCalculator, ATRCalculator.

function calculateRSIValue(averageGain, averageLoss) {
  if (averageGain === 0 && averageLoss === 0) return 50;
  if (averageLoss === 0) return 100;
  if (averageGain === 0) return 0;

  const relativeStrength = averageGain / averageLoss;
  return 100 - 100 / (1 + relativeStrength);
}

function rsiCalculator(period = 14) {
  const closeArray = getCloseArray();

  if (closeArray.length <= period) {
    showIndicatorDataWarning("RSI");
    return [];
  }

  let gainSum = 0;
  let lossSum = 0;
  const rsiData = [];

  for (let i = 1; i <= period; i++) {
    const change = closeArray[i].value - closeArray[i - 1].value;

    if (change > 0) {
      gainSum += change;
    } else {
      lossSum += Math.abs(change);
    }
  }

  let avgGain = gainSum / period;
  let avgLoss = lossSum / period;

  rsiData.push({
    time: closeArray[period].time,
    value: calculateRSIValue(avgGain, avgLoss),
  });

  for (let i = period + 1; i < closeArray.length; i++) {
    const change = closeArray[i].value - closeArray[i - 1].value;
    const gain = change > 0 ? change : 0;
    const loss = change < 0 ? Math.abs(change) : 0;

    avgGain = (avgGain * (period - 1) + gain) / period;
    avgLoss = (avgLoss * (period - 1) + loss) / period;

    rsiData.push({
      time: closeArray[i].time,
      value: calculateRSIValue(avgGain, avgLoss),
    });
  }

  return rsiData;
}

function bollingerCalculator(period = 20, multiplier = 2) {
  const closeArray = getCloseArray();

  if (closeArray.length < period) {
    showIndicatorDataWarning("Bollinger Bands");
    return null;
  }

  const upper = [];
  const middle = [];
  const lower = [];

  for (let i = period - 1; i < closeArray.length; i++) {
    const window = closeArray.slice(i - period + 1, i + 1);
    const closes = window.map((point) => point.value);
    const mean = average(closes);
    const std = standardDeviation(closes, mean);

    if (mean === null || std === null) continue;

    upper.push({
      time: closeArray[i].time,
      value: mean + multiplier * std,
    });

    middle.push({
      time: closeArray[i].time,
      value: mean,
    });

    lower.push({
      time: closeArray[i].time,
      value: mean - multiplier * std,
    });
  }

  return { upper, middle, lower };
}

function EMA(points, period = 12) {
  if (!Array.isArray(points) || points.length < period) return [];

  const values = points.map((point) => point.value);
  const emaValues = [];
  let emaValue = average(values.slice(0, period));
  const smoothingFactor = 2 / (period + 1);

  if (emaValue === null) return [];

  emaValues.push(emaValue);

  for (let i = period; i < values.length; i++) {
    emaValue = values[i] * smoothingFactor + emaValue * (1 - smoothingFactor);
    emaValues.push(emaValue);
  }

  return emaValues.map((value, index) => ({
    time: points[index + period - 1].time,
    value,
  }));
}

function MACDCalculator(fastPeriod = 12, slowPeriod = 26, signalPeriod = 9) {
  const closeArray = getCloseArray();
  const minimumCandles = slowPeriod + signalPeriod - 1;

  if (closeArray.length < minimumCandles) {
    showIndicatorDataWarning("MACD");
    return null;
  }

  const fastEMA = EMA(closeArray, fastPeriod);
  const slowEMA = EMA(closeArray, slowPeriod);
  const fastOffset = slowPeriod - fastPeriod;

  const macd = slowEMA
    .map((slowPoint, index) => {
      const fastPoint = fastEMA[index + fastOffset];
      if (!fastPoint) return null;

      return {
        time: slowPoint.time,
        value: fastPoint.value - slowPoint.value,
      };
    })
    .filter(Boolean);

  const signal = EMA(macd, signalPeriod);
  const signalOffset = signalPeriod - 1;

  const histogram = signal
    .map((signalPoint, index) => {
      const macdPoint = macd[index + signalOffset];
      if (!macdPoint) return null;

      return {
        time: signalPoint.time,
        value: macdPoint.value - signalPoint.value,
      };
    })
    .filter(Boolean);

  return { macd, signal, histogram };
}

function ATRCalculator(period = 14) {
  const atrArray = getATRArray();

  if (atrArray.length < period + 1) {
    showIndicatorDataWarning("ATR");
    return null;
  }

  const trueRanges = atrArray.slice(1).map((currentPoint, index) => {
    const previousPoint = atrArray[index];
    const highLow = currentPoint.high - currentPoint.low;
    const highPrevClose = Math.abs(currentPoint.high - previousPoint.close);
    const lowPrevClose = Math.abs(currentPoint.low - previousPoint.close);

    return {
      time: currentPoint.time,
      value: Math.max(highLow, highPrevClose, lowPrevClose),
    };
  });

  if (trueRanges.length < period) {
    showIndicatorDataWarning("ATR");
    return null;
  }

  let atrValue = average(
    trueRanges.slice(0, period).map((point) => point.value),
  );
  if (atrValue === null) return null;

  const atrData = [
    {
      time: trueRanges[period - 1].time,
      value: atrValue,
    },
  ];

  for (let i = period; i < trueRanges.length; i++) {
    atrValue = (atrValue * (period - 1) + trueRanges[i].value) / period;

    atrData.push({
      time: trueRanges[i].time,
      value: atrValue,
    });
  }

  return atrData;
}
