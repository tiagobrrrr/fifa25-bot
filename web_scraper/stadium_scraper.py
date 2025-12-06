# web_scraper/stadium_scraper.py
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup
import time
import re
import hashlib

URL = "https://football.esportsbattle.com/en"

def slugify(name: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "_", name).strip().replace(" ", "_")

def make_match_id(d: dict) -> str:
    key = f"{d.get('stadium','')}_{d.get('team1','')}_{d.get('team2','')}_{d.get('match_time','')}_{d.get('score','')}"
    return hashlib.sha1(key.encode('utf-8')).hexdigest()

class StadiumScraper:
    def __init__(self, wait_seconds: int = 6):
        self.wait_seconds = wait_seconds

    def _get_driver(self):
        opts = Options()
        opts.add_argument("--headless=new")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--window-size=1920,1080")
        return webdriver.Chrome(ChromeDriverManager().install(), options=opts)

    def fetch_page(self):
        driver = self._get_driver()
        try:
            driver.get(URL)
            time.sleep(self.wait_seconds)
            return driver.page_source
        finally:
            driver.quit()

    def parse(self, html: str):
        soup = BeautifulSoup(html, "html.parser")

        # Mapa de estádios
        locations = {}
        loc_section = soup.find("section", class_=lambda v: v and "locations" in v)
        if loc_section:
            for it in loc_section.find_all(attrs={"data-id": True}):
                lid = it.get("data-id")
                name_el = it.find(class_=lambda v: v and "locations-name" in v)
                name = name_el.get_text(strip=True) if name_el else it.get_text(strip=True)
                if lid and name:
                    locations[lid] = name

        # Coleta dos cards de partidas
        cards = soup.find_all(class_=lambda v: v and ("online-matches-match" in v or "match-card" in v or "match" in v))
        results = []

        for card in cards:
            try:
                league = card.find(class_=lambda v: v and "subcaption-2" in v)
                league = league.get_text(strip=True) if league else "-"

                match_time = card.find(class_=lambda v: v and "subcaption-1" in v)
                match_time = match_time.get_text(strip=True) if match_time else "-"

                # Estádio
                stadium = None
                for attr in ("data-location", "data-location-id", "data-id", "data-loc"):
                    if card.get(attr):
                        stadium = locations.get(card.get(attr), card.get(attr))
                        break
                if not stadium:
                    loc_el = card.find(class_=lambda v: v and ("location" in v or "stadium" in v))
                    stadium = loc_el.get_text(strip=True) if loc_el else "Unknown"

                # Times / Players
                team1 = team2 = player1 = player2 = score = "-"

                stats = card.find_all(class_=lambda v: v and "online-matches-stats-item" in v)
                if stats and len(stats) >= 2:
                    left, right = stats

                    # Players
                    p1 = left.find("a")
                    p2 = right.find("a")
                    player1 = p1.get_text(strip=True) if p1 else "-"
                    player2 = p2.get_text(strip=True) if p2 else "-"

                    # Teams
                    t1 = left.find(class_=lambda v: v and ("team" in v or "club" in v))
                    t2 = right.find(class_=lambda v: v and ("team" in v or "club" in v))
                    team1 = t1.get_text(strip=True) if t1 else "-"
                    team2 = t2.get_text(strip=True) if t2 else "-"

                    # Score
                    score_el = card.find(class_=lambda v: v and ("score" in v or "stats-item-score" in v))
                    score = score_el.get_text(strip=True) if score_el else "-"

                status = "Live" if "LIVE" in card.get_text() else "Scheduled"

                match = {
                    "match_id": None,
                    "stadium": stadium,
                    "league": league,
                    "match_time": match_time,
                    "team1": team1,
                    "player1": player1,
                    "team2": team2,
                    "player2": player2,
                    "score": score,
                    "status": status
                }
                match["match_id"] = make_match_id(match)
                results.append(match)

            except:
                continue

        return locations, results

    def collect(self):
        html = self.fetch_page()
        return self.parse(html)

