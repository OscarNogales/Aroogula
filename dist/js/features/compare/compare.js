"use strict";

// Multi-ticker comparison chart.
// Lets the user add up to MAX_COMPARISONS extra tickers and renders each line
// as percentage change from its first visible close.

const compareButton = document.getElementById("compare_button");
const compareADDButton = document.getElementById("compare_add_button");
const inputCompare = document.getElementById("compare_input");
const compareMenu = document.getElementById("compare_menu");
const compareSuggestions = document.getElementById("compare_suggestions");
const activeComparisons = document.getElementById("active_comparisons");

let supportedCompanies = [];
let selectedCompany = null;
let comparedCompanies = [];
const MAX_COMPARISONS = 4;
const comparisonSeries = new Map();

async function getCompanies() {
  try {
    const response = await apiGet("/api/companies/list");
    const payload = unwrapResponse(response);
    return Array.isArray(payload) ? payload : payload?.companies || [];
  } catch (error) {
    console.error("Could not load supported companies:", error);
    return [];
  }
}

function hideCompareSuggestions() {
  compareSuggestions.replaceChildren();
  compareSuggestions.hidden = true;
}

function companyMatchesSearch(company, searchText) {
  const ticker = String(company.ticker || "").toLowerCase();
  const words = String(company.name || "").toLowerCase().split(/\s+/);

  return ticker.includes(searchText) || words.some((word) => word.startsWith(searchText));
}

function renderCompareSuggestions(matches) {
  compareSuggestions.replaceChildren();
  compareSuggestions.hidden = matches.length === 0;

  matches.forEach((company) => {
    const suggestionButton = document.createElement("button");
    suggestionButton.classList.add("compare-suggestion");
    suggestionButton.type = "button";

    suggestionButton.addEventListener("mousedown", (event) => {
      event.preventDefault();
    });

    suggestionButton.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();

      selectedCompany = company;
      inputCompare.value = company.ticker;

      // Esto es opcional:
      // Si quieres que solo desaparezcan las sugerencias, déjalo.
      // Si quieres que la lista se quede visible, quítalo.
      hideCompareSuggestions();

      inputCompare.focus();
    });

    const tickerElement = document.createElement("strong");
    const nameElement = document.createElement("span");

    tickerElement.textContent = company.ticker;
    nameElement.textContent = company.name;

    suggestionButton.append(tickerElement, nameElement);
    compareSuggestions.append(suggestionButton);
  });
}

function handleCompareSearchInput() {
  const searchText = inputCompare.value.trim().toLowerCase();

  if (searchText === "") {
    selectedCompany = null;
    hideCompareSuggestions();
    return;
  }

  const matches = supportedCompanies
    .filter((company) => companyMatchesSearch(company, searchText))
    .slice(0, 5);

  renderCompareSuggestions(matches);
}

function updateCompareButton() {
  const amount = comparedCompanies.length;
  compareButton.textContent = amount === 0 ? "⊕ Compare" : `⊕ Compare ⋅ ${amount}`;
}

function syncCurrentTickerAfterComparisonRemoval() {
  if (comparedCompanies.length === 1) {
    const remainingCompany = comparedCompanies[0];

    state.ticker = remainingCompany.ticker;
    state.chartKind = "ticker";

    comparedCompanies = [];

    document.getElementById("chartTicker").textContent = state.ticker;
    document.getElementById("sharesHint").textContent = `(${state.ticker})`;

    return;
  }

  if (comparedCompanies.length === 0 && !state.ticker) {
    state.chartKind = "portfolio";
    document.getElementById("chartTicker").textContent = "Portfolio";
    document.getElementById("sharesHint").textContent = "";
  }
}

function renderComparedCompanies() {
  activeComparisons.replaceChildren();
  activeComparisons.hidden = comparedCompanies.length === 0;

  comparedCompanies.forEach((company) => {
    const chip = document.createElement("div");
    chip.classList.add("comparison-chip");

    const tickerElement = document.createElement("span");
    tickerElement.classList.add("comparison-chip-ticker");
    tickerElement.textContent = company.ticker;

    const removeButton = document.createElement("button");
    removeButton.classList.add("comparison-chip-remove");
    removeButton.type = "button";
    removeButton.textContent = "×";
    removeButton.title = `Remove ${company.ticker}`;
    removeButton.setAttribute(
      "aria-label",
      `Remove ${company.ticker} from comparison`,
    );

    removeButton.addEventListener("click", async () => {
      event.preventDefault();
      event.stopPropagation();

      comparedCompanies = comparedCompanies.filter((item) => item.ticker !== company.ticker);

      selectedCompany = null;
      inputCompare.value = "";
      hideCompareSuggestions();
      syncCurrentTickerAfterComparisonRemoval();
      renderComparedCompanies();

      try {
        await graphComparedTickers(comparedCompanies);
      } catch (error) {
        console.error(`Error removing ${company.ticker} from chart:`, error);
        showToast("❌ Could not update the comparison chart.");
      }
    });

    chip.append(tickerElement, removeButton);
    activeComparisons.append(chip);
  });

  updateCompareButton();
}

