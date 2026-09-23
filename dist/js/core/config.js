"use strict";

// Global frontend configuration.
// Keep environment flags here so demo/real backend behavior is easy to change.

const API_BASE = "";

const USE_DEMO_DATA = false;
const USE_DEMO_POSITIONS_WHEN_EMPTY = false; // Development-only fallback. Disable for real trading tests.

const POLLING_INTERVALS = {
  equitySummaryMs: 5 * 60 * 1000,
  activityMs: 5 * 1000,
  schedulerMs: 15 * 1000,
  portfolioMs: 15 * 1000,
  newsCheckMs: 5 * 60 * 1000,
};

const COMPARISON_COLORS = [
  "#24D26C",
  "#3A92FF",
  "#FFB84D",
  "#A78BFA",
  "#F472B6",
];
