"use strict";

// Timeframe menu and portfolio chart mode controls.

function closeTimeframeMenu() {
  const timeframeTrigger = document.getElementById("timeframeTrigger");
  const timeframeMenu = document.getElementById("timeframeMenu");
  timeframeMenu?.classList.remove("open");
  timeframeTrigger?.setAttribute("aria-expanded", "false");
}

function initTimeframeControls() {
  const timeframeTrigger = document.getElementById("timeframeTrigger");
  const timeframeMenu = document.getElementById("timeframeMenu");

  timeframeTrigger?.addEventListener("click", () => {
    const isOpen = timeframeMenu.classList.toggle("open");
    timeframeTrigger.setAttribute("aria-expanded", String(isOpen));
  });

  document.querySelectorAll(".timeframe-menu button").forEach((button) => {
    button.addEventListener("click", async () => {
      state.timeframe = button.dataset.timeframe;
      document.getElementById("selectedTimeframe").textContent =
        state.timeframe.toUpperCase();
      document.getElementById("chartTimeframe").textContent =
        state.timeframe.toUpperCase();
      closeTimeframeMenu();
      await renderCurrentChart();
    });
  });
}

function initBalanceModeControls() {
  document.querySelectorAll(".balance-mode-button").forEach((button) => {
    button.addEventListener("click", async () => {
      document
        .querySelectorAll(".balance-mode-button")
        .forEach((btn) => btn.classList.remove("active"));
      button.classList.add("active");

      state.mode = button.dataset.mode;
      state.chartKind = "portfolio";
      await renderCurrentChart();
    });
  });
}


function initChartNavigationControls() {
  initTimeframeControls();
  initBalanceModeControls();
}

initChartNavigationControls();
