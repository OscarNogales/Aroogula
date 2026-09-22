"""Trading news analyzer orchestrator.

TradeAnalyzer coordinates the decision pipeline. The specialized work lives in
small services:
- MarketDataService collects market/ticker features.
- MarketRegimeAnalyzer classifies the current regime.
- RiskGuard blocks unsafe buy environments.
- FinBERTClassifier performs the fast NLP filter.
- LLMDecisionEngine asks Ollama for the deeper decision.
- AILogger stores the final structured decision record.

This version also emits lightweight runtime events through backend.app.event_bus so
that the frontend can update AI activity, portfolio cards, and charts while a
news scan is running.
"""

from __future__ import annotations

import logging
import sqlite3 as sql
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import pytz
from uuid import uuid4

from backend.app.event_bus import event_bus
from backend.analysis.decision_context import DecisionContextBuilder
from backend.analysis.finbert import FinBERTClassifier
from backend.analysis.llm import LLMDecisionEngine
from backend.market.market_data import MarketDataService
from backend.market.regime import RISK_PROFILES, MarketRegimeAnalyzer
from backend.analysis.risk_guard import RiskGuard

logger = logging.getLogger(__name__)


class TradeAnalyzer:
    """Coordinates news scanning, AI decisions, logging, and trade execution."""

    def __init__(
        self,
        broker,
        dossier,
        memory,
        settings,
        bot_state,
        ai_logger,
        edgar_db_path: str | None = None,
        yahoo_db_path: str | None = None,
        forbes_db_path: str | None = None,
        bloomberg_db_path: str | None = None,
        finbert_device: str = "cpu",
        finbert_model_path: str | Path = "models/best_model",
        ollama_app_path: str | None = None,
    ):
        self.broker = broker
        self.dossier = dossier
        self.memory = memory
        self.settings = settings
        self.bot_state = bot_state
        self.ai_logger = ai_logger

        self.edgar_db_path = edgar_db_path
        self.yahoo_db_path = yahoo_db_path
        self.forbes_db_path = forbes_db_path
        self.bloomberg_db_path = bloomberg_db_path

        self.settings_dict = self._load_settings()
        self.llm_model_name = self.settings_dict.get("LLM_model", "deepseek-r1")
        self.risk_profile = RISK_PROFILES["ACCUMULATION"].copy()

        market_data_mode = getattr(
            self.broker,
            "mode",
            self.settings_dict.get("trading_mode", "local_sim"),
        )
        self.market_data = self._create_market_data_service(mode=market_data_mode)
        self.market_regime_analyzer = MarketRegimeAnalyzer(self.market_data)
        self.risk_guard = RiskGuard(self.market_data, self.bot_state)
        self.context_builder = DecisionContextBuilder(self.market_data)
        self.finbert = FinBERTClassifier(finbert_model_path, device=finbert_device)
        self.llm_engine = LLMDecisionEngine(self.llm_model_name, ollama_app_path=ollama_app_path)

        self.seen_ids: set[str] = self._load_seen_news_ids()
        self.fresh_news = pd.DataFrame()

        self._configure_scheduler()
        logger.info("TradeAnalyzer initialized with model=%s.", self.llm_model_name)

    # ------------------------------------------------------------------
    # Lifecycle / settings
    # ------------------------------------------------------------------

    def _load_settings(self) -> dict:
        self.settings.settings = self.settings._load_settings()
        return self.settings.settings

    def _create_market_data_service(self, *, mode: str):
        """Create MarketDataService with explicit execution mode.

        The try/except keeps this compatible if an older MarketDataService still
        does not accept a mode argument. In that case, we attach the attributes
        manually so get_current_price() still has self.mode and self.client.
        """
        alpaca_client = getattr(self.broker, "client", None)

        try:
            return MarketDataService(alpaca_client=alpaca_client, mode=mode)
        except TypeError:
            service = MarketDataService(alpaca_client=alpaca_client)
            service.client = alpaca_client
            service.mode = mode
            return service

    def _configure_scheduler(self) -> None:
        """Create and start the background news-check scheduler."""
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger

        self.scheduler = BackgroundScheduler(timezone="America/New_York")
        self.scheduler.add_job(
            self.check_news,
            trigger=CronTrigger(
                day_of_week="mon-fri",
                hour="9-16",
                minute="1,16,31,46",
                timezone="America/New_York",
            ),
            id="check_news_loop",
            replace_existing=True,
        )
        self.scheduler.pause_job("check_news_loop")
        self._sync_scheduler()
        self.scheduler.start()
        self.scheduler.pause_job("check_news_loop")

    def _sync_scheduler(self) -> None:
        status = self.bot_state.data.get("bot_status", "PAUSED")
        if status == "ACTIVE":
            self.scheduler.resume_job("check_news_loop")
        else:
            self.scheduler.pause_job("check_news_loop")

    def toggle_Aroogula(self, turn_on: bool):
        if turn_on:
            can_activate, reason = self.bot_state.can_activate_bot()

            if not can_activate:
                self.bot_state.data["bot_status"] = "PAUSED"
                self._sync_scheduler()

                return {
                    "status": "rejected",
                    "message": reason,
                    "data": {
                        "bot_status": "PAUSED",
                    },
                }

            self.bot_state.data["bot_status"] = "ACTIVE"
            self._sync_scheduler()

            return {
                "status": "success",
                "message": "Bot activated.",
                "data": {
                    "bot_status": "ACTIVE",
                },
            }

        self.bot_state.data["bot_status"] = "PAUSED"
        self._sync_scheduler()

        return {
            "status": "success",
            "message": "Bot paused.",
            "data": {
                "bot_status": "PAUSED",
            },
        }

    # ------------------------------------------------------------------
    # Event helpers
    # ------------------------------------------------------------------

    def _emit(self, event_type: str, payload: dict | None = None) -> None:
        """Publish a UI event without letting event failures break trading."""
        try:
            event_bus.publish(event_type, payload or {})
        except Exception:
            logger.exception("Failed to publish event: %s", event_type)

    @staticmethod
    def _new_cycle_summary() -> dict:
        return {
            "news_scanned": 0,
            "finbert_rejected": 0,
            "llm_wait": 0,
            "buys_executed": 0,
            "errors": 0,
        }

    # ------------------------------------------------------------------
    # Backward-compatible helpers formerly implemented in this class
    # ------------------------------------------------------------------

    def _get_change_and_history(self, ticker_symbol: str, period: str = "90d"):
        return self.market_data.get_change_and_history(ticker_symbol, period)

    def _get_market_indices(self) -> dict:
        return self.market_data.get_index_snapshot()

    def _analyze_market_regime(self) -> dict:
        self.risk_profile = self.market_regime_analyzer.analyze()
        return self.risk_profile

    def _get_finbert_prediction(self, text: str) -> tuple[str, bool, float, float]:
        result = self.finbert.predict(text)
        return (
            result["sentiment"],
            result["tradeable"],
            result["sentiment_score"],
            result["tradeable_score"],
        )

    def _get_ai_decision(self, title: str, summary: str, ticker: str):
        return self._run_llm_decision(title=title, summary=summary, ticker=ticker)

    def _is_market_crashing(self):
        return self.risk_guard._is_market_crashing(self.settings_dict)["rejected"]

    def _check_panic_assets(self):
        return self.risk_guard._check_panic_assets(self.settings_dict)["rejected"]

    def _check_economic_calendar(self):
        return self.risk_guard._check_economic_calendar(self.settings_dict)["rejected"]

    # ------------------------------------------------------------------
    # News loading
    # ------------------------------------------------------------------

    def _process_unred_news(self) -> pd.DataFrame:
        """Load fresh, unseen news from enabled scraper databases."""
        logger.info("Fetching unseen news for AI analysis.")
        nyc_tz = pytz.timezone("America/New_York")
        nyc_cutoff = (datetime.now(nyc_tz) - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")

        frames = []

        if self.settings_dict.get("Yahoo bot"):
            frames.append(
                self._read_news_source(
                    db_path=self.yahoo_db_path,
                    source="Yahoo",
                    query="""
                        SELECT id, title, summary, ticker, pubDate AS date
                        FROM news
                        WHERE pubDate >= ?
                    """,
                    params=(nyc_cutoff,),
                )
            )

        if self.settings_dict.get("Bloomberg bot"):
            frames.append(
                self._read_news_source(
                    db_path=self.bloomberg_db_path,
                    source="Bloomberg",
                    query="""
                        SELECT link AS id, title, summary, ticker, published AS date
                        FROM news
                        WHERE published >= ? AND ticker IS NOT NULL
                    """,
                    params=(nyc_cutoff,),
                )
            )

        if self.settings_dict.get("EDGAR bot"):
            frames.append(
                self._read_news_source(
                    db_path=self.edgar_db_path,
                    source="EDGAR",
                    query="""
                        SELECT accession_number AS id,
                               form AS title,
                               primaryDocument AS summary,
                               ticker,
                               filing_date AS date
                        FROM edgar_filings
                        WHERE filing_date >= ?
                    """,
                    params=(nyc_cutoff,),
                )
            )

        if self.settings_dict.get("Forbes bot"):
            frames.append(
                self._read_news_source(
                    db_path=self.forbes_db_path,
                    source="Forbes",
                    query="""
                        SELECT id, title, summary, ticker, pubDate AS date
                        FROM forbes_news
                        WHERE pubDate >= ?
                    """,
                    params=(nyc_cutoff,),
                )
            )

        valid_frames = [frame for frame in frames if frame is not None and not frame.empty]
        if not valid_frames:
            self.fresh_news = pd.DataFrame()
            return self.fresh_news

        combined_news = pd.concat(valid_frames, ignore_index=True)
        combined_news["id"] = combined_news["id"].astype(str)
        combined_news["ticker"] = combined_news["ticker"].astype(str).str.upper()
        combined_news["date_utc"] = pd.to_datetime(
            combined_news["date"],
            errors="coerce",
            utc=True,
             format="mixed"
        )

        cutoff_utc = pd.Timestamp.now(tz="UTC") - pd.Timedelta(hours=24)

        news_mask = (
                combined_news["date_utc"].notna()
                & (combined_news["date_utc"] >= cutoff_utc)
                & (~combined_news["id"].isin(self.seen_ids))
            )


        fresh_news = combined_news[news_mask].copy()
        if fresh_news.empty:
            self.fresh_news = pd.DataFrame()
            return self.fresh_news

        self.seen_ids.update(fresh_news["id"].tolist())
        self.fresh_news = fresh_news
        return self.fresh_news

    def _read_news_source(self, *, db_path: str | None, source: str, query: str, params: tuple) -> pd.DataFrame:
        if not db_path:
            return pd.DataFrame()
        try:
            with sql.connect(db_path) as conn:
                df = pd.read_sql(query, conn, params=params)
            if not df.empty:
                df["Source"] = source
            return df
        except Exception:
            logger.exception("Failed to read %s news database at %s.", source, db_path)
            return pd.DataFrame()

    def _load_seen_news_ids(self) -> set[str]:
        if self.ai_logger is None:
            return set()

        try:
            decisions = self.ai_logger.get_all()

            if decisions.empty or "news_id" not in decisions.columns:
                return set()

            return set(
                decisions["news_id"]
                .dropna()
                .astype(str)
                .tolist()
            )

        except Exception:
            logger.exception("Unable to retrieve seen ids from ai_logger.")
            return set()


    # ------------------------------------------------------------------
    # Decision pipeline
    # ------------------------------------------------------------------

    def check_news(self) -> dict:
        """Run one complete news scan and emit frontend-friendly events."""
        self.settings_dict = self._load_settings()
        self.llm_model_name = self.settings_dict.get("LLM_model", self.llm_model_name)

        cycle_summary = self._new_cycle_summary()
        actions_taken: list[dict] = []
        last_finbert_rejections: list[dict] = []
        last_llm_rejections: list[dict] = []

        self._emit("cycle_started", {
            "message": "News check started.",
            "model": self.llm_model_name,
        })

        self.risk_profile = self.market_regime_analyzer.analyze()

        risk_result = self.risk_guard.evaluate_global_buy_halt(self.settings_dict)
        if risk_result["rejected"]:
            message = risk_result.get("reason") or "Risk guard halted new buys."
            logger.warning("News scan halted by risk guard: %s", message)

            self._emit("risk_halt", {
                "message": message,
                "reason": risk_result.get("reason"),
                "risk_level": risk_result.get("risk_level"),
            })
            self._emit("cycle_complete", {
                "message": message,
                "cycle_summary": cycle_summary,
                "actions_taken": actions_taken,
            })

            return {
                "status": "error",
                "message": message,
                "data": {
                    "cycle_summary": cycle_summary,
                    "actions_taken": actions_taken,
                },
                "actions_taken": actions_taken,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }

        fresh_news = self._process_unred_news()
        if fresh_news.empty:
            logger.info("No fresh news found in this cycle.")
            self._emit("cycle_complete", {
                "message": "No fresh news found.",
                "cycle_summary": cycle_summary,
                "actions_taken": actions_taken,
            })
            return {
                "status": "success",
                "message": "No new news found.",
                "data": {
                    "cycle_summary": cycle_summary,
                    "actions_taken": actions_taken,
                },
                "actions_taken": actions_taken,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }

        cycle_summary["news_scanned"] = int(len(fresh_news))

        for _, row in fresh_news.iterrows():
            ticker = str(row.get("ticker", "")).upper()

            self._emit("ai_activity", {
                "level": "info",
                "message": f"Evaluating {ticker}.",
                "ticker": ticker,
            })

            try:
                result = self._evaluate_opportunity_from_row(row)
            except Exception:
                logger.exception("Unhandled error while evaluating %s.", ticker)
                result = {
                    "status": "error",
                    "stage": "error",
                    "ticker": ticker,
                    "reason": "Unhandled error during AI evaluation.",
                }

            stage = result.get("stage", "unknown")

            if stage == "finbert_rejected":
                cycle_summary["finbert_rejected"] += 1
                last_finbert_rejections.append({
                    "ticker": ticker,
                    "reason": result.get("reason"),
                    "sentiment": result.get("sentiment"),
                    "tradeable_score": result.get("tradeable_score"),
                })

                if cycle_summary["finbert_rejected"] % 5 == 0:
                    self._emit("ai_rejected_batch", {
                        "kind": "finbert",
                        "message": f"{cycle_summary['finbert_rejected']} news rejected by FinBERT.",
                        "rejected_count": cycle_summary["finbert_rejected"],
                        "last_rejections": last_finbert_rejections[-5:],
                    })

            elif stage == "llm_wait":
                cycle_summary["llm_wait"] += 1
                last_llm_rejections.append({
                    "ticker": ticker,
                    "reason": result.get("reason"),
                    "signal": result.get("signal"),
                    "confidence": result.get("confidence"),
                })

                if cycle_summary["llm_wait"] % 5 == 0:
                    self._emit("ai_rejected_batch", {
                        "kind": "llm",
                        "message": f"{cycle_summary['llm_wait']} news rejected by {self.llm_model_name}.",
                        "rejected_count": cycle_summary["llm_wait"],
                        "last_rejections": last_llm_rejections[-5:],
                    })

            elif stage == "buy_executed":
                cycle_summary["buys_executed"] += 1
                actions_taken.append(result)

                self._emit("trade_executed", self._trade_executed_payload(result))
                self._emit("portfolio_changed", {
                    "reason": "buy_executed",
                    "ticker": ticker,
                })

            elif stage in {"error", "buy_error"}:
                cycle_summary["errors"] += 1
                actions_taken.append(result)
                self._emit("ai_error", {
                    "ticker": ticker,
                    "message": result.get("reason") or result.get("message") or "AI pipeline error.",
                    "stage": stage,
                })

        logger.info("News scan finished. Processed %d items.", len(fresh_news))

        self._emit("cycle_complete", {
            "message": "News check completed.",
            "cycle_summary": cycle_summary,
            "actions_taken": actions_taken,
        })

        return {
            "status": "success",
            "message": f"Processed {len(fresh_news)} news items.",
            "data": {
                "cycle_summary": cycle_summary,
                "actions_taken": actions_taken,
            },
            "actions_taken": actions_taken,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    def _evaluate_opportunity_from_row(self, row: pd.Series | dict) -> dict:
        ticker = str(row.get("ticker", "")).upper()
        title = row.get("title", "") or ""
        summary = row.get("summary", "") or ""
        news_id = str(row.get("id"))

        context = self.context_builder.build(
            news_row=row,
            risk_profile=self.risk_profile,
            settings=self.settings_dict,
        )

        return self._evaluate_opportunity(
            ticker=ticker,
            title=title,
            summary=summary,
            news_id=news_id,
            context=context,
        )

    def _evaluate_opportunity(self, ticker: str, title: str, summary: str, news_id: str, context: dict | None = None) -> dict:
        """Evaluate one news item and optionally execute a trade."""

        decision_id = f"DEC-{uuid4().hex[:8].upper()}"

        logger.info("Evaluating opportunity for %s. Decision ID: %s", ticker, decision_id)
        text = f"{title} {summary}".strip()
        
        if context is None:
            context = self.context_builder.build(
                news_row={"id": news_id, "ticker": ticker, "title": title, "summary": summary},
                risk_profile=self.risk_profile,
                settings=self.settings_dict,
            )

        finbert_result = self._run_finbert_filter(text)
        if not finbert_result["approved"]:
            self._log_ai_decision(
                context=context,
                finbert_result=finbert_result,
                ai_result={
                    "signal": "SKIP",
                    "confidence": finbert_result.get("tradeable_score"),
                    "reasoning": finbert_result["reason"],
                },
                decision_result="rejected",
                risk_result={"rejected": False, "risk_level": "LOW", "reason": None},
                linked_trade_id=None,
                decision_id=decision_id
            )
            logger.info("FinBERT rejected %s: %s", ticker, finbert_result["reason"])
            return {
                "status": "ignored",
                "stage": "finbert_rejected",
                "ticker": ticker,
                "reason": finbert_result["reason"],
                "sentiment": finbert_result.get("sentiment"),
                "sentiment_score": finbert_result.get("sentiment_score"),
                "tradeable": bool(finbert_result.get("tradeable", False)),
                "tradeable_score": finbert_result.get("tradeable_score"),
                "decision_id": decision_id
            }

        self._emit("finbert_approved", {
            "ticker": ticker,
            "message": f"FinBERT approved {ticker}.",
            "sentiment": finbert_result.get("sentiment"),
            "sentiment_score": finbert_result.get("sentiment_score"),
            "tradeable_score": finbert_result.get("tradeable_score"),
            "decision_id": decision_id
        })

        self._emit("llm_started", {
            "ticker": ticker,
            "message": f"Running LLM decision for {ticker}. Decision ID: {decision_id}",
        })

        ai_result = self._run_llm_decision(title=title, summary=summary, ticker=ticker)
        if ai_result is None:
            self._emit("llm_completed", {
                "ticker": ticker,
                "signal": None,
                "confidence": None,
                "message": "LLM decision failed.",
            })
            self._log_ai_decision(
                context=context,
                finbert_result=finbert_result,
                ai_result={"signal": "SKIP", "confidence": None, "reasoning": "LLM connection or parsing failed."},
                decision_result="error",
                risk_result={"rejected": False, "risk_level": "MEDIUM", "reason": "LLM error"},
                linked_trade_id=None,
                decision_id=decision_id
            )
            return {
                "status": "error",
                "stage": "error",
                "ticker": ticker,
                "reason": "AI connection failed",
            }

        signal = str(ai_result.get("signal", "WAIT")).upper()
        confidence = float(ai_result.get("confidence", 0.0) or 0.0)
        min_buy_conf = self.risk_profile.get("BUY_CONF", 0.75)
        logger.info("AI decision for %s: signal=%s confidence=%.2f", ticker, signal, confidence)

        self._emit("llm_completed", {
            "ticker": ticker,
            "signal": signal,
            "confidence": confidence,
            "message": f"LLM decided {signal} for {ticker} with {confidence:.2f} confidence.",
        })

        if signal != "BUY" or confidence < min_buy_conf:
            self._log_ai_decision(
                context=context,
                finbert_result=finbert_result,
                ai_result=ai_result,
                decision_result="skipped",
                risk_result={"rejected": False, "risk_level": "LOW", "reason": None},
                linked_trade_id=None,
                decision_id=decision_id
            )
            return {
                "status": "ignored",
                "stage": "llm_wait",
                "ticker": ticker,
                "signal": signal,
                "confidence": confidence,
                "reason": f"AI decided {signal} with {confidence:.2f} confidence.",
                "reasoning": ai_result.get("reasoning", ""),
            }

        broker_response = self._execute_ai_buy(ticker=ticker, news_id=news_id, ai_result=ai_result, decision_id=decision_id)
        linked_trade_id = self._extract_trade_id(broker_response)
        decision_result = "executed" if broker_response.get("status") == "success" else "error"
        risk_result = {"rejected": False, "risk_level": "LOW", "reason": None}

        self._log_ai_decision(
            context=context,
            finbert_result=finbert_result,
            ai_result=ai_result,
            decision_result=decision_result,
            risk_result=risk_result,
            linked_trade_id=linked_trade_id,
            decision_id=decision_id
        )

        if broker_response.get("status") == "success":
            self._save_trade_memory(ticker=ticker, news_id=news_id, text=text, ai_result=ai_result)
            broker_response["stage"] = "buy_executed"
            broker_response["memory_saved"] = True
        else:
            broker_response["stage"] = "buy_error"
            broker_response["reason"] = broker_response.get("message") or broker_response.get("reason") or "Broker buy failed."

        broker_response["ticker"] = ticker
        broker_response["signal"] = signal
        broker_response["confidence"] = confidence
        broker_response["reasoning"] = ai_result.get("reasoning", "")
        broker_response["linked_trade_id"] = linked_trade_id
        return broker_response

    def _run_finbert_filter(self, text: str) -> dict:
        result = self.finbert.predict(text)
        min_sent_conf = self.risk_profile.get("FINBERT_SENT", 0.55)
        min_trad_conf = self.risk_profile.get("FINBERT_TRAD", 0.55)

        approved = (
            result["sentiment"] == "positive"
            and bool(result["tradeable"])
            and result["sentiment_score"] >= min_sent_conf
            and result["tradeable_score"] >= min_trad_conf
        )

        reason = (
            "Approved by FinBERT"
            if approved
            else (
                f"FinBERT rejected: sentiment={result['sentiment']} "
                f"sentiment_score={result['sentiment_score']:.2f} "
                f"tradeable={result['tradeable']} "
                f"tradeable_score={result['tradeable_score']:.2f}"
            )
        )

        return {**result, "approved": approved, "reason": reason}

    def _run_llm_decision(self, *, title: str, summary: str, ticker: str) -> dict | None:
        text = f"{title} {summary}".strip()
        try:
            vector = self.memory.vectorize_string(text)
            results = self.memory.search_memory(ticker, vector)
            memory_context = self.memory.format_memory_for_prompt(results, max_distance=0.6)
        except Exception:
            logger.exception("Failed to retrieve memory context for %s.", ticker)
            memory_context = ""

        try:
            company_dossier = self.dossier.get(ticker)
        except Exception:
            logger.exception("Failed to retrieve dossier for %s.", ticker)
            company_dossier = ""

        return self.llm_engine.decide(
            title=title,
            summary=summary,
            ticker=ticker,
            company_dossier=company_dossier,
            memory_context=memory_context,
            risk_profile=self.risk_profile,
        )

    def _execute_ai_buy(self, *, ticker: str, news_id: str, ai_result: dict, decision_id: str) -> dict:
        try:
            wallet_state = self.broker.wallet.get_balance()
            cash = float(wallet_state["data"]["equity"])
            risk_per_trade = float(self.settings_dict.get("trade_risk_per_trade_pct", 0.005))
            amount_to_buy = cash * risk_per_trade
            take_profit_pct = float(self.settings_dict.get("trade_target_gain_pct", 0.05))
            stop_loss_pct = float(self.settings_dict.get("trade_stop_loss_pct", 0.03))

            logger.info("Executing AI buy for %s: amount=%.2f", ticker, amount_to_buy)
            response = self.broker.buy(
                ticker=ticker,
                invest_amount=amount_to_buy,
                buy_reason=ai_result.get("reasoning", ""),
                news_id=news_id,
                decision_id=decision_id,
                ai_confidence=ai_result.get("confidence", 0.5),
                stop_loss_pct=stop_loss_pct,
                take_profit_pct=take_profit_pct,
            )

            if isinstance(response, dict):
                response["requested_amount"] = amount_to_buy
                response["risk_per_trade_pct"] = risk_per_trade
                response["take_profit_pct"] = take_profit_pct
                response["stop_loss_pct"] = stop_loss_pct
            return response

        except Exception:
            logger.exception("Broker buy failed for %s.", ticker)
            return {"status": "error", "message": "Broker buy failed."}

    def _trade_executed_payload(self, result: dict) -> dict:
        data = result.get("data") if isinstance(result.get("data"), dict) else {}
        return {
            "side": "BUY",
            "ticker": result.get("ticker"),
            "trade_id": result.get("linked_trade_id") or data.get("trade_id"),
            "shares": data.get("shares"),
            "price": data.get("price") or data.get("entry_price") or data.get("buy_price"),
            "amount": result.get("requested_amount"),
            "confidence": result.get("confidence"),
            "reasoning": result.get("reasoning"),
            "data": data,
        }

    def _save_trade_memory(self, *, ticker: str, news_id: str, text: str, ai_result: dict) -> None:
        try:
            vector = self.memory.vectorize_string(text)
            self.memory.save_memory(
                ticker=ticker,
                database_id=news_id,
                text=text,
                vector_array=vector,
                macro_state=self.risk_profile,
                ai_decision=f"BOUGHT (Conf: {float(ai_result.get('confidence', 0.0)):.2f}) - {ai_result.get('reasoning', '')}",
            )
            logger.info("Market memory updated for %s.", ticker)
        except Exception:
            logger.exception("Failed to save market memory for %s.", ticker)

    def _log_ai_decision(
        self,
        *,
        context: dict,
        finbert_result: dict,
        ai_result: dict | None,
        decision_result: str,
        risk_result: dict | None,
        linked_trade_id: str | None,
        decision_id: str | None
    ) -> None:
        if self.ai_logger is None:
            return

        ai_result = ai_result or {}
        risk_result = risk_result or {}

        entry = {
            **context,
            "ai_signal": str(ai_result.get("signal", "SKIP")).upper(),
            "ai_confidence": ai_result.get("confidence"),
            "ai_reasoning": ai_result.get("reasoning"),
            "decision_result": decision_result,
            "linked_trade_id": linked_trade_id,
            "finbert_sentiment": finbert_result.get("sentiment"),
            "finbert_sentiment_score": finbert_result.get("sentiment_score"),
            "finbert_tradeable": int(bool(finbert_result.get("tradeable", False))),
            "finbert_tradeable_score": finbert_result.get("tradeable_score"),
            "risk_level": risk_result.get("risk_level"),
            "rejected_by_risk_guard": int(bool(risk_result.get("rejected", False))),
            "risk_guard_reason": risk_result.get("reason"),
            "decision_id": decision_id
        }

        try:
            self.ai_logger.save_entry(entry)
        except Exception:
            logger.exception("Failed to save AI decision log for %s.", context.get("ticker"))

    @staticmethod
    def _extract_trade_id(response: dict) -> str | None:
        data = response.get("data") if isinstance(response, dict) else None
        if isinstance(data, dict):
            return data.get("trade_id")
        return None