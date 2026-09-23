"use strict";

// Top-right chart actions: fullscreen, export and settings menu.

async function toggleChartFullscreen() {
  const chartBox = document.getElementById("chartBox");
  if (!chartBox) return;

  const isChartFullscreen = document.fullscreenElement === chartBox;
  if (isChartFullscreen) {
    await document.exitFullscreen();
  } else {
    await chartBox.requestFullscreen();
  }
}

function exportChartAsPng() {
  if (!chartElement || typeof chartElement.takeScreenshot !== "function") {
    showToast("❌ Chart screenshot is not available yet.");
    return;
  }

  const canvas = chartElement.takeScreenshot();
  const ticker = state.chartKind === "ticker" ? state.ticker : "portfolio";
  const label = state.chartKind === "portfolio" ? state.mode : state.timeframe;
  const filename = `${ticker}_${label}_chart.png`.replace(/[^a-z0-9_.-]/gi, "_");
  const link = document.createElement("a");

  link.download = filename;
  link.href = canvas.toDataURL("image/png");
  link.click();

  showToast("📷 Chart exported as PNG to  .");
}

function setChartSettingsOpen(isOpen) {
  const button = document.getElementById("chart_settings_button");
  const menu = document.getElementById("chart_settings_menu");
  if (!button || !menu) return;

  button.setAttribute("aria-expanded", String(isOpen));
  menu.classList.toggle("open", isOpen);
  menu.setAttribute("aria-hidden", String(!isOpen));
}

function toggleChartSettingsMenu() {
  const menu = document.getElementById("chart_settings_menu");
  setChartSettingsOpen(!menu?.classList.contains("open"));
}

async function clearChartIndicators() {
  state.indicators.ema20 = false;
  state.indicators.bollinger = false;
  state.indicators.lowerPanel = null;

  if (typeof syncIndicatorControls === "function") syncIndicatorControls();
  await renderCurrentChart();
  showToast("Indicators cleared.");
}

function handleChartSettingAction(action) {
  if (action === "fit") {
    fitChartContent();
    showToast("↻ Chart view reset.");
    return;
  }

  if (action === "grid") {
    toggleGridVisibility();
    return;
  }

  if (action === "theme") {
    toggleChartTheme();
    return;
  }

  if (action === "clear-indicators") {
    clearChartIndicators();
  }
}

function initChartActions() {
  const fullscreenButton = document.getElementById("chart_fullscreen");
  const exportButton = document.getElementById("chart_export_button");
  const settingsButton = document.getElementById("chart_settings_button");
  const settingsMenu = document.getElementById("chart_settings_menu");

  fullscreenButton.addEventListener("click", toggleChartFullscreen);
  exportButton.addEventListener("click", exportChartAsPng);
  settingsButton.addEventListener("click", (event) => {
    toggleChartSettingsMenu();
  });

  settingsMenu.addEventListener("click", (event) => {
    const button = event.target.closest("[data-chart-setting-action]");
    if (!button) return;
    handleChartSettingAction(button.dataset.chartSettingAction);
    setChartSettingsOpen(false);
  });

  document.addEventListener("fullscreenchange", () => {
    requestAnimationFrame(() => {
      const chartBox = document.getElementById("chartBox");
      if (!chartElement || !chartBox) return;
      chartElement.resize(chartBox.clientWidth, chartBox.clientHeight);
      chartElement.timeScale().fitContent();
    });
  });
}

initChartActions();
