"use strict";

// Grid, crosshair, theme and fit-content controls.

function setGridVisible(isVisible) {
  chartUiState.gridVisible = Boolean(isVisible);
  applyGridOptions();
}

function toggleGridVisibility() {
  setGridVisible(!chartUiState.gridVisible);
  showToast(chartUiState.gridVisible ? "⌗ Grid enabled." : "⌗ Grid hidden.");
}

function setChartTheme(theme) {
  chartUiState.theme = theme === "light" ? "light" : "dark";
  applyThemeOptions();
}

function toggleChartTheme() {
  setChartTheme(chartUiState.theme === "dark" ? "light" : "dark");
  showToast(chartUiState.theme === "light" ? "◐ Light chart." : "◐ Dark chart.");
}

function fitChartContent() {
  if (!chartElement) return;
  chartElement.timeScale().fitContent();
}

function toggleCrosshair() {
  if (!chartElement) return;

  const currentCrosshairMode = chartElement.options().crosshair.mode;
  const isVisible =
    currentCrosshairMode === LightweightCharts.CrosshairMode.Normal;

  showToast(isVisible ? "┼ Crosshair hidden." : "┼ Crosshar enabled.")

  chartElement.applyOptions({
    crosshair: {
      mode: isVisible
        ? LightweightCharts.CrosshairMode.Hidden
        : LightweightCharts.CrosshairMode.Normal,
    },
  });
}

function initChartDisplayControls() {
  const gridButton = document.getElementById("grid_button");
  const crosshairButton = document.getElementById("crosshair_button");
  const focusButton = document.getElementById("focus_button");
  const themeButton = document.getElementById("theme_button");

  gridButton?.addEventListener("click", toggleGridVisibility);
  crosshairButton?.addEventListener("click", toggleCrosshair);
  focusButton?.addEventListener("click", () => {
    fitChartContent();
    showToast("↻ Chart view reset.");
  });
  themeButton?.addEventListener("click", toggleChartTheme);
}

initChartDisplayControls();
