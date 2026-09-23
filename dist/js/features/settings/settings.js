"use strict";

// Settings controls.
// This module keeps the Control Panel synced with Python Settings through Tauri.
// It intentionally edits only known keys, so accidental UI fields cannot corrupt settings.json.

const DEFAULT_BOT_SETTINGS = {
  "Bloomberg bot": false,
  "Yahoo bot": true,
  "Forbes bot": false,
  "EDGAR bot": false,
  LLM_model: "deepseek-r1:8b",
  strategy_version: "v1",
  prompt_version: "v1",
  trade_execution_mode: "normal",
  trade_risk_per_trade_pct: 0.005,
  trade_target_gain_pct: 0.05,
  trade_stop_loss_pct: 0.03,
  ai_dynamic_risk_mode: "normal",
  ai_dynamic_gain_mode: "normal",
  ai_dynamic_loss_mode: "normal",
  cb_spy_hard_stop: -1.75,
  cb_vix_high: 28.0,
  cb_vix_spike: 10.0,
  cb_tnx_spike: 2.5,
  cb_breadth_drop: -1.0,
  cb_min_warning_score: 3,
  gold_spike: 1.5,
  oil_spike: 2.5,
  cb_macro_buffer_minutes: 45,
};

const NEWS_SOURCE_SETTINGS = {
  bloomberg: { command: "/api/toggle/bloomberg", key: "Bloomberg bot", label: "Bloomberg" },
  yahoo: { command: "/api/toggle/yahoo", key: "Yahoo bot", label: "Yahoo" },
  forbes: { command: "/api/toggle/forbes", key: "Forbes bot", label: "Forbes" },
  edgar: { command: "/api/toggle/edgar", key: "EDGAR bot", label: "EDGAR" },
};

const SETTINGS_FORM_FIELDS = [
  { id: "aiModelSelect", key: "LLM_model", type: "string" },
  { id: "tradeExecutionModeSelect", key: "trade_execution_mode", type: "string" },
  { id: "tradeRiskPctInput", key: "trade_risk_per_trade_pct", type: "percent" },
  { id: "rptInput", key: "trade_risk_per_trade_pct", type: "percent" },
  { id: "targetGainPctInput", key: "trade_target_gain_pct", type: "percent" },
  { id: "stopLossPctInput", key: "trade_stop_loss_pct", type: "percent" },
  { id: "dynamicRiskModeSelect", key: "ai_dynamic_risk_mode", type: "string" },
  { id: "dynamicGainModeSelect", key: "ai_dynamic_gain_mode", type: "string" },
  { id: "dynamicLossModeSelect", key: "ai_dynamic_loss_mode", type: "string" },
  { id: "strategyVersionInput", key: "strategy_version", type: "string" },
  { id: "promptVersionInput", key: "prompt_version", type: "string" },
  { id: "spyHardStopInput", key: "cb_spy_hard_stop", type: "number" },
  { id: "vixHighInput", key: "cb_vix_high", type: "number" },
  { id: "vixSpikeInput", key: "cb_vix_spike", type: "number" },
  { id: "tnxSpikeInput", key: "cb_tnx_spike", type: "number" },
  { id: "breadthDropInput", key: "cb_breadth_drop", type: "number" },
  { id: "warningScoreInput", key: "cb_min_warning_score", type: "integer" },
  { id: "goldSpikeInput", key: "gold_spike", type: "number" },
  { id: "oilSpikeInput", key: "oil_spike", type: "number" },
  { id: "macroBufferInput", key: "cb_macro_buffer_minutes", type: "integer" },
];

let currentBotSettings = { ...DEFAULT_BOT_SETTINGS };
let settingsDirty = false;

function unwrapSettingsResponse(response) {
  const data = unwrapResponse(response) || response || {};

  if (data.settings && typeof data.settings === "object") return data.settings;
  if (data.new_settings && typeof data.new_settings === "object") return data.new_settings;
  if (data.updated_settings && typeof data.updated_settings === "object") return data.updated_settings;
  if (data.data?.settings && typeof data.data.settings === "object") return data.data.settings;
  if (data.data && typeof data.data === "object") return data.data;

  return data;
}

function setSettingsStatus(text, tone = "neutral") {
  const badge = document.getElementById("settingsStatusBadge");
  if (!badge) return;
  badge.textContent = text;
  badge.dataset.tone = tone;
}

function percentToUi(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "";
  return (numeric * 100).toFixed(2).replace(/\.00$/, "");
}

function uiToNumber(value, fallback = null) {
  const parsed = Number(String(value ?? "").trim());
  return Number.isFinite(parsed) ? parsed : fallback;
}

function writeFieldValue(field, settings) {
  const element = document.getElementById(field.id);
  if (!element) return;

  const value = settings[field.key] ?? DEFAULT_BOT_SETTINGS[field.key] ?? "";

  if (field.type === "percent") {
    element.value = percentToUi(value);
    return;
  }

  element.value = value ?? "";
}

function readFieldValue(field) {
  const element = document.getElementById(field.id);
  if (!element) return undefined;

  if (field.type === "percent") {
    const numberValue = uiToNumber(element.value);
    return numberValue == null ? undefined : numberValue / 100;
  }

  if (field.type === "number") {
    return uiToNumber(element.value);
  }

  if (field.type === "integer") {
    const numberValue = uiToNumber(element.value);
    return numberValue == null ? undefined : Math.trunc(numberValue);
  }

  return String(element.value ?? "").trim();
}

