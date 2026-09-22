import json
from datetime import datetime, timedelta
import pandas as pd
from pathlib import Path
import pytz
import sqlite3 as sql
import requests
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import logging

logger = logging.getLogger(__name__)

class Dossiers():
    def __init__(self, 
                 dossier_path: str,
                 company_profile_path: str,
                 forbes_db_path: str,
                 edgar_db_path: str,
                 yahoo_db_path: str,
                 bloomberg_db_path: str,
                 reuters_db_path: str,
                 companies_csv_path: str):

        # Context and profiles
        self.company_profile_path = company_profile_path      
        self.dossier_path = dossier_path
        self.dossiers = self.load_dossiers()
        self.companies_profiles = self.load_company_profiles()
        
        
        # DB paths
        self.forbes_db_path = forbes_db_path
        self.edgar_db_path = edgar_db_path
        self.yahoo_db_path = yahoo_db_path
        self.bloomberg_db_path = bloomberg_db_path
        self.reuters_db_path = reuters_db_path

        # Companies CSV
        self.companies_csv_path = companies_csv_path
        self.companies = pd.read_csv(self.companies_csv_path)["ticker"].tolist()

        # Background Scheduler
        self.scheduler = BackgroundScheduler(timezone="America/New_York")

        self.scheduler.add_job(
            self.dossier_updater,
            trigger=CronTrigger(day_of_week="fri", hour="16", minute="30", timezone="America/New_York"),
                id="dossier_updater_job",
                replace_existing=True
        )
        
        self.scheduler.start()

    def load_dossiers(self):
        if not Path(self.dossier_path).exists():
            return {}
        try:
            with open(self.dossier_path, 'r', encoding="utf-8") as file:
                return json.load(file)
        except json.JSONDecodeError as e:
            logger.error(f"Error reading Dossiers JSON: {e}")
            return {}

    def load_company_profiles(self):
        if not Path(self.company_profile_path ).exists():
            return {}
        try:
            with open(self.company_profile_path , "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error reading Company Profiles JSON: {e}")
            return {}

    def _weekly_news(self):
        logger.info("Fetching unseen news to the AI...")
        nyc_tz = pytz.timezone('America/New_York')
        nyc_cutoff = (datetime.now(nyc_tz) - timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')

        # Cargas de DBs (Mismo código que tenías)
        with sql.connect(self.yahoo_db_path) as conn:
            yahoo_df = pd.read_sql("SELECT id, title, summary, ticker, pubDate AS date FROM news WHERE pubDate >= ?", conn, params=(nyc_cutoff,))

        with sql.connect(self.bloomberg_db_path) as conn:
            bb_df = pd.read_sql("SELECT link AS id, title, summary, ticker, published AS date FROM news WHERE pubDate >= ? AND ticker IS NOT NULL", conn, params=(nyc_cutoff,))
            
        with sql.connect(self.edgar_db_path) as conn:
            edgar_df = pd.read_sql("SELECT accession_number AS id, form AS title, primaryDocument AS summary, ticker, filing_date AS date FROM edgar_filings WHERE filing_date >= ?", conn, params=(nyc_cutoff,))
            
        with sql.connect(self.forbes_db_path) as conn:
            forbes_df = pd.read_sql("SELECT id, title, summary, ticker, pubDate AS date FROM forbes_news WHERE pubDate >= ?", conn, params=(nyc_cutoff,))
                
        combined_news = pd.concat([yahoo_df, bb_df, edgar_df, forbes_df], ignore_index=True)

        if combined_news.empty:
            return pd.DataFrame()
        return combined_news

    def _ai_updater(self, ticker: str, week_news: str, previous_dossier: str) -> str:
        url = "http://localhost:11434/api/generate"
        
        prompt = f"""
        You are a Strategic Investment Analyst. You are updating the 'Living Dossier' for {ticker}.
        
        ### CURRENT DOSSIER CONTEXT:
        {previous_dossier}

        ### NEW INTELLIGENCE FROM THE PAST WEEK:
        {week_news}

        ### TASK:
        Synthesize the new intelligence into the existing dossier. 
        - If the news confirms the current narrative, strengthen the language.
        - If the news contradicts the previous dossier, prioritize the NEW information.
        - Keep the output concise but high-density.
        
        ### OUTPUT:
        Return ONLY the updated dossier text. Start with the Sector and Narrative, followed by 'Key Recent Developments' from this week's news.
        """

        payload = {
            "model": "deepseek-r1:8b", 
            "prompt": prompt,
            "stream": False
        }

        try:
            response = requests.post(url, json=payload)
            response.raise_for_status()
            result_text = response.json().get('response', '')

            if "</think>" in result_text:
                result_text = result_text.split("</think>")[-1].strip()
            return result_text
        
        except Exception as e:
            logger.error(f"Error calling AI: {e}")
            return None

    def dossier_updater(self):
        news = self._weekly_news()
        
        if news.empty:
            logger.warning("No new news generated this week.")
            return

        dossiers_copy = self.dossiers.copy()

        for tkr in self.companies:

            last_week_dossier = self.dossiers.get(tkr, "No previous dossier exists. Create a new narrative based on the new intelligence.")

            tkr_news = news[news['ticker'] == tkr]

            if tkr_news.empty:
                logger.warning(f"No new news for {tkr}, skipping update.")
                continue

            formatted_news = "\n".join([f"- {row['title']}: {row['summary']}" for _, row in tkr_news.iterrows()])

            logger.info(f"Updating {tkr} with {len(tkr_news)} news items...")
            
            new_dossier_text = self._ai_updater(tkr, formatted_news, last_week_dossier)

            if new_dossier_text:
                dossiers_copy[tkr] = new_dossier_text
                logger.info(f"✅ {tkr} Dossier successfully updated.")
            else:
                logger.info(f"⚠️ Could not update {tkr} (AI error).")

        # Guardamos el resultado final
        with open(self.dossier_path, 'w', encoding="utf-8") as file:
            json.dump(dossiers_copy, file, indent=4)
            
        self.dossiers = dossiers_copy

    def _normalize_ticker(self, ticker: str) -> str:
        return str(ticker or "").strip().upper()

    def get(self, ticker: str) -> str:
        ticker = self._normalize_ticker(ticker)
        return self.dossiers.get(ticker, f"No dossier associated with {ticker}")

    def get_profile(self, ticker: str) -> dict:
        ticker = self._normalize_ticker(ticker)

        return self.companies_profiles.get(ticker, {
            "ticker": ticker,
            "name": ticker,
            "sector": "Unknown",
            "industry": "Unknown",
            "market_cap_label": "N/A",
            "revenue_trend": "N/A",
            "risk_level": "N/A",
            "outlook": "N/A",
            "summary": "",
            "logo_ticker": ticker,
        })
