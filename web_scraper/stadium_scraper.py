# web_scraper/stadium_scraper.py
import logging
import requests
import re
import hashlib
from bs4 import BeautifulSoup
from typing import List, Dict, Tuple, Optional

log = logging.getLogger("stadium_scraper")

DEFAULT_URL = "https://football.esportsbattle.com/en"


def make_match_id(data: dict) -> str:
    base = f"{data.get('stadium','')}_{data.get('player1','')}_{data.get('player2','')}_{data.get('match_time','')}"
    return hashlib.sha1(base.encode("utf-8")).hexdigest()


class StadiumScraper:
    """
    Scraper robusto para football.esportsbattle.com
    - Compatível com Render
    - Sem Selenium
    - Baseado em HTML real
    """

    def __init__(self, url: str = DEFAULT_URL, timeout: int = 15):
        self.url = url
        self.timeout = timeout

    # -------------------------
    # FETCH
    # -------------------------
    def fetch_page(self) -> Optional[str]:
        try:
            log.info("[stadium_scraper] Fetch via requests")
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120 Safari/537.36"
                )
            }
            r = requests.get(self.url, headers=headers, timeout=self.timeout)
            r.raise_for_status()
            return r.text
        except Exception as e:
            log.error("[stadium_scraper] Erro ao buscar página: %s", e)
            return None

    # -------------------------
    # PARSER
    # -------------------------
    def parse(self, html: Optional[str]) -> Tuple[Dict[str, str], List[dict]]:
        if not html:
            return {}, []

        soup = BeautifulSoup(html, "html.parser")
        matches: List[dict] = []

        # Cards principais (baseado nos HTMLs enviados)
        cards = soup.select("div[class*='event'], div[class*='match'], div[class*='online']")
        log.info("[stadium_scraper] Cards encontrados: %d", len(cards))

        for card in cards:
            text = card.get_text(" ", strip=True)
            if not text or len(text) < 20:
                continue

            try:
                # STATUS
                status = "Live" if re.search(r"\blive\b", text, re.I) else "Scheduled"

                # SCORE
                score = "-"
                m_score = re.search(r"\b\d+\s*[:\-]\s*\d+\b", text)
                if m_score:
                    score = m_score.group(0)

                # PLAYERS
                players = re.findall(r"[A-Za-z0-9_]{3,}", text)
                player1 = players[0] if len(players) > 0 else "-"
                player2 = players[1] if len(players) > 1 else "-"

                # TIME
                match_time = "-"
                m_time = re.search(r"\b\d{1,2}:\d{2}\b", text)
                if m_time:
                    match_time = m_time.group(0)

                # LEAGUE
                league = "-"
                league_el = card.select_one(".league, .competition")
                if league_el:
                    league = league_el.get_text(strip=True)

                # STADIUM
                stadium = "-"
                stadium_el = card.select_one(".stadium, .location, .venue")
                if stadium_el:
                    stadium = stadium_el.get_text(strip=True)

                match = {
                    "match_id": make_match_id({
                        "stadium": stadium,
                        "player1": player1,
                        "player2": player2,
                        "match_time": match_time
                    }),
                    "stadium": stadium,
                    "league": league,
                    "match_time": match_time,
                    "team1": player1,
                    "player1": player1,
                    "team2": player2,
                    "player2": player2,
                    "score": score,
                    "status": status,
                }

                matches.append(match)

            except Exception as e:
                log.warning("[stadium_scraper] Card ignorado: %s", e)

        return {}, matches

    # -------------------------
    # PUBLIC
    # -------------------------
    def collect(self) -> Tuple[Dict[str, str], List[dict]]:
        html = self.fetch_page()
        return self.parse(html)
