import requests
import feedparser
import pandas as pd
import spacy
import sqlite3
import os
import datetime
import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from tqdm import tqdm
from zoneinfo import ZoneInfo


class BloombergBot:
    def __init__(self, db_path: str, companies_csv: str, sites: list):
        self.db_path = db_path
        self.sites = sites
        
        print('Loading NLP model (spaCy)...')
        self.nlp = spacy.load("en_core_web_sm")
        
        self.companies = pd.read_csv(companies_csv)
        
        # Initialize Database
        self._initialize_news_table()

    def _initialize_news_table(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()

            cur.execute("""
                CREATE TABLE IF NOT EXISTS news (
                    title TEXT,
                    summary TEXT,
                    link TEXT,
                    published TEXT,
                    ticker TEXT,
                    dateAccesed TEXT
                );
            """)

            cur.execute("""
                DELETE FROM news
                WHERE rowid NOT IN (
                    SELECT MIN(rowid)
                    FROM news
                    GROUP BY link
                );
            """)

            cur.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_news_link 
                ON news(link);
            """)

            cur.execute("""
            CREATE INDEX IF NOT EXISTS pubDate_idx
                ON news(published)
            """)

            conn.commit()

    def _extract_single_ticker_from_tags(self, tags):
        if not isinstance(tags, list):
            return None

        symbols = []
        for t in tags:
            if isinstance(t, dict) and t.get("scheme") == "stock-symbol":
                term = t.get("term", "")
                if ":" in term:
                    symbols.append(term.split(":", 1)[1])

        return symbols[0] if len(symbols) == 1 else None

    def _extract_company_from_text(self, text: str):
        doc = self.nlp(text)
        
        # 1) ORGs detected in the text
        orgs_in_text = [
            ent.text.lower()
            for ent in doc.ents
            if ent.label_ == "ORG"
        ]

        if not orgs_in_text:
            return None

        # Normalize company names
        companies_norm = self.companies.copy()
        companies_norm["name_norm"] = (
            companies_norm["name"]
            .str.lower()
            .str.replace(r"[^\w\s]", "", regex=True)
        )

        # Try to match
        matches = []
        for org in orgs_in_text:
            org_norm = org.lower()
            mask = companies_norm["name_norm"].str.contains(org_norm, na=False)
            matches.extend(companies_norm.loc[mask, "ticker"].tolist())

        matches = list(set(matches))
        return matches[0] if len(matches) == 1 else None

    def _infer_ticker_if_missing(self, row):
        if pd.notna(row["ticker"]):
            return row["ticker"]

        text = f"{row['title']}. {row['summary']}"
        inferred = self._extract_company_from_text(text)
        return inferred

    def _news_to_table(self, bloomberg_url: str) -> pd.DataFrame:
        response = requests.get(bloomberg_url, timeout=20)
        response.raise_for_status()

        content = feedparser.parse(response.content)
        table = pd.DataFrame(content.entries)

        tags_series = table.get("tags", pd.Series([None] * len(table)))

        wanted_entries = ["title", "summary", "link", "published"]
        table_masked = table[wanted_entries].copy()
 
        table_masked["ticker"] = tags_series.apply(self._extract_single_ticker_from_tags)

        nyc_tz = pytz.timezone('America/New_York')
        table_masked["dateAccesed"] = datetime.datetime.now(tz=nyc_tz).strftime('%Y-%m-%d %H:%M:%S')

        table_masked["ticker"] = table_masked.apply(
            lambda row: self._infer_ticker_if_missing(row),
            axis=1
        )

        return table_masked

    def _table_to_sql(self, table: pd.DataFrame):
        if table.empty:
            return

        # Drop duplicates before inserting
        table = table.drop_duplicates(subset=["link"])

        rows = list(
            table[["title", "summary", "link", "published", "ticker", "dateAccesed"]]
            .itertuples(index=False, name=None)
        )

        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()

            try:
                cur.execute("ALTER TABLE news ADD COLUMN dateAccesed TEXT;")
            except sqlite3.OperationalError:
                # This means the column already exists, so we just carry on!
                pass

            cur.executemany("""
                INSERT OR IGNORE INTO news
                (title, summary, link, published, ticker, dateAccesed)
                VALUES (?, ?, ?, ?, ?, ?);
            """, rows)
            conn.commit()

    def run_start_time(self):
        mexico_tz = ZoneInfo("America/Mexico_City")
        nyc_tz = ZoneInfo("America/New_York")
        now_mex = datetime.datetime.now(mexico_tz)
        now_nyc = datetime.datetime.now(nyc_tz)
        print(f"\nStarting the news pull at {now_mex} MEXICO / {now_nyc} NEW YORK CITY")

    def run_end_time(self):
        mexico_tz = ZoneInfo("America/Mexico_City")
        nyc_tz = ZoneInfo("America/New_York")
        later_mex = datetime.datetime.now(mexico_tz)
        later_nyc = datetime.datetime.now(nyc_tz)
        print(f"\nEnding news pull at {later_mex} MEXICO / {later_nyc} NEW YORK CITY")

    def execute_news_pull(self):
        failed = []
        self.run_start_time()
        
        all_news_tables = []
        
        with tqdm(self.sites, desc="Looking at rss websites...", unit="url") as pbar:
            for url in pbar:
                pbar.set_postfix(feed=url)

                try:
                    table = self._news_to_table(url)
                    all_news_tables.append(table)
                    pbar.set_postfix(feed=url, rows=len(table))
                except Exception as e:
                    failed.append((url, str(e)))
                    pbar.set_postfix(feed=url, error="yes")

        # Concat and save to SQL
        if all_news_tables:
            combined_table = pd.concat(all_news_tables, ignore_index=True)
            self._table_to_sql(combined_table)

        if failed:
            print("\nDone, but some feeds failed:")
            for url, err in failed:
                print(f" - {url}: {err}")
        else:
            print("\nSuccessfully pulled news from all listed websites.")

        self.run_end_time()


if __name__ == "__main__":
    from backend.config import paths

    bloomberg_sites = [   
        'https://feeds.bloomberg.com/markets/news.rss',
        'https://feeds.bloomberg.com/politics/news.rss', 
        'https://feeds.bloomberg.com/technology/news.rss', 
        'https://feeds.bloomberg.com/wealth/news.rss'
    ]

    # 2. Instantiate the Bot
    my_bloomberg_bot = BloombergBot(
        db_path=paths.BLOOMBERG_DB_PATH, 
        companies_csv=paths.COMPANIES_CSV_PATH, 
        sites=bloomberg_sites
    )

    # 3. Manual Test Run
    print("Executing manual test run...")
    my_bloomberg_bot.execute_news_pull()

    # 4. Schedule the bot
    scheduler = BackgroundScheduler(timezone="America/New_York")

    scheduler.add_job(
        my_bloomberg_bot.execute_news_pull,
        trigger=CronTrigger(day_of_week="mon-fri", hour="9-16", minute="1-59/30", timezone="America/New_York"),
        id="bloomberg_news_pull",
        replace_existing=True
    )

    print("Bloomberg News bot started. Standing by...")
    scheduler.start()