"use strict";

// Technical indicator controller.
// Keeps UI state, toggle synchronization and chart redraw requests in one place.

function setPriceOverlay(indicatorName, isEnabled) {
  state.indicators[indicatorName] = isEnabled;
  syncOverlayControls();
  return renderCurrentChart();
}

function setLowerPanel(panelName) {
  state.indicators.lowerPanel = panelName;
  syncLowerPanelControls();
  return renderCurrentChart();
}

function syncLowerPanelControls() {
  document
    .querySelectorAll('.indicator-toggle[data-indicator-type="lower"]')
    .forEach((toggle) => {
      toggle.checked = state.indicators.lowerPanel === toggle.dataset.indicator;
    });
}

function syncOverlayControls() {
  document
    .querySelectorAll('.indicator-toggle[data-indicator-type="overlay"]')
    .forEach((toggle) => {
      toggle.checked = state.indicators[toggle.dataset.indicator] === true;
    });
}

function syncIndicatorControls() {
  syncLowerPanelControls();
  syncOverlayControls();
}

function renderActiveTechnicalIndicators() {
  if (state.indicators.bollinger === true) {
    const bollingerData = bollingerCalculator();
    if (bollingerData && bollingerData.upper.length !== 0) {
      renderBollinger(bollingerData);
    }
  }

  if (state.indicators.lowerPanel === "rsi") {
    const rsiData = rsiCalculator();
    if (rsiData.length !== 0) renderRSI(rsiData);
  }

  if (state.indicators.lowerPanel === "macd") {
    const macdData = MACDCalculator();
    if (macdData && macdData.macd.length !== 0) renderMACD(macdData);
  }

  if (state.indicators.lowerPanel === "atr") {
    const atrData = ATRCalculator();
    if (atrData && atrData.length !== 0) renderATR(atrData);
  }
}

function initIndicatorsMenu() {
  const indicatorButton = document.getElementById("indicators_button");
  const indicatorsMenu = document.getElementById("indicators_menu");
  const indicatorToggles = document.querySelectorAll(".indicator-toggle");

  if (!indicatorButton || !indicatorsMenu) return;

  indicatorButton.addEventListener("click", () => {
    const isOpen = indicatorsMenu.classList.toggle("open");
    indicatorButton.setAttribute("aria-expanded", String(isOpen));
  });

  indicatorToggles.forEach((toggle) => {
    toggle.addEventListener("change", async () => {
      const indicatorName = toggle.dataset.indicator;
      const indicatorType = toggle.dataset.indicatorType;
      const isChecked = toggle.checked;

      if (indicatorType === "overlay") {
        await setPriceOverlay(indicatorName, isChecked);
        return;
      }

      if (indicatorType === "lower") {
        const nextPanel = isChecked ? indicatorName : null;
        await setLowerPanel(nextPanel);
      }
    });
  });
}

initIndicatorsMenu();