function makeCompanyFromTicker(ticker) {
  return {
    ticker,
    name: ticker,
  };
}

async function addSelectedComparison() {
  if (selectedCompany === null) {
    showToast("Select a company to make the comparison.");
    return;
  }

  const currentTicker = state.ticker;
  const addedTicker = selectedCompany.ticker;

  const currentAlreadyCompared = comparedCompanies.some(
    (company) => company.ticker === currentTicker,
  );

  if (currentTicker && !currentAlreadyCompared && currentTicker !== addedTicker) {
    comparedCompanies.push(makeCompanyFromTicker(currentTicker));
  }

  const alreadyCompared = comparedCompanies.some(
    (company) => company.ticker === addedTicker,
  );

  if (alreadyCompared) {
    showToast(`❌ ${addedTicker} is already being compared.`);
    return;
  }

  if (comparedCompanies.length >= MAX_COMPARISONS) {
    const removedCompany = comparedCompanies.shift();
    showToast(`↔ ${removedCompany.ticker} was replaced by ${addedTicker}.`);
  }

  state.ticker = addedTicker;
  state.chartKind = "ticker";

  selectedCompany = null;
  inputCompare.value = "";
  hideCompareSuggestions();
  renderComparedCompanies();

  try {
    await graphComparedTickers(comparedCompanies);
    showToast(`✅ ${addedTicker} added to comparison.`);
  } catch (error) {
    console.error(`Error adding ${addedTicker} to comparison:`, error);
    showToast(`❌ Could not graph ${addedTicker}.`);
  }
}

async function compareTicker(ticker) {
  const response = await apiPost("/api/graphs/ticker_graph", {
    ticker,
    period: state.timeframe,
    mean: false,
  });

  const candles = normalizeTickerCandles(response);
  if (candles.length === 0) {
    throw new Error(`No valid candles were returned for ${ticker}.`);
  }

  const firstClose = candles[0].close;
  if (!Number.isFinite(firstClose) || firstClose === 0) {
    throw new Error(`Invalid first close for ${ticker}.`);
  }

  return {
    ticker,
    data: candles.map((candle) => ({
      time: candle.time,
      value: Number(((candle.close / firstClose - 1) * 100).toFixed(4)),
    })),
  };
}

function clearComparisonSeries() {
  comparisonSeries.clear();
}

async function graphComparedTickers(companies) {
  if (companies.length === 0) {
    clearComparisonSeries();
    await loadCandles(state.ticker, state.timeframe);
    return;
  }

  const chart = createBaseChart();
  clearComparisonSeries();

  setTickerHeaderVisible(false);
  document.getElementById("chartModeLabel").textContent = "Compare";

  const tickerLines = [await compareTicker(state.ticker)];
  const comparisonLines = await Promise.all(
    companies.map((company) => compareTicker(company.ticker)),
  );
  tickerLines.push(...comparisonLines);

  tickerLines.forEach((lineData, index) => {
    const lineSeries = addLineSeriesCompat(chart, {
      title: lineData.ticker,
      lineWidth: 2,
      color: COMPARISON_COLORS[index % COMPARISON_COLORS.length],
      priceFormat: {
        type: "custom",
        formatter: (value) => pct(value),
      },
    });

    lineSeries.setData(lineData.data);
    comparisonSeries.set(lineData.ticker, lineSeries);
  });

  chart.timeScale().fitContent();
}

function initCompareFeature() {
  if (!compareButton || !compareADDButton || !inputCompare) return;

  inputCompare.addEventListener("input", handleCompareSearchInput);
  compareButton.addEventListener("click", (event) => {
  event.preventDefault();
  event.stopPropagation();
  compareMenu.classList.toggle("open");
  });
  compareADDButton.addEventListener("click", addSelectedComparison);
  renderComparedCompanies();
}
