"use strict";

// Shared chart visual options.

function isLightChartTheme() {
  return chartUiState.theme === "light";
}

function getGridLineColor(isVisible = chartUiState.gridVisible) {
  if (!isVisible) return "transparent";
  return isLightChartTheme()
    ? "rgba(0, 0, 0, 0.15)"
    : "rgba(255, 255, 255, 0.15)";
}

function getGridOptions(isVisible = chartUiState.gridVisible) {
  const color = getGridLineColor(isVisible);
  return {
    vertLines: { color },
    horzLines: { color },
  };
}

function applyGridOptions() {
  if (!chartElement) return;
  chartElement.applyOptions({
    grid: getGridOptions(chartUiState.gridVisible),
  });
}

function applyThemeOptions() {
  if (!chartElement) return;
  chartElement.applyOptions({
    layout: {
      background: {
        type: LightweightCharts.ColorType.Solid,
        color: isLightChartTheme() ? "white" : "transparent",
      },
    },
    grid: getGridOptions(chartUiState.gridVisible),
  });
}
