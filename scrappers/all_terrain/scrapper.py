import json
import logging
import platform
import random
import subprocess
import time
import urllib.parse
import urllib.request
from difflib import SequenceMatcher
from pathlib import Path

from bs4 import BeautifulSoup
from bs4.element import Tag
from playwright.sync_api import sync_playwright
from tqdm.auto import tqdm

from utils.database import SQLiteTableStore


logger = logging.getLogger(__name__)


class scrapper(SQLiteTableStore):
    """
    Bot that allows you to scrape news from different websites.

    The class handles fetching HTML. Static helper methods handle parsing and
    extraction because they do not depend on the state of a scraper instance.
    """

    bot_name: str = ""

    bot_url: dict = {
        "normal_site": None,  # reuters.com / forbes.com / yahoo.com
        "query_site": None,   # https://www.reuters.com/site-search/?query=msft
        "rss_site": None,     # RSS/Atom feed URL
    }

    table_name: str = "news"

    columns = (
        "timestamp",
        "id",
        "title",
        "summary",
        "url",
    )

    schema_sql = f"""
    CREATE TABLE IF NOT EXISTS {table_name} (
        id TEXT PRIMARY KEY,
        ticker TEXT,
        title TEXT,
        summary TEXT,
        url TEXT,
        timestamp DATE
    )
    """

    indexes_sql = (
        "CREATE UNIQUE INDEX IF NOT EXISTS timestamp_idx ON news (timestamp)",
        "CREATE UNIQUE INDEX IF NOT EXISTS ticker_idx ON news (ticker)",
    )

    def __init__(self, db_path: str = ""):
        if db_path == "":
            self.db_path = Path.cwd() / "Reuters.db"
        else:
            self.db_path = db_path

        super().__init__(self.db_path)
        self._launch_hijackable_chrome()

    def _launch_hijackable_chrome(self):
        """Launch the shared Chrome instance only if port 9222 is not active."""
        try:
            with urllib.request.urlopen(
                "http://localhost:9222/json/version",
                timeout=2,
            ) as response:
                if response.status == 200:
                    logger.info(
                        "An instance of Chrome is already active; skipping launch."
                    )
                    return
        except Exception:
            pass

        bot_profile_path = Path.cwd() / "BotChromeProfile"
        bot_profile_path.mkdir(parents=True, exist_ok=True)

        system = platform.system()
        if system == "Windows":
            chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        elif system == "Darwin":
            chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        else:
            chrome_path = "google-chrome"

        subprocess.Popen(
            [
                chrome_path,
                "--remote-debugging-port=9222",
                f"--user-data-dir={bot_profile_path}",
            ]
        )

        logger.info(
            "Hijackable Chrome ready for news scraping for %s",
            self.bot_name,
        )
        time.sleep(3)

    def _direct_request(self, urls: list[str]) -> dict[str, str | None]:
        """Fetch raw HTML directly with urllib."""
        htmls: dict[str, str | None] = {}

        for _, url in tqdm(enumerate(urls), total=len(urls)):
            try:
                with urllib.request.urlopen(url) as response:
                    htmls[url] = response.read().decode("utf-8")
            except Exception as exc:
                htmls[url] = None
                logger.error(
                    "Direct request failed for %s: %s",
                    url,
                    exc,
                )

        return htmls

    def _chrome_request(self, urls: list[str]) -> dict[str, str | None]:
        """Fetch rendered HTML through the shared Playwright/Chrome instance."""
        htmls: dict[str, str | None] = {}

        with sync_playwright() as playwright:
            browser = playwright.chromium.connect_over_cdp(
                        "http://localhost:9222",
                        timeout=10000
                    )
            context = browser.contexts[0]

            for i, url in tqdm(enumerate(urls), total=len(urls)):
                page = context.new_page()

                try:
                    try:
                        page.goto(
                            url,
                            wait_until="commit",
                            timeout=15000
                        )
                    except Exception as exc:
                        # A timeout can still leave a useful rendered DOM behind.
                        logger.warning("Chrome navigation issue for %s: %s", url, exc)

                    page.wait_for_timeout(3000)

                    htmls[url] = page.content()
                    time.sleep(random.uniform(3.0, 8.0))

                except Exception as exc:
                    htmls[url] = None
                    logger.error("Chrome request failed for %s: %s", url, exc)

                finally:
                    page.close()

                has_more_urls = (i + 1) < len(urls)
                if has_more_urls and (i + 1) % 5 == 0:
                    time.sleep(random.uniform(120.0, 300.0))
                elif has_more_urls:
                    time.sleep(random.uniform(15.0, 40.0))

        return htmls

    @staticmethod
    def chrome_search_request(query: str) -> str:
        """Build a Google News RSS search URL."""
        encoded_query = urllib.parse.quote(query)
        return (
            "https://news.google.com/rss/search"
            f"?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"
        )

    @staticmethod
    def _normalize_title(title: str) -> str:
        """Normalize a title only for similarity comparisons."""
        return " ".join(title.lower().strip().split())

    @staticmethod
    def _walk_json_ld(data):
        """Yield dictionaries recursively from JSON-LD dict/list/@graph structures."""
        if isinstance(data, dict):
            yield data
            for value in data.values():
                if isinstance(value, (dict, list)):
                    yield from scrapper._walk_json_ld(value)

        elif isinstance(data, list):
            for item in data:
                yield from scrapper._walk_json_ld(item)

    @staticmethod
    def _find_title(soup: BeautifulSoup) -> str | None:
        """Find the title with the strongest agreement across page metadata."""
        candidates: list[str] = []

        title_tag = soup.title
        if title_tag:
            title = title_tag.get_text(strip=True)
            if title:
                candidates.append(title)

        h1_tag = soup.find("h1")
        if h1_tag:
            h1 = h1_tag.get_text(" ", strip=True)
            if h1:
                candidates.append(h1)

        og_title_tag = soup.find("meta", property="og:title")
        if og_title_tag:
            og_title = og_title_tag.get("content")
            if isinstance(og_title, str) and og_title.strip():
                candidates.append(og_title.strip())

        json_types = {"NewsArticle", "Article"}
        json_blocks = soup.find_all("script", type="application/ld+json")

        for json_tag in json_blocks:
            raw_json = json_tag.string or json_tag.get_text(strip=True)
            if not raw_json:
                continue

            try:
                data = json.loads(raw_json)
            except (json.JSONDecodeError, TypeError):
                continue

            for node in scrapper._walk_json_ld(data):
                node_type = node.get("@type")
                headline = node.get("headline")

                if (
                    isinstance(headline, str)
                    and headline.strip()
                    and (node_type in json_types or "headline" in node)
                ):
                    candidates.append(headline.strip())

        if not candidates:
            return None

        if len(candidates) == 1:
            return candidates[0]

        normalized_candidates = [
            scrapper._normalize_title(candidate)
            for candidate in candidates
        ]

        similarity_scores = {
            i: []
            for i in range(len(normalized_candidates))
        }

        for i, candidate in enumerate(normalized_candidates):
            for j in range(i + 1, len(normalized_candidates)):
                candidate_2 = normalized_candidates[j]

                similarity = SequenceMatcher(
                    a=candidate,
                    b=candidate_2,
                ).ratio()

                similarity_scores[i].append(similarity)
                similarity_scores[j].append(similarity)

        best_index = max(
            similarity_scores,
            key=lambda i: (
                sum(similarity_scores[i]) / len(similarity_scores[i])
                if similarity_scores[i]
                else 0.0
            ),
        )

        # Return the original title, not the lower-cased normalized version.
        return candidates[best_index]

    @staticmethod
    def _is_text_block(element: Tag) -> bool:
        """Heuristic: identify text-heavy leaf-like structural nodes."""
        text = element.get_text(" ", strip=True)
        total_words = len(text.split())

        if total_words < 10:
            return False

        children = element.find_all(
            ["div", "p", "article", "section"],
            recursive=False,
        )

        children_words = 0

        for child in children:
            child_text = child.get_text(" ", strip=True)
            children_words += len(child_text.split())

        child_ratio = children_words / total_words
        return child_ratio <= 0.30

    @staticmethod
    def _find_summary(soup: BeautifulSoup) -> dict:
        """Find the strongest article-body prospect using a DFS over the DOM."""
        root = soup.find("main") or soup.body

        if root is None:
            return {
                "text": [],
                "word_count": 0,
                "children": 0,
            }

        seen_elements: set[int] = set()
        prospects: dict[int, dict] = {}

        def inspect(element: Tag):
            element_id = id(element)

            if element_id in seen_elements:
                return

            seen_elements.add(element_id)

            if scrapper._is_text_block(element):
                parent = element.parent
                if not isinstance(parent, Tag):
                    return

                parent_id = id(parent)
                text = element.get_text(" ", strip=True)

                if parent_id not in prospects:
                    prospects[parent_id] = {
                        "text": [],
                        "word_count": 0,
                        "children": 0,
                    }

                prospects[parent_id]["text"].append(text)
                prospects[parent_id]["word_count"] += len(text.split())
                prospects[parent_id]["children"] += 1
                return

            children = element.find_all(
                ["div", "p", "article", "section"],
                recursive=False,
            )

            for child in children:
                inspect(child)

        elements = root.find_all(
            ["div", "p", "article", "section"],
            recursive=False,
        )

        for element in elements:
            inspect(element)

        if not prospects:
            return {
                "text": [],
                "word_count": 0,
                "children": 0,
            }

        best_prospect = max(
            prospects.values(),
            key=lambda prospect: prospect["word_count"],
        )

        return best_prospect

    @staticmethod
    def extract_html(html: str) -> dict:
        """Extract the best title and article-body candidate from raw HTML."""
        soup = BeautifulSoup(html, "html.parser")

        title = scrapper._find_title(soup)
        article_prospect = scrapper._find_summary(soup)
        article = " ".join(article_prospect["text"])

        return {
            "title": title,
            "article": article,
        }

