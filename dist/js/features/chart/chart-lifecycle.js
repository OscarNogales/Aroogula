"use strict";

// Chart creation, teardown and base configuration.

// Set the time for New York for all graphs
  const chart_time_zone = "America/New_York";

function destroyActiveChart() {
  if (chartResizeObserver) {
    chartResizeObserver.disconnect();
    chartResizeObserver = null;
  }

  if (chartElement) {
    chartElement.remove();
    chartElement = null;
  }

  activeSeries = null;
  seriesMarkersApi = null;
  ema20Series = null;
  volumeSeries = null;

  if (typeof resetIndicatorSeries === "function") {
    resetIndicatorSeries();
  }

  const container = document.getElementById("chartContainer");
  if (container) container.innerHTML = "";
}

function chartTimeToDate(time) {
  if (typeof time === "number") {
    return new Date(time * 1000);
  }

  if (
    typeof time === "object" &&
    time !== null &&
    "year" in time &&
    "month" in time &&
    "day" in time
  ) {
    return new Date(Date.UTC(time.year, time.month - 1, time.day));
  }

  return new Date(String(time));
}

function formatChartTick(time) {
  const date = chartTimeToDate(time);

  return new Intl.DateTimeFormat("en-US", {
    timeZone: chart_time_zone,
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date);
}

function formatChartTooltip(time) {
  const date = chartTimeToDate(time);

  return new Intl.DateTimeFormat("en-US", {
    timeZone: chart_time_zone,
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date);
}


function createBaseChart() {
  const container = document.getElementById("chartContainer");
  const box = document.getElementById("chartBox");

  if (!container || !box) {
    throw new Error("chartContainer/chartBox was not found.");
  }

  destroyActiveChart();

  chartElement = LightweightCharts.createChart(container, {
    width: Math.max(1, box.clientWidth),
    height: Math.max(1, box.clientHeight),

    layout: {
      background: {
        type: LightweightCharts.ColorType.Solid,
        color: chartUiState.theme === "light" ? "white" : "transparent",
      },
      textColor: "#8d8d96",
      fontFamily:
        'system-ui, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif',
    },

    grid: getGridOptions(chartUiState.gridVisible),

    rightPriceScale: {
      borderVisible: false,
      scaleMargins: { top: 0.12, bottom: 0.12 },
    },

    localization: {
      timeFormatter: formatChartTooltip,
    },

    timeScale: {
      borderVisible: false,
      timeVisible: true,
      secondsVisible: false,
      tickMarkFormatter: formatChartTick,
    },

    crosshair: {
      mode: LightweightCharts.CrosshairMode.Normal,
    },
  });

  chartResizeObserver = new ResizeObserver(() => {
    if (chartElement && box.clientWidth > 0 && box.clientHeight > 0) {
      chartElement.resize(box.clientWidth, box.clientHeight);
    }
  });

  chartResizeObserver.observe(box);

  return chartElement;
}

function setChartMessage(message) {
  const container = document.getElementById("chartContainer");
  if (!container) return;
  destroyActiveChart();
  container.innerHTML = `
      <div style="height:100%;display:grid;place-items:center;color:#8d8d96;text-align:center;padding:24px;">
        <div>${message}</div>
      </div>
    `;
}
