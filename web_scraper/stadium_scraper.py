# web_scraper/stadium_scraper.py
import time
import logging
import requests
from bs4 import BeautifulSoup
import re
import hashlib
from typing import Tuple, List, Dict, Optional

# selenium imports (used only if available / possible)
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from webdriver_manager.chrome import ChromeDriverManager
    SELENIUM_AVAILABLE = True
except Exception:
    SELENIUM_AVAILABLE = False
    # don't fail import — we'll fallback to requests

log = logging.getLogger("stadium_scraper")
DEFAULT_URL = "https://football.esportsbattle.com/en"

def slugify(name: str) -> str:
    if not name:
        return "unknown"
    s = re.sub(r'[\\/*?:"<>|]', "_", name)
    s = re.sub(r"\s+", "_", s)
    return s.strip()[:100]

def make_match_id(d: dict) -> str:
    key = f"{d.get('stadium','')}_{d.get('team1','')}_{d.get('team2','')}_{d.get('match_time','')}_{d.get('score','')}"
    return hashlib.sha1(key.encode("utf-8")).hexdigest()

class StadiumScraper:
    """
    Robust stadium scraper:
    - Prefer Selenium (if available and Chrome binary exists).
    - If Selenium not available or Chrome missing, fallback to requests + BS4.
    - parse() returns (locations_map, matches_list).
    """

    def __init__(self, url: str = DEFAULT_URL, wait_seconds: int = 6, force_requests: bool = False):
        self.url = url
        self.wait_seconds = max(1, int(wait_seconds or 1))
        self.force_requests = bool(force_requests)

    # -------------------------
    # Selenium driver builder
    # -------------------------
    def _create_selenium_driver(self):
        if not SELENIUM_AVAILABLE:
            raise RuntimeError("Selenium/webdriver-manager not available in environment.")

        opts = Options()
        # modern headless arg: use plain --headless to be compatible
        opts.add_argument("--headless")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--window-size=1920,1080")
        opts.add_argument("--log-level=3")
        # avoid automation banners
        opts.add_experimental_option("excludeSwitches", ["enable-automation"])
        opts.add_experimental_option("useAutomationExtension", False)

        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=opts)
        return driver

    # -------------------------
    # Fetch page (selenium preferred, fallback to requests)
    # -------------------------
    def fetch_page(self) -> Optional[str]:
        # If forced to requests, skip selenium entirely
        if not self.force_requests and SELENIUM_AVAILABLE:
            try:
                log.info("[stadium_scraper] Trying Selenium to fetch page.")
                driver = self._create_selenium_driver()
                try:
                    driver.get(self.url)
                    time.sleep(self.wait_seconds)
                    html = driver.page_source
                    log.info("[stadium_scraper] Selenium fetch successful.")
                    return html
                finally:
                    try:
                        driver.quit()
                    except Exception:
                        pass
            except Exception as e:
                log.warning("[stadium_scraper] Selenium fetch failed, falling back to requests: %s", e)

        # fallback: requests
        try:
            log.info("[stadium_scraper] Using requests fallback to fetch page.")
            headers = {
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114 Safari/537.36"
            }
            r = requests.get(self.url, headers=headers, timeout=12)
            r.raise_for_status()
            return r.text
        except Exception as e:
            log.error("[stadium_scraper] requests fetch failed: %s", e)
            return None

    # -------------------------
    # Parser — adapt to site structure but resilient
    # returns (locations_map, matches_list)
    # -------------------------
    def parse(self, html: Optional[str]) -> Tuple[Dict[str, str], List[dict]]:
        if not html:
            return {}, []

        soup = BeautifulSoup(html, "html.parser")
        locations = {}
        matches = []

        # Try to extract stadium/location mappings if present
        # Different versions of the site may store locations in a section; try common locations
        try:
            loc_nodes = soup.select("[data-location-id], [data-id].location, .locations-list, .locations")
            for n in loc_nodes:
                lid = n.get("data-location-id") or n.get("data-id") or n.get("id")
                if not lid:
                    continue
                name = n.get_text(strip=True)
                if name:
                    locations[str(lid)] = name
        except Exception:
            pass

        # Find match cards - try multiple plausible selectors to be robust
        card_selectors = [
            ".match-card", ".event-card", ".online-match", ".match-item", ".card.match"
        ]

        cards = []
        for sel in card_selectors:
            found = soup.select(sel)
            if found:
                cards = found
                break

        # If none found, fallback to any div that looks like a match container
        if not cards:
            cards = soup.find_all("div", class_=lambda v: v and ("match" in v or "event" in v))

        for card in cards:
            try:
                # stadium
                stadium = "-"
                # check data attributes first
                for attr in ("data-location", "data-location-id", "data-id", "data-loc"):
                    if card.get(attr):
                        stadium = locations.get(card.get(attr)) or card.get(attr)
                        break

                if stadium == "-" or not stadium:
                    # try common child selectors
                    el = card.select_one(".stadium, .location, .match-location, .event-card__location, .event-card__venue")
                    if el:
                        stadium = el.get_text(strip=True)

                # league / time
                league_el = card.select_one(".league, .competition, .event-card__league, .subcaption-2")
                league = league_el.get_text(strip=True) if league_el else "-"

                time_el = card.select_one(".time, .event-card__time, .subcaption-1, .match-time")
                match_time = time_el.get_text(strip=True) if time_el else "-"

                # teams / players / score
                # Try structured stats block
                team1 = team2 = player1 = player2 = score = "-"
                # look for left/right blocks
                left = card.select_one(".team-1, .left, .stats-left, .online-matches-stats-item:nth-of-type(1)")
                right = card.select_one(".team-2, .right, .stats-right, .online-matches-stats-item:nth-of-type(2)")

                if left:
                    player1 = (left.select_one("a") or left.select_one(".player-name") or left).get_text(strip=True)
                    t1 = left.select_one(".club, .team-name, .team")
                    team1 = t1.get_text(strip=True) if t1 else player1

                if right:
                    player2 = (right.select_one("a") or right.select_one(".player-name") or right).get_text(strip=True)
                    t2 = right.select_one(".club, .team-name, .team")
                    team2 = t2.get_text(strip=True) if t2 else player2

                # score
                sc = card.select_one(".score, .match-score, .event-card__score")
                if sc:
                    score = sc.get_text(strip=True)

                # If still missing, try generic patterns
                text = card.get_text(" ", strip=True)
                status = "Live" if re.search(r"\blive\b", text, flags=re.I) else "Scheduled"

                match = {
                    "match_id": make_match_id({
                        "stadium": stadium,
                        "team1": team1,
                        "team2": team2,
                        "match_time": match_time,
                        "score": score
                    }),
                    "stadium": stadium or "Unknown",
                    "league": league,
                    "match_time": match_time,
                    "team1": team1,
                    "player1": player1,
                    "team2": team2,
                    "player2": player2,
                    "score": score,
                    "status": status
                }
                matches.append(match)
            except Exception:
                # be resilient: skip problematic card
                continue

        return locations, matches

    # -------------------------
    # Convenience: collect both
    # -------------------------
    def collect(self) -> Tuple[Dict[str, str], List[dict]]:
        html = self.fetch_page()
        return self.parse(html)
