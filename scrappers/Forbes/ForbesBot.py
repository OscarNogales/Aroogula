from playwright.sync_api import sync_playwright
import time
import feedparser
import urllib.parse
import random
from datetime import datetime
import json
import requests
import pandas as pd
import sqlite3 as sql
from tqdm import tqdm
import subprocess
import platform
import os
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

# Making this thing an obbject

class ForbesBot():
    def __init__(self, db_path: str, groq_api_key: str, companies_csv: str):
        self.db_path = db_path
        self.groq_api_key = groq_api_key
        self.companies_csv_path = companies_csv

        # Everytime 
        self._initialize_database()
    
    def _initialize_database(self):
        if not os.path.exists(self.db_path):
            with sql.connect(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS forbes_news (
                        id TEXT PRIMARY KEY,
                        title TEXT,
                        url TEXT,
                        summary TEXT,
                        pubDate TEXT,
                        ticker TEXT,
                        accessedDate TEXT
                    )
                """)

                cur.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS pubDate_idx
                ON forbes_news(pubDate)
""")
                conn.commit()
        else:
            pass

    def _load_companies(self) -> list[str]:
        companies = pd.read_csv(self.companies_csv_path)
        return companies['ticker'].tolist()
    
    def _launch_hijackable_chrome(self):
        try:
            response = requests.get(
                "http://localhost:9222/json/version",
                timeout=2
            )

            if response.ok:
                print("🌐 Chrome already running. Reusing existing browser.")
                return

        except requests.RequestException:
            pass
        bot_profile_path = os.path.join(os.getcwd(), "BotChromeProfile")
        os.makedirs(bot_profile_path, exist_ok=True)

        system = platform.system()
        if system == "Windows":
            chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        elif system == "Darwin":
            chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        else:
            chrome_path = "google-chrome"

        subprocess.Popen([
            chrome_path, 
            "--remote-debugging-port=9222", 
            f"--user-data-dir={bot_profile_path}"
        ])
        time.sleep(3)

    def _get_real_forbes_news(self, ticker: str, context):
        query = urllib.parse.quote(f"{ticker} site:forbes.com when:30d")
        url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
        
        feed = feedparser.parse(url)
        valid_entries = [e for e in feed.entries if hasattr(e, 'published_parsed') and e.published_parsed]
        
        if not valid_entries:
            tqdm.write(f"🤷‍♂️ [SKIP] No Forbes articles found for {ticker} in the last 30 days.")
            return None

        valid_entries.sort(key=lambda x: x.published_parsed, reverse=True)
        latest_entry = valid_entries[0]
        
        page = context.new_page()
        try:
            page.goto(latest_entry.link, timeout=25000)
            
            try:
                page.wait_for_url("**forbes.com**", timeout=15000)
            except Exception:
                pass
                
            real_url = page.url
            
        except Exception as e:
            tqdm.write(f"🐌 [TIMEOUT] Could not click link for {ticker}. Error: {e}")
            real_url = latest_entry.link
        finally:
            page.close()

        if "forbes.com" not in real_url:
            tqdm.write(f"🛑 [REJECT] Redirect failed. URL stuck at: {real_url[:50]}...")
            return None

        return {
            "id": latest_entry.id if hasattr(latest_entry, 'id') else real_url,
            "title": latest_entry.title,
            "url": real_url,
            "pubDate": time.strftime('%Y-%m-%d %H:%M:%S', latest_entry.published_parsed),
            "ticker": ticker
        }
    
    def _batch_scrape_forbes_articles(self, urls: list, context):
        summaries = {}
        for index, url in enumerate(urls):
            page = context.new_page()
            try:
                try:
                    page.goto(url, wait_until="commit", timeout=20000)
                except Exception:
                    pass
                
                page.wait_for_selector("p", timeout=10000)
                paragraphs = page.locator("p").all_inner_texts()
                article_text = " ".join([text.strip() for text in paragraphs if len(text.strip()) > 60])
                
                summaries[url] = article_text if article_text else None
                time.sleep(random.uniform(3.0, 8.0)) 
                
            except Exception:
                summaries[url] = None
            finally:
                page.close()
                
                if (index + 1) % 5 == 0 and (index + 1) < len(urls):
                    time.sleep(random.uniform(120.0, 300.0))
                elif (index + 1) < len(urls):
                    time.sleep(random.uniform(15.0, 40.0))
                    
        return summaries
    
    def _summarize_article(self, api_key: str, article_text: dict, ticker: str):
        url, raw_text = list(article_text.items())[0]

        prompt = f"""You are an elite financial analyst. Extract ONLY the information relevant to the stock: {ticker}.
        Format as 3 short bullet points:
        1. The main event or news.
        2. The market sentiment (Bullish, Bearish, Neutral).
        3. Specific numbers, earnings, or targets.
        
        Article: {raw_text}
        """

        try:
            response = requests.post(
                "https://api.groq.com/openai/v1/chat/completions", 
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}, 
                json={"model": "llama3-8b-8192", "messages": [{"role": "user", "content": prompt}], "temperature": 0.2}, 
                timeout=30
            )
            return response.json()["choices"][0]["message"]["content"].strip()
        except Exception:
            return raw_text[:500] + "..."
        
    def _send_dict_to_database(self, db_path: str, news_dict: dict):
        accessed_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            with sql.connect(db_path) as conn:
                cur = conn.cursor()
                cur.execute("""
                INSERT OR IGNORE INTO forbes_news
                (id, title, url, summary, pubDate, ticker, accessedDate)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    news_dict.get("id"), news_dict.get("title"), news_dict.get("url"),
                    news_dict.get("summary"), news_dict.get("pubDate"),
                    news_dict.get("ticker"), accessed_date
                ))
                
                if cur.rowcount > 0:
                    # This prints above the progress bar
                    tqdm.write(f"💾 [DB] Saved {news_dict.get('ticker')}: {news_dict.get('title')[:40]}...")
        except Exception as e:
            tqdm.write(f"⚠️ DB Error on {news_dict.get('ticker')}: {e}")

    def execute_news_pull(self):
        self._launch_hijackable_chrome()
        companies = self._load_companies()
        count = 0
        
        print(f"\n🚀 Starting Forbes Scraper at {datetime.now().strftime('%H:%M:%S')}")

        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp("http://localhost:9222")
            context = browser.contexts[0]

            for ticker in tqdm(companies, desc="Scraping News"):
                try:
                    news_dict = self._get_real_forbes_news(ticker, context)
                    # print(news_dict) ######
                    if news_dict:
                        url = news_dict.get("url")
                        article_dict = self._batch_scrape_forbes_articles([url], context)
                        # print(article_dict) ######
                        if list(article_dict.values())[0]:
                            summary = self._summarize_article(self.groq_api_key, article_dict, ticker)
                            news_dict["summary"] = summary
                            self._send_dict_to_database(self.db_path, news_dict) 
                            count += 1

                except Exception as e:
                    # This prints above the progress bar
                    tqdm.write(f"⚠️ Error processing {ticker}: {e}")

            browser.close()

        print(f"\n🏁 Finished scraping {count} new articles at {datetime.now().strftime('%H:%M:%S')}")


if __name__ == "__main__":
    from backend.config import paths
    from backend.config.environment import require_env

    forbes_bot = ForbesBot(
        db_path=paths.FORBES_DB_PATH,
        groq_api_key=require_env("GROQ_API_KEY"),
        companies_csv=paths.COMPANIES_CSV_PATH,
    )

    print("\n⏰ Booting up APScheduler...")
    scheduler = BlockingScheduler(timezone="America/New_York")
    scheduler.add_job(
        forbes_bot.execute_news_pull,
        trigger=CronTrigger(hour="*/2"),
        id="forbes_scraper",
    )
    scheduler.start()
