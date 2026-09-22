import sqlite3
import yfinance as yf
import datetime
import pandas as pd
import os
from tqdm import tqdm
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger



class YahooNewsBot:
    def __init__(self, db_path: str, companies_csv: str):
        # 1. Initialize variables
        self.db_path = db_path
        self.news_saved_today = False
        
        # 2. Load Tickers
        companies = pd.read_csv(companies_csv)
        self.tickers = companies['ticker'].tolist()
        self.names = companies['name'].tolist()

        # 3. Initialize Database
        self._initialize_database()

    def _initialize_database(self):
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        try:
            with sqlite3.connect(database=self.db_path) as conn:
                cur = conn.cursor()
                
                # Catch error if 'news' table doesn't exist yet on the very first run
                try:
                    cur.execute(''' DELETE FROM news 
                                    WHERE rowid NOT IN ( 
                                    SELECT MIN(rowid) 
                                    FROM news 
                                    GROUP BY id ) ''')
                except sqlite3.OperationalError:
                    pass 
                
                cur.execute('''
                            CREATE UNIQUE INDEX IF NOT EXISTS idx_news_id ON news(id);
                            ''')
                
                cur.execute("""
                CREATE INDEX IF NOT EXISTS pubDate_idx 
                ON news(pubDate)
                """)
                conn.commit()
        except Exception as e:
            print(f'Database initialization error: {e}')


    def _ticker_yahoo(self, ticker: str):
        try:
            tkr_obj = yf.Ticker(ticker)
            data = tkr_obj.history(period="1d")

            if data.empty:
                return None

            return tkr_obj
        except Exception as e:
            print(f'ticker_yahoo error for {ticker}: {e}')
            return None


    def _parse_news(self, ticker: str):
        try:
            columns = ['id', 
                       'content.title', 
                       'content.summary', 
                       'content.pubDate', 
                       'content.displayTime', 
                       'content.clickThroughUrl.url'] 

            desired_column_names = ['id', 
                                    'title', 
                                    'summary', 
                                    'pubDate', 
                                    'displayTime', 
                                    'url']

            assert len(columns) == len(desired_column_names), "Column rename mismatch"

            # Use self._ticker_yahoo to call your other function
            tkr_obj = self._ticker_yahoo(ticker)
            if tkr_obj is None:
                return None
                
            news = tkr_obj.news

            if not news:
                raise ValueError(f'There are no news gathered for {ticker}')

            data_frame = pd.json_normalize(news)

            if not set(columns).issubset(data_frame.columns):
                raise ValueError(f'Input columns not inside data for {ticker}')

            data_frame_desired = data_frame[columns].copy()
            data_frame_desired.columns = desired_column_names
            data_frame_desired['dateAccessed'] = datetime.datetime.now()
            data_frame_desired['ticker'] = ticker # Added this so we know who the news belongs to!

            return data_frame_desired

        except Exception as e:
            # Commented out the print so the terminal doesn't get spammed if a ticker has no news
            # print(f'get_news error: {e}')
            return None


    def execute_news_pull(self):
        print("Starting the news pull...")
        all_dbs = []
        
        # Loop through tickers and parse
        with tqdm(self.tickers, desc="Pulling news", unit="ticker") as pbar:
            for tkr in pbar:
                pbar.set_postfix(ticker=tkr)
                
                df = self._parse_news(tkr)
                if df is not None and not df.empty:
                    all_dbs.append(df)
        
        # Concat the list and send to database!
        if all_dbs:
            combined_dbs = pd.concat(all_dbs, ignore_index=True)
            success = self._add_news_to_sql_database(combined_dbs)
            
            # If successfully added to database, wave the flag!
            if success:
                self.news_saved_today = True
        else:
            print("\nNo news pulled across all tickers today.")


    def _add_news_to_sql_database(self, df: pd.DataFrame):
        try:
            with sqlite3.connect(self.db_path) as conn:
                try:
                    db_ids = pd.read_sql("SELECT id FROM news", conn)["id"].astype(str)
                except Exception:
                    db_ids = pd.Series([], dtype="object")

                df2 = df.copy()
                df2["id"] = df2["id"].astype(str)
                
                df2 = df2.drop_duplicates(subset=["id"])
                df_not_in_database = df2[~df2["id"].isin(db_ids)]

                if df_not_in_database.empty:
                    print("\nNo new news to add.")
                    return True

                df_not_in_database.to_sql("news", con=conn, if_exists="append", index=False)

            print(f"\nSuccessfully added {len(df_not_in_database)} news to news table")
            return True

        except Exception as e:
            print("add_news_to_sql error:", e)
            return None




if __name__ == "__main__":
    from backend.config import paths

    scheduler = BlockingScheduler(timezone="America/New_York")

    YahooBot = YahooNewsBot(
        db_path=paths.YAHOO_DB_PATH,
        companies_csv=paths.COMPANIES_CSV_PATH,
    )

    # Test run
    # YahooBot.execute_news_pull()

    # Initialize database
    YahooBot._initialize_database()

    scheduler.add_job(
        YahooBot.execute_news_pull,
        trigger=CronTrigger(day_of_week="mon-fri", hour="9-16", minute="0,7,30", timezone="America/New_York"),
        id="news_pull",
        replace_existing=True
    )

    print("News bot started. Standing by...")

    scheduler.start()