def test_news_extraction(url: str):
        print("\n" + "=" * 70)
        print("ALL-TERRAIN SCRAPER TEST")
        print("=" * 70)

        reuters = scrapper(
            # bot_url={
            #    "normal_site": "reuters.com",
            #    "query_site": "https://www.reuters.com/site-search/?query=msft",
            #    "rss_site": "https://ir.thomsonreuters.com/rss/news-releases.xml?items=15",
            # },
            # bot_name="reuters",
            db_path=Path.cwd() / "database_test" / "reuters_test.db",
        )

        test_site = (
            url
        )

        print(f"\nTest URL:")
        print(f"   {test_site}")

        # ------------------------------------------------------------------
        # DIRECT REQUEST
        # ------------------------------------------------------------------

        print("\n" + "-" * 70)
        print("📡 TEST 1 — DIRECT REQUEST")
        print("-" * 70)

        dr_result = reuters._direct_request([test_site])
        dr_html = None

        if dr_result and dr_result.get(test_site):
            dr_html = reuters.extract_html(dr_result[test_site])

            print("✅ Direct request succeeded")
            print(f"📰 Title:   {dr_html.get('title')}")
            print(f"📝 Article: {len(dr_html.get('article', '').split())} words")

        else:
            print("❌ Direct request failed")

        # ------------------------------------------------------------------
        # CHROME REQUEST
        # ------------------------------------------------------------------

        print("\n" + "-" * 70)
        print("🧟 TEST 2 — CHROME REQUEST")
        print("-" * 70)

        cr_result = reuters._chrome_request([test_site])
        cr_html = None

        if cr_result and cr_result.get(test_site):
            cr_html = reuters.extract_html(cr_result[test_site])

            print("✅ Chrome request succeeded")
            print(f"📰 Title:   {cr_html.get('title')}")
            print(f"📝 Article: {len(cr_html.get('article', '').split())} words")
            print(f"📝 Complete Article: {cr_html.get('article', '')}")

        else:
            print("❌ Chrome request failed")

        # ------------------------------------------------------------------
        # COMPARISON
        # ------------------------------------------------------------------

        print("\n" + "-" * 70)
        print("🔬 EXTRACTION COMPARISON")
        print("-" * 70)

        if dr_html and cr_html:
            print(f"Direct title : {dr_html.get('title')}")
            print(f"Chrome title : {cr_html.get('title')}")

            direct_words = len(dr_html.get("article", "").split())
            chrome_words = len(cr_html.get("article", "").split())

            print(f"\nDirect article words : {direct_words}")
            print(f"Chrome article words : {chrome_words}")

            if dr_html.get("title") == cr_html.get("title"):
                print("\n✅ Titles match")
            else:
                print("\n⚠️ Titles differ")

        print("\n" + "=" * 70)
        print("🏁 TEST COMPLETE")
        print("=" * 70 + "\n")


if __name__ == "__main__":

    test_urls = [
        "https://finance.yahoo.com/economy/policy/article/the-treasury-department-just-pushed-down-long-term-us-bond-yields-that-could-make-kevin-warshs-job-harder-174238269.html",
        "https://www.reuters.com/legal/litigation/moderna-merck-breakthrough-could-usher-wave-cancer-vaccines-2026-08-19/",
        "https://www.forbes.com/sites/jeffkauflin/2026/08/19/inside-paypal-mafia-billionaire-max-levchins-slow-and-steady-path-to-fintech-profitability/",
        "https://www.bloomberg.com/news/articles/2026-08-19/bessent-becomes-most-interventionist-treasury-chief-in-decades?srnd=homepage-americas"
    ]

    for test_url in test_urls:
        test_news_extraction(test_url)