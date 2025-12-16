import requests
from bs4 import BeautifulSoup
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

BASE_URL = "https://football.esportsbattle.com/en/live"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
}


class StadiumScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def run(self):
        """
        Método principal chamado pelo app.py
        """
        try:
            logger.info("[SCRAPER] Coleta iniciada")
            html = self._fetch_page()
            matches = self._parse_matches(html)
            logger.info(f"[SCRAPER] {len(matches)} partidas encontradas")
            return matches
        except Exception as e:
            logger.exception(f"[SCRAPER] Erro fatal: {e}")
            return []

    def _fetch_page(self):
        response = self.session.get(BASE_URL, timeout=20)
        response.raise_for_status()
        return response.text

    def _parse_matches(self, html):
        soup = BeautifulSoup(html, "html.parser")
        cards = soup.select("div.match-card")

        results = []

        for card in cards:
            try:
                league = self._get_text(card, ".match-league")
                teams = self._get_text(card, ".match-teams")
                stadium = self._get_text(card, ".match-stadium")
                time_raw = self._get_text(card, ".match-time")

                results.append({
                    "league": league,
                    "title": teams,
                    "stadium": stadium,
                    "match_time": self._parse_time(time_raw),
                    "created_at": datetime.utcnow()
                })

            except Exception as e:
                logger.warning(f"[SCRAPER] Card ignorado: {e}")

        return results

    @staticmethod
    def _get_text(parent, selector):
        el = parent.select_one(selector)
        return el.get_text(strip=True) if el else None

    @staticmethod
    def _parse_time(raw):
        if not raw:
            return None
        try:
            return datetime.strptime(raw, "%H:%M").time()
        except Exception:
            return None
