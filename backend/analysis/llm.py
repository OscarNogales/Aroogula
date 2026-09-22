"""Ollama-backed LLM decision engine."""

from __future__ import annotations

import json
import os
import logging
import shutil
import subprocess
from pathlib import Path
from time import sleep
from urllib.error import URLError
from urllib.request import urlopen

import requests

logger = logging.getLogger(__name__)


class LLMDecisionEngine:
    """Ensures Ollama is available and requests structured trade decisions."""

    def __init__(self, model_name: str, ollama_app_path: str | None = None):
        self.model_name = model_name
        self.ollama_app_path = ollama_app_path or os.getenv("OLLAMA_APP_PATH") or shutil.which("ollama") or "ollama"
        self._ensure_ready()

    def _is_ollama_installed(self) -> bool:
        return shutil.which("ollama") is not None or Path(self.ollama_app_path).exists()

    def _is_server_running(self, timeout: float = 3) -> bool:
        try:
            with urlopen("http://localhost:11434/api/tags", timeout=timeout) as response:
                return response.status == 200
        except (URLError, TimeoutError, OSError):
            return False

    def _start_server(self) -> None:
        if self._is_server_running():
            logger.info("Ollama server is already running.")
            return

        logger.info("Starting Ollama server.")
        subprocess.Popen(
            [self.ollama_app_path],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

        for _ in range(10):
            if self._is_server_running(timeout=1):
                logger.info("Ollama server started successfully.")
                return
            sleep(0.5)

        raise RuntimeError("Ollama could not be started.")

    def _is_model_installed(self) -> bool:
        try:
            response = requests.get("http://localhost:11434/api/tags", timeout=5)
            response.raise_for_status()
            models = response.json().get("models", [])
            model_names = {model.get("name") for model in models}
            return self.model_name in model_names
        except Exception:
            logger.exception("Failed to list Ollama models.")
            return False

    def _ensure_ready(self) -> None:
        if not self._is_ollama_installed():
            raise RuntimeError("Ollama was not found. Install Ollama or configure ollama_app_path.")

        self._start_server()

        if not self._is_model_installed():
            raise RuntimeError(f"Ollama model {self.model_name!r} is not installed. Run: ollama pull {self.model_name}")

        logger.info("Ollama is ready with model %s.", self.model_name)

    def decide(self, *, title: str, summary: str, ticker: str, company_dossier: str, memory_context: str, risk_profile: dict) -> dict | None:
        """Request a structured BUY/WAIT decision from Ollama."""
        regime_warnings = {
            "MARKUP": "🟢 MACRO REGIME: MARKUP (Bull Market). Reward momentum and growth catalysts heavily. The market is forgiving, let winners run.",
            "DISTRIBUTION": "🟡 MACRO REGIME: DISTRIBUTION (Market Top / Slow Bleed). Institutions are secretly selling. Be EXTREMELY conservative. Only approve undeniable, historic catalysts. Fake rallies are common.",
            "MARKDOWN": "🔴 MACRO REGIME: MARKDOWN (Bear Market). Fear is high. Good news is usually ignored or used as exit liquidity. Be extremely pessimistic.",
            "ACCUMULATION": "🔵 MACRO REGIME: ACCUMULATION (Bottoming). The market is sideways. Look specifically for 'Turnaround' or 'Breakout' news that shows the company is waking up.",
        }
        regime = risk_profile.get("REGIME", "DISTRIBUTION")
        regime_warning = regime_warnings.get(regime, regime_warnings["DISTRIBUTION"])

        prompt = f"""
            You are an elite proprietary momentum trader looking for asymmetrical, multi-day upside.

            Company Context (Dossier): {company_dossier}

            {memory_context}

            Current News Headline: {title}
            Current News Summary: {summary}

            Task: Evaluate if this current news is a powerful enough catalyst to trigger sustained institutional buying and multi-day price growth for {ticker}.

            ENVIRONMENT & RULES:
            {regime_warning}

            TRADER FRAMEWORK:
            - Context is King: Does this news directly solve a major problem mentioned in the dossier or massively accelerate their core growth engine?
            - Historical Precedent: Review your 'Past Memories' (if any exist). Have you seen a catalyst mathematically similar to this before? Did you BUY or WAIT?
            - The Multi-Day Tailwind: Is this an unexpected, systemic shift that will cause the stock to run for the next 1 to 5 days, or just a brief retail spike?
            - Ignore the Noise: Strictly filter out generic CEO optimism, minor product tweaks, analyst chatter, or broad macro news.

            Respond ONLY in valid JSON format with the following keys:
            "signal": "BUY" or "WAIT",
            "confidence": float from 0.0 to 1.0,
            "reasoning": one concise sentence explaining the decision.
            """

        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "format": "json",
        }

        try:
            response = requests.post("http://localhost:11434/api/generate", json=payload, timeout=120)
            response.raise_for_status()
            result_text = response.json()["response"]
            data = json.loads(result_text)
            return {
                "signal": data.get("signal", "WAIT"),
                "confidence": float(data.get("confidence", 0.0)),
                "reasoning": data.get("reasoning", ""),
            }
        except Exception:
            logger.exception("Failed to call Ollama model %s for ticker %s.", self.model_name, ticker)
            return None
