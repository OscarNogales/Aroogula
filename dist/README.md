# Trading Dashboard Frontend

A Tauri trading-dashboard frontend for portfolio monitoring, equity cards, ticker charts, technical indicators, comparison charts, manual trading controls, AI activity, and trade-journal review.

The codebase still uses classic browser scripts instead of ES modules. This keeps it compatible with the current Tauri/Rust bridge and avoids a bundler migration while still keeping files separated by responsibility.

## Project structure

```text
index.html
styles/
  main.css                         # CSS entrypoint; imports all feature styles
  base.css                         # Global variables, reset, base layout
  chart.css                        # Chart area, topbar, chart settings menu
  compare.css                      # Compare dropdown and chips
  indicator.css                    # Indicator menu and toggles
  panels.css                       # Dashboard panels and trading controls
  activity.css                     # AI activity and trade journal styles
  overlays.css                     # Modal/drawer/toast overlays
  responsive.css                   # Responsive behavior
js/
  core/
    config.js                      # Feature flags, polling intervals, shared constants
    state.js                       # Shared runtime state object
  data/
    company-profiles.js            # Lightweight company metadata for UI labels
    demo-data.js                   # Demo/fallback positions, journal, activity, scheduler
  services/
    api.js                         # Tauri invoke bridge and HTTP fallback helpers
  utils/
    helpers.js                     # Formatting, ticker metadata lookup, toasts
  features/
    portfolio/
      summary-cards.js             # Total Equity and Today's Gain cards
      positions.js                 # Portfolio table, position normalization, sell dropdown
    trading/
      actions.js                   # Buy, sell, liquidate, and post-trade refresh
    compare/
      compare.js                   # Multi-ticker percentage comparison chart
    activity/
      activity.js                  # Scheduler, live activity, trade journal, modal/drawer
    settings/
      settings.js                  # News-source toggles and AI risk/model settings
    analyzer/
      trade-analyzer.js            # START/STOP news analyzer loop
    chart/
      chart-state.js               # Chart globals and portfolio series config
      chart-demo.js                # Local demo candle generator
      chart-options.js             # Grid/theme option builders
      chart-adapters.js            # Lightweight Charts compatibility wrappers
      chart-lifecycle.js           # Chart create/destroy/message lifecycle
      chart-normalizers.js         # Backend response normalization
      chart-ticker.js              # Ticker candlestick renderer
      chart-portfolio.js           # Portfolio/equity renderer
      chart-router.js              # renderCurrentChart dispatcher
      chart-display-controls.js    # Grid, crosshair, theme, fit controls
      chart-actions.js             # Fullscreen, PNG export, settings menu
      chart-indicator-controls.js  # EMA20 and volume toolbar controls
    indicators/
      math.js                      # Shared indicator constants and math helpers
      calculators.js               # RSI, Bollinger, EMA, MACD, ATR calculations
      renderers.js                 # Lightweight Charts indicator drawing functions
      controller.js                # Indicator menu, toggle state, redraw orchestration
  main.js                          # App bootstrap and polling setup
```

## Runtime flow

```text
main.js
  initUiControls()
  loadInitialDashboardData()
    fetchEquitySummary()
    loadPortfolio()
    loadTradeJournal()
    loadActivity()
    loadScheduler()
    getCompanies()
  renderCurrentChart()
  startPolling()
```

## Backend bridge

Most real data comes through Rust/Tauri commands using `invoke(...)`:

```text
get_equity_summary
get_positions
equity_log_graph
ticker_graph
buy_action
sell_action
sell_everything
news_check
get_companies
update_settings
toggle_bloomberg / toggle_yahoo / toggle_forbes / toggle_edgar
```

The frontend expects `get_equity_summary` to return fields like:

```json
{
  "data": {
    "cash": 1000,
    "portfolio_assets": 9000,
    "total_equity": 10000,
    "equity_gain_pct": 1.2,
    "today_gain": 120,
    "today_gain_pct": 1.2
  }
}
```

`summary-cards.js` unwraps common response shapes such as `{ data: ... }`, `{ payload: ... }`, or the raw object.

## Validation

All JavaScript files were checked with:

```bash
find js -name '*.js' -print0 | xargs -0 -n1 node --check
```

Additional static checks were run for missing script references and missing `getElementById(...)` targets.
