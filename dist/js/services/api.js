"use strict";

// Backend bridge.
// In the Tauri desktop app this delegates to Rust commands.
// In browser/demo mode it returns safe fixtures so the UI can be inspected without Python/Rust.

const tauriInvoke = window.__TAURI__?.core?.invoke ?? window.__TAURI__?.invoke;

function cloneFallback(value) {
  if (value === undefined) return undefined;
  if (value === null) return null;
  if (typeof structuredClone === "function") return structuredClone(value);
  return JSON.parse(JSON.stringify(value));
}

function demoSettingsResponse() {
  return {
    status: "success",
    data: {
      settings: cloneFallback(DEFAULT_BOT_SETTINGS ?? {}),
    },
  };
}

async function demoInvoke(command, args = {}) {
  if (!USE_DEMO_DATA) {
    throw new Error(`Tauri invoke is not available for command: ${command}`);
  }

  console.warn(`Demo invoke fallback: ${command}`, args);

  switch (command) {
    case "get_equity_summary":
      return {
        status: "success",
        data: {
          cash: 9200,
          portfolio_assets: 836.4,
          total_equity: 10036.4,
          equity_gain_pct: 0.36,
          today_gain: 36.4,
          today_gain_pct: 0.36,
        },
      };
    case "get_positions":
      return { status: "success", data: { positions: cloneFallback(demoPositions) } };
    case "get_settings":
      return demoSettingsResponse();
    case "update_settings":
      return { status: "success", data: { settings: args.newSettingsDict || {} } };
    case "news_check":
      return { status: "success", message: "Demo news check completed." };
    case "check_stock":
      return { status: "success", message: "Demo position risk check completed." };
    case "sell_everything":
      return { status: "success", message: "Demo liquidation request accepted." };
    case "buy_action":
      return { status: "success", message: `Demo buy accepted for ${args.ticker}.` };
    case "sell_action":
      return { status: "success", message: "Demo sell accepted." };
    case "get_companies":
      return { status: "success", data: Object.keys(companyProfiles || {}) };
    default:
      return { status: "success", message: `Demo command ${command} completed.` };
  }
}

const invoke = tauriInvoke ?? demoInvoke;

async function apiGet(path, fallback) {
  if (USE_DEMO_DATA) return cloneFallback(fallback);

  try {
    const response = await fetch(`${API_BASE}${path}`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return await response.json();
  } catch (error) {
    console.warn(`API fallback for ${path}:`, error);
    return cloneFallback(fallback);
  }
}

async function apiPost(path, payload, fallback) {
  if (USE_DEMO_DATA) return cloneFallback(fallback);

  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return await response.json();
}
