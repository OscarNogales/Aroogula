"use strict";

// Portfolio/equity chart rendering.

async function loadEquityChart() {
  state.chartKind = "portfolio";
  const config =
    portfolioSeriesConfig[state.mode] || portfolioSeriesConfig.equity;

  document.getElementById("chartTicker").textContent = "PORTFOLIO";
  document.getElementById("chartTimeframe").textContent =
    state.timeframe.toUpperCase();
  document.getElementById("chartModeLabel").textContent = config.label;
  setTickerHeaderVisible(false);

  try {
    const response = await apiPost("/api/graphs/equity_graph", {
      time: state.timeframe,
    });
    const rows = normalizeEquityRows(response);

    let points = rows
      .map((row, index) => ({
        time: parseChartTime(
          row.timestamp ??
            row.time ??
            row.date ??
            row.datetime ??
            row.Date ??
            row.Datetime,
          index,
        ),
        value: firstNumericField(row, config.fields),
      }))
      .filter((point) => Number.isFinite(point.value));

    points = sortAndDeduplicateByTime(points);
    points = filterPointsByTimeframe(points, state.timeframe);

    if (!points.length) {
      setChartMessage(
        `No ${config.label} data is available.<br><small>The ledger must return timestamp, equity, cash, and portfolio_assets.</small>`,
      );
      return;
    }

    const chart = createBaseChart();
    activeSeries = addLineSeriesCompat(chart, {
      color: config.color,
      lineWidth: 3,
      title: config.label,
      pointMarkersVisible: true,
      pointMarkersRadius: 3,
      priceFormat: {
        type: "custom",
        formatter: (value) => money(value),
      },
    });
    activeSeries.setData(points);
    chart.timeScale().fitContent();
  } catch (error) {
    console.error("Error loading historical portfolio chart:", error);
    setChartMessage(
      `Could not load ${config.label}.<br><small>${String(error)}</small>`,
    );
  }
}
