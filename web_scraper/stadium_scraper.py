import requests
from bs4 import BeautifulSoup
import logging

logger = logging.getLogger(__name__)

class StadiumScraper:
    def __init__(self):
        self.url = "https://football.esportsbattle.com/"

        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }

    def collect(self):
        logger.info("[SCRAPER] Coleta iniciada")

        try:
            response = requests.get(self.url, headers=self.headers, timeout=15)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            matches = []

            # 🔥 SELETOR REAL
            cards = soup.select("div.match-card")

            for card in cards:
                try:
                    home = card.select_one(".team.home")
                    away = card.select_one(".team.away")
                    league = card.select_one(".league")
                    stadium = card.select_one(".stadium")
                    time = card.select_one(".time")

                    match = {
                        "home_team": home.text.strip() if home else "N/A",
                        "away_team": away.text.strip() if away else "N/A",
                        "league": league.text.strip() if league else "N/A",
                        "stadium": stadium.text.strip() if stadium else "N/A",
                        "status": time.text.strip() if time else "N/A",
                    }

                    matches.append(match)

                except Exception as e:
                    logger.warning(f"[SCRAPER] Erro ao processar card: {e}")

            logger.info(f"[SCRAPER] {len(matches)} partidas encontradas")
            return matches

        except Exception as e:
            logger.error(f"[SCRAPER] Falha crítica: {e}")
            return []
