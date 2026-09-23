const buttonsChartContainer = document.getElementById("chart-actions");

const emaButton = document.getElementById("moving_average_button");
const volumeButton = document.getElementById("volume_button");
const spyButton = document.getElementById("spy_compare_button");

function updateButtons() {
  if (!emaButton || !volumeButton || !spyButton) return;

  emaButton.hidden = true;
  volumeButton.hidden = true;
  spyButton.hidden = true;

  if (state.chartKind === "ticker") {
    emaButton.hidden = false;
    volumeButton.hidden = false;
    return;
  }

  if (state.chartKind === "portfolio" && state.mode === "equity") {
    spyButton.hidden = false;
    return;
  }

}