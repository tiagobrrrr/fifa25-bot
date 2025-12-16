import requests
import logging
from bs4 import BeautifulSoup
from datetime import datetime
import pytz

logger = logging.getLogger(__name__)

class StadiumScraper:
    """
    Scraper compatível com Render (requests only)
    Coleta partidas AO VIVO do football.esportsbattle.com
    """

    BASE_URL = "https://football.esportsbattle.com/en/live"

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html",
        "Connection": "keep-alive",
    }

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)

    # =========================
    # MÉTODO PRINCIPAL (APP USA ESSE)
    # =========================
    def run(self) -> list[dict]:
        logger.info("[SCRAPER] Coleta iniciada")

        html = self._fetch_page()
        if not html:
            return []

        matches = self._parse_matches(html)

        logger.info(f"[SCRAPER] {len(matches)} partidas encontradas")
        return matches

    # =========================
    # DOWNLOAD DA PÁGINA
    # =========================
    def _fetch_page(self) -> str | None:
        try:
            response = self.session.get(self.BASE_URL, timeout=20)
            response.raise_for_status()
            return response.text
        except Exception as e:
            logger.error(f"[SCRAPER] Erro ao baixar página: {e}")
            return None

    # =========================
    # PARSE DO HTML
    # =========================
    def _parse_matches(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        results = []

        # 🔥 IMPORTANTE
        # Ajuste este seletor caso o site mude
        cards = soup.select("div.match-row, div.event-row, div.match-item")

        if not cards:
            return results

        for card in cards:
            try:
                match = self._parse_single_match(card)
                if match:
                    results.append(match)
            except Exception as e:
                logger.warning(f"[SCRAPER] Erro ao parsear card: {e}")

        return results

    # =========================
    # PARSE DE UMA PARTIDA
    # =========================
    def _parse_single_match(self, card) -> dict | None:
        text = card.get_text(" ", strip=True)

        # Filtro mínimo para evitar lixo
        if " vs " not in text.lower():
            return None

        # Tentativas flexíveis de captura
        home, away = self._extract_teams(card)
        league = self._extract_league(card)
        stadium = self._extract_stadium(card)
        match_time = self._extract_time(card)

        if not home or not away:
            return None

        return {
            "league": league or "Unknown",
            "title": f"{home} vs {away}",
            "stadium": stadium or "Unknown",
            "match_time": match_time,
            "created_at": self._now_utc()
        }

    # =========================
    # MÉTODOS AUXILIARES
    # =========================
    def _extract_teams(self, card):
        teams = card.select("span.team-name, div.team-name")

        if len(teams) >= 2:
            return teams[0].get_text(strip=True), teams[1].get_text(strip=True)

        text = card.get_text(" ", strip=True)
        if " vs " in text:
            parts = text.split(" vs ")
            return parts[0].strip(), parts[1].split(" ")[0].strip()

        return None, None

    def _extract_league(self, card):
        el = card.select_one(".league, .tournament, .competition")
        return el.get_text(strip=True) if el else None

    def _extract_stadium(self, card):
        el = card.select_one(".stadium, .arena, .location")
        return el.get_text(strip=True) if el else None

    def _extract_time(self, card):
        el = card.select_one("time")
        if el and el.get("datetime"):
            try:
                return datetime.fromisoformat(el["datetime"])
            except Exception:
                pass
        return self._now_utc()

    def _now_utc(self):
        return datetime.now(tz=pytz.UTC)
