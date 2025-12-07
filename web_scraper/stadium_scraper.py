# web_scraper/stadium_scraper.py
import time
import logging
import requests
from bs4 import BeautifulSoup

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import WebDriverException
from webdriver_manager.chrome import ChromeDriverManager

logger = logging.getLogger("stadium_scraper")
logger.setLevel(logging.INFO)


class StadiumScraper:
    def __init__(self, url="https://football.esportsbattle.com/en", wait_seconds: int = 6):
        """
        wait_seconds: tempo para aguardar a página carregar no Selenium.
        """
        self.url = url
        self.wait_seconds = wait_seconds

    def _get_driver(self):
        opts = Options()
        # Headless moderno
        opts.add_argument("--headless=new")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--window-size=1920,1080")
        # evita logs do Chromium (opcional)
        opts.add_argument("--log-level=3")

        # instala driver via webdriver-manager
        service = Service(ChromeDriverManager().install())

        return webdriver.Chrome(service=service, options=opts)

    def fetch_page_with_selenium(self):
        driver = None
        try:
            driver = self._get_driver()
            driver.get(self.url)
            time.sleep(self.wait_seconds)
            html = driver.page_source
            return html
        finally:
            if driver:
                try:
                    driver.quit()
                except Exception:
                    pass

    def fetch_page_with_requests(self):
        try:
            r = requests.get(self.url, timeout=12, headers={
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
            })
            r.raise_for_status()
            return r.text
        except Exception as e:
            logger.warning("[SCRAPER] requests fetch failed: %s", e)
            return None

    def fetch_page(self):
        """
        Tenta Selenium primeiro. Se houver erro de WebDriver (por ex. sem binário Chrome),
        faz fallback para requests.
        """
        try:
            html = self.fetch_page_with_selenium()
            if html:
                logger.info("[SCRAPER] fetch_page: usando Selenium")
                return html
        except WebDriverException as e:
            # erro típico: cannot find Chrome binary
            logger.warning("[SCRAPER] Selenium indisponível: %s", e)
        except Exception as e:
            logger.warning("[SCRAPER] Selenium erro: %s", e)

        # fallback
        html = self.fetch_page_with_requests()
        if html:
            logger.info("[SCRAPER] fetch_page: usando requests fallback")
        else:
            logger.error("[SCRAPER] fetch_page: falha total ao obter HTML")
        return html

    def parse(self, html: str):
        """
        Parse genérico e robusto — tenta encontrar cards/partidas. Retorna (locations_map, matches_list).
        Cada match é dicionário com chaves: stadium, league, match_time, team1, player1, team2, player2, score, status, match_id
        """
        if not html:
            return {}, []

        soup = BeautifulSoup(html, "html.parser")

        # Tenta extrair mapa de localizações (se houver)
        locations = {}
        # vários sites usam data attributes diferentes; tentamos localizar qualquer bloco 'location' ou 'stadium'
        for loc in soup.find_all(attrs={"data-location": True}):
            lid = loc.get("data-location")
            text = loc.get_text(strip=True)
            if lid:
                locations[lid] = text

        matches = []

        # tentativa 1: procurar por cards mais comuns (match-card / event-card / online-matches)
        card_selectors = [
            {"name": "div", "class_": lambda v: v and ("match-card" in v or "event-card" in v or "online-matches-match" in v)},
            {"name": "div", "class_": lambda v: v and ("match" in v and "card" in v)},
            {"name": "article", "class_": lambda v: v and "match" in v}
        ]

        cards = []
        for sel in card_selectors:
            found = soup.find_all(sel["name"], class_=sel["class_"])
            if found:
                cards.extend(found)

        # fallback: toda vez que não encontre card, tentamos identificar linhas de tabela
        if not cards:
            # procurar por tabelas com colunas 'Time' ou 'Placar'
            tables = soup.find_all("table")
            for t in tables:
                # heurística: tem header com 'Placar' ou 'Time'
                header = t.find("thead")
                text_head = header.get_text(" ").lower() if header else ""
                if "placar" in text_head or "time" in text_head or "score" in text_head:
                    rows = t.find_all("tr")
                    for r in rows[1:]:
                        cols = [c.get_text(strip=True) for c in r.find_all(["td", "th"])]
                        if len(cols) >= 4:
                            matches.append({
                                "stadium": "Unknown",
                                "league": "-",
                                "match_time": cols[-2] if len(cols) >= 4 else "-",
                                "team1": cols[0],
                                "player1": "-",
                                "team2": cols[1] if len(cols) > 1 else "-",
                                "player2": "-",
                                "score": cols[2] if len(cols) > 2 else "-",
                                "status": "Live" if "live" in " ".join(cols).lower() else "Scheduled",
                                "match_id": None
                            })
                    return locations, matches

        # parse cards
        for card in cards:
            try:
                # estádio
                stadium = "-"
                # várias páginas colocam localização em atributo data-location / data-id etc
                for attr in ("data-location", "data-location-id", "data-id", "data-loc"):
                    if card.get(attr):
                        stadium = locations.get(card.get(attr), card.get(attr))
                        break
                if stadium == "-":
                    # procurar elemento com texto 'location' ou 'stadium'
                    el = card.find(class_=lambda v: v and ("location" in v or "stadium" in v))
                    if el:
                        stadium = el.get_text(strip=True)

                # league / time
                league = "-"
                el = card.find(class_=lambda v: v and ("league" in v or "competition" in v or "subcaption" in v))
                if el:
                    league = el.get_text(strip=True)

                # match_time
                match_time = "-"
                el = card.find(class_=lambda v: v and ("time" in v or "hour" in v or "date" in v))
                if el:
                    match_time = el.get_text(strip=True)

                # score
                score = "-"
                el = card.find(class_=lambda v: v and ("score" in v or "result" in v))
                if el:
                    score = el.get_text(strip=True)

                # teams / players: tentamos vários padrões
                team1 = team2 = player1 = player2 = "-"
                # procurar blocos com "team-1"/"team-2" ou "player" classes
                left = card.find(class_=lambda v: v and ("team-1" in v or "left" in v or "player1" in v))
                right = card.find(class_=lambda v: v and ("team-2" in v or "right" in v or "player2" in v))

                if left:
                    # procurar nome do jogador / time em links ou spans
                    a = left.find("a")
                    team1 = a.get_text(strip=True) if a else left.get_text(strip=True)
                if right:
                    a = right.find("a")
                    team2 = a.get_text(strip=True) if a else right.get_text(strip=True)

                # como fallback, buscar por elementos tipo ".online-matches-stats-item"
                stats = card.find_all(class_=lambda v: v and "online-matches-stats-item" in v)
                if stats and len(stats) >= 2:
                    try:
                        left, right = stats[0], stats[1]
                        player1 = left.get_text(" ", strip=True)
                        player2 = right.get_text(" ", strip=True)
                    except Exception:
                        pass

                status = "Live" if "live" in card.get_text(" ").lower() else "Scheduled"

                matches.append({
                    "stadium": stadium or "Unknown",
                    "league": league or "-",
                    "match_time": match_time or "-",
                    "team1": team1 or "-",
                    "player1": player1 or "-",
                    "team2": team2 or "-",
                    "player2": player2 or "-",
                    "score": score or "-",
                    "status": status,
                    "match_id": None
                })
            except Exception:
                continue

        return locations, matches