function applySettingsToForm(settings) {
  currentBotSettings = { ...DEFAULT_BOT_SETTINGS, ...settings };

  SETTINGS_FORM_FIELDS.forEach((field) => writeFieldValue(field, currentBotSettings));

  const riskMode = currentBotSettings.ai_dynamic_risk_mode || "normal";
  const aiRptToggle = document.getElementById("aiRptToggle");
  if (aiRptToggle) aiRptToggle.checked = riskMode !== "normal";

  document.querySelectorAll(".news-toggle").forEach((toggle) => {
    const source = toggle.dataset.source?.toLowerCase();
    const config = NEWS_SOURCE_SETTINGS[source];
    if (!config) return;
    toggle.checked = Boolean(currentBotSettings[config.key]);
  });

  settingsDirty = false;
  setSettingsStatus("Loaded", "success");
}

function readSettingsForm() {
  const nextSettings = {};

  SETTINGS_FORM_FIELDS.forEach((field) => {
    const value = readFieldValue(field);
    if (value !== undefined && value !== "") nextSettings[field.key] = value;
  });

  const aiRptToggle = document.getElementById("aiRptToggle");
  if (aiRptToggle && aiRptToggle.checked && nextSettings.ai_dynamic_risk_mode === "normal") {
    nextSettings.ai_dynamic_risk_mode = "aggressive";
  }

  document.querySelectorAll(".news-toggle").forEach((toggle) => {
    const source = toggle.dataset.source?.toLowerCase();
    const config = NEWS_SOURCE_SETTINGS[source];
    if (!config) return;
    nextSettings[config.key] = Boolean(toggle.checked);
  });

  return nextSettings;
}

function markSettingsDirty() {
  settingsDirty = true;
  setSettingsStatus("Unsaved", "warning");
}

async function loadBotSettings() {
  try {
    const response = await apiGet("/api/settings/get_settings");
    const settings = unwrapSettingsResponse(response);
    applySettingsToForm(settings);
    return currentBotSettings;
  } catch (error) {
    console.warn("Could not load settings from backend. Using frontend defaults.", error);
    applySettingsToForm(DEFAULT_BOT_SETTINGS);
    setSettingsStatus("Demo defaults", "warning");
    return currentBotSettings;
  }
}

async function saveSettingsPatch(patch, options = {}) {
  const { quiet = false } = options;

  try {
    const response = await apiPost("/api/settings/update_settings", {
      new_settings_dict: patch,
    });

    const updatedSettings = unwrapSettingsResponse(response);
    currentBotSettings = { ...currentBotSettings, ...patch, ...updatedSettings };
    applySettingsToForm(currentBotSettings);

    if (!quiet) showToast("⚙️ Settings saved");
    return true;
  } catch (error) {
    console.error("Error updating settings:", error);
    setSettingsStatus("Save failed", "danger");
    if (!quiet) showToast("❌ Could not save settings");
    return false;
  }
}

async function saveSettingsForm() {
  const nextSettings = readSettingsForm();
  await saveSettingsPatch(nextSettings);
}

async function toggleNewsSource(event) {
  const toggle = event.target;
  const source = toggle.dataset.source?.toLowerCase();
  const config = NEWS_SOURCE_SETTINGS[source];
  const isEnabled = toggle.checked;

  if (!config) {
    toggle.checked = !isEnabled;
    showToast(`${toggle.dataset.source || "This source"} is not connected yet.`);
    return;
  }

  try {
    const response = await apiPost(config.command, { turn_on: isEnabled });

    currentBotSettings[config.key] = isEnabled;
    await saveSettingsPatch({ [config.key]: isEnabled }, { quiet: true });

    addActivityEvent({
      type: "SYSTEM",
      ticker: "--",
      title: `${config.label} ${isEnabled ? "enabled" : "disabled"}`,
      summary: response?.message || "News source setting changed.",
      ttl_seconds: 18,
    });
  } catch (error) {
    console.error(`Error updating ${config.label}:`, error);
    toggle.checked = !isEnabled;
    showToast(`❌ Could not update ${config.label}.`);
  }
}

async function saveQuickAiSettings() {
  const patch = {};
  const aiModel = readFieldValue({ id: "aiModelSelect", key: "LLM_model", type: "string" });
  const riskPerTrade = readFieldValue({ id: "rptInput", key: "trade_risk_per_trade_pct", type: "percent" });
  const aiRptToggle = document.getElementById("aiRptToggle");

  if (aiModel) patch.LLM_model = aiModel;
  if (riskPerTrade !== undefined) patch.trade_risk_per_trade_pct = riskPerTrade;
  if (aiRptToggle) patch.ai_dynamic_risk_mode = aiRptToggle.checked ? "aggressive" : "normal";

  await saveSettingsPatch(patch);
}

function initSettingsControls() {
  document.querySelectorAll(".news-toggle").forEach((switchElement) => {
    switchElement.addEventListener("change", toggleNewsSource);
  });

  ["aiModelSelect", "aiRptToggle", "rptInput"].forEach((id) => {
    document.getElementById(id)?.addEventListener("change", saveQuickAiSettings);
  });

  document.querySelectorAll("#settingsPanel .settings-input").forEach((input) => {
    input.addEventListener("input", markSettingsDirty);
    input.addEventListener("change", markSettingsDirty);
  });

  document.getElementById("saveSettingsBtn")?.addEventListener("click", saveSettingsForm);
  document.getElementById("reloadSettingsBtn")?.addEventListener("click", loadBotSettings);
  document.getElementById("resetSettingsFormBtn")?.addEventListener("click", () => {
    applySettingsToForm(currentBotSettings);
    showToast("Settings form reset");
  });

  loadBotSettings();
}
