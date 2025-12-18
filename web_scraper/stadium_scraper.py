import requests
import logging
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List, Dict

logger = logging.getLogger(__name__)

class StadiumScraper:
    """
    Scraper compatível com Render (requests only)
    Coleta partidas AO VIVO + FUTURAS
    """

    BASE_URL = "https://football.esportsbattle.com/en/live"

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }

    def __init__(self, timeout: int = 15):
        self.timeout = timeout

    # =====================================================
    # MÉTODO PRINCIPAL (o app.py deve chamar ESSE método)
    # =====================================================
    def collect(self) -> List[Dict]:
        logger.info("[SCRAPER] Coleta iniciada")

        try:
            html = self._fetch_page()
            matches = self._parse_matches(html)

            logger.info(f"[SCRAPER] {len(matches)} partidas encontradas")
            return matches

        except Exception as e:
            logger.exception(f"[SCRAPER] Erro crítico: {e}")
            return []

    # =====================================================
    # HTTP
    # =====================================================
    def _fetch_page(self) -> str:
        response = requests.get(
            self.BASE_URL,
            headers=self.HEADERS,
            timeout=self.timeout
        )
        response.raise_for_status()
        return response.text

    # =====================================================
    # PARSER PRINCIPAL
    # =====================================================
    def _parse_matches(self, html: str) -> List[Dict]:
        soup = BeautifulSoup(html, "html.parser")
        results = []

        # Cards de partidas (estrutura genérica e resiliente)
        match_cards = soup.select("div.match, div.event, div.card")

        for card in match_cards:
            try:
                match = self._parse_single_match(card)
                if match:
                    results.append(match)
            except Exception as e:
                logger.warning(f"[SCRAPER] Erro ao processar card: {e}")

        return results

    # =====================================================
    # PARSER DE UMA PARTIDA
    # =====================================================
    def _parse_single_match(self, card) -> Dict | None:
        def safe_text(selector_list):
            for sel in selector_list:
                el = card.select_one(sel)
                if el and el.get_text(strip=True):
                    return el.get_text(strip=True)
            return None

        league = safe_text([
            ".league",
            ".tournament",
            ".competition"
        ]) or "Unknown League"

        home = safe_text([
            ".home .team-name",
            ".team.home",
            ".team1",
            ".player1"
        ])

        away = safe_text([
            ".away .team-name",
            ".team.away",
            ".team2",
            ".player2"
        ])

        if not home or not away:
            return None  # ignora cards quebrados

        score = safe_text([
            ".score",
            ".result",
            ".score-live"
        ]) or "-"

        stadium = safe_text([
            ".stadium",
            ".venue"
        ]) or "Virtual Stadium"

        status = safe_text([
            ".status",
            ".live",
            ".time"
        ]) or "scheduled"

        return {
            "league": league,
            "home": home,
            "away": away,
            "score": score,
            "stadium": stadium,
            "status": status,
            "collected_at": datetime.utcnow()
        }
