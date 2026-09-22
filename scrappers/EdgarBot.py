from edgar import set_identity, Company
from datetime import datetime, timezone
import pandas as pd
from typing import Any
from tqdm import tqdm
import sqlite3 as sql
import os
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from zoneinfo import ZoneInfo

class EdgarBot:
    def __init__(self, db_path: str, companies_csv: str, identity: str):
        self.db_path = db_path
        
        # Set EDGAR Identity (Required by SEC)
        self.identity = identity
        set_identity(self.identity)
        print(f"Set EDGAR identity to: {self.identity}")
        
        # Load Tickers
        companies = pd.read_csv(companies_csv)
        self.tickers = companies['ticker'].tolist()
        
        # Store weights dictionary inside the class
        self.item_weights = {
            # ─── Financials & operations ───
            "1.01": 0.80,  "1.02": 0.85,  "1.03": 0.90,
            "2.01": 0.70,  "2.02": 0.95,  "2.03": 0.65,
            "2.04": 0.75,  "2.05": 0.80,  "2.06": 0.85,
            "3.01": 0.80,  "3.02": 0.60,  "3.03": 0.70,
            "4.01": 0.75,  "4.02": 0.90,  "5.01": 0.85,
            "5.02": 0.80,  "5.03": 0.60,  "5.07": 0.70,
            "5.08": 0.65,  "6.01": 0.70,  "6.02": 0.70,
            "6.03": 0.65,  "8.01": 0.55,  "9.01": 0.40,
        }

        # Initialize Database
        self._initialize_filings_table()

    def _initialize_filings_table(self):
        with sql.connect(self.db_path) as conn:

            cur = conn.cursor()

            cur.execute("""
                CREATE TABLE IF NOT EXISTS edgar_news(
                        accession_number TEXT PRIMARY KEY,
                        form TEXT,
                        items TEXT,
                        score FLOAT,
                        primaryDocument TEXT,
                        ticker TEXT,
                        filingDate TEXT
                        )
            """)

            cur.execute("""
            CREATE INDEX IF NOT EXISTS filingDate_idx
                        ON edgar_news(filingDate)
""")

            conn.commit()

    def _request_forms_from_EDGAR(self, company_ticker: str) -> dict | list:
        try:
            company = Company(company_ticker)
            filings = company.get_filings()
            latest_filing = filings.latest()

            if latest_filing is None:
                return False

            return latest_filing.to_dict()
        except Exception as e:
            print(f"Error fetching {company_ticker}: {e}")
            return False

    def _filing_catalog_8k(self, latest_filing: dict, ticker: str) -> dict:
        
        if not latest_filing:
            return None

        if latest_filing.get("form") != "8-K":
            return None

        item = latest_filing.get("items")

        wanted_items = ["accession_number", "form", "items", "filing_date", "primaryDocument"]

        desired_dict = {k: v for k, v in latest_filing.items() if k in wanted_items}

        desired_dict["ticker"] = ticker
        desired_dict["score"] = self.item_weights.get(item, 0.5)

        return desired_dict





    def _add_filings_to_sql_database(self, df: pd.DataFrame):
        
        desired_order = [
            "accession_number",
            "form",
            "items",
            "score",
            "primaryDocument",
            "ticker",
            "filing_date"
        ]

        missing = [c for c in desired_order if c not in df.columns]

        if missing:
            print(f"Missing columns: {missing}")
            return

        df = df.drop_duplicates(subset=["accession_number"])

        rows = list(
            df[desired_order]
            .itertuples(index=False, name=None)
        )

        with sql.connect(self.db_path) as conn:

            cur = conn.cursor()

            cur.executemany("""
                INSERT OR IGNORE INTO edgar_news
                (accession_number, form, items, score, primaryDocument, ticker, filingDate)
                VALUES (?, ?, ?, ?, ?, ?, ?);
            """, rows)
            
            conn.commit()



    def execute_filings_pull(self):
        print("Starting EDGAR filings pull...")
        all_filings = []
        
        with tqdm(self.tickers, desc="Pulling filings", unit="ticker") as pbar:
            for tkr in pbar:
                pbar.set_postfix(ticker=tkr)
                
                # 1. Fetch raw data
                raw_data = self._request_forms_from_EDGAR(tkr)
                
                # 2. Parse and filter
                if raw_data:
                    parsed_data = self._filing_catalog_8k(raw_data, tkr)
                    
                    # 3. Append to our master list
                    if parsed_data: 
                        # Assuming parsed_data is a DataFrame or can be turned into one
                        all_filings.append(parsed_data)
        
        # 4. Concatenate and Save!
        if all_filings:
            combined_dbs = pd.DataFrame(all_filings)
            self._add_filings_to_sql_database(combined_dbs)
        else:
            print("\nNo new 8-K filings pulled today.")


if __name__ == "__main__":
    from backend.config import paths
    from backend.config.environment import require_env

    # SEC EDGAR asks clients to identify themselves with a name/contact email.
    my_edgar_bot = EdgarBot(
        db_path=paths.EDGAR_DB_PATH,
        companies_csv=paths.COMPANIES_CSV_PATH,
        identity=require_env("SEC_EDGAR_IDENTITY"),
    )

    # 3. Manual Test Run
    print("Executing manual test run...")
    my_edgar_bot.execute_filings_pull()

    # 4. Schedule the bot
    scheduler = BlockingScheduler(timezone="America/New_York")

    # Notice the minutes! You had "0,15,30,45" in your old variables.
    scheduler.add_job(
        my_edgar_bot.execute_filings_pull, 
        trigger=CronTrigger(day_of_week="mon-fri", hour="9-16", minute="0,15,30,45", timezone="America/New_York"),
        id="edgar_pull",
        replace_existing=True
    )
    
    print("Starting EDGAR scheduler...")
    scheduler.start()