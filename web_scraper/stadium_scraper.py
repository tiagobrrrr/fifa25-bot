import requests
from bs4 import BeautifulSoup
import logging
from datetime import datetime

logger = logging.getLogger("stadium_scraper")

BASE_URL = "https://football.esportsbattle.com/en/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}


class StadiumScraper:
    def __init__(self, timeout=15):
        self.timeout = timeout

    def fetch_page(self):
        logger.info("[stadium_scraper] Fetch via requests")
        resp = requests.get(BASE_URL, headers=HEADERS, timeout=self.timeout)
        resp.raise_for_status()
        return resp.text

    def parse_matches(self, html):
        soup = BeautifulSoup(html, "html.parser")

        cards = soup.select(".event-card, .match-card, .card")
        logger.info(f"[stadium_scraper] Cards encontrados: {len(cards)}")

        matches = []

        for card in cards:
            try:
                time1 = card.select_one(".team1, .home, .team-home")
                time2 = card.select_one(".team2, .away, .team-away")
                score = card.select_one(".score, .result")
                league = card.select_one(".league, .tournament")
                time_info = card.select_one(".time, .match-time")

                if not time1 or not time2:
                    continue

                match = {
                    "time1": time1.get_text(strip=True),
                    "time2": time2.get_text(strip=True),
                    "placar": score.get_text(strip=True) if score else "0 - 0",
                    "liga": league.get_text(strip=True) if league else "Desconhecida",
                    "horario": time_info.get_text(strip=True) if time_info else "",
                    "status": "Ao Vivo",
                    "updated_at": datetime.utcnow(),
                }

                matches.append(match)

            except Exception as e:
                logger.warning(f"[stadium_scraper] Erro ao parsear card: {e}")

        return matches

    def get_live_matches(self):
        html = self.fetch_page()
        return self.parse_matches(html)
