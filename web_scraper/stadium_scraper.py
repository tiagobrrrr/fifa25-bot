import logging
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from datetime import datetime
from typing import List, Dict

logger = logging.getLogger(__name__)

class StadiumScraper:
    """
    Scraper usando Playwright - COLETA PARTIDAS AO VIVO 24/7
    Coleta todas as partidas em andamento
    """

    BASE_URL = "https://football.esportsbattle.com/en/live"
    
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/120.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }

    def __init__(self, timeout: int = 30):
        self.timeout = timeout * 1000

    def collect(self) -> List[Dict]:
        logger.info("[SCRAPER] Coleta iniciada - buscando partidas AO VIVO")

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                    args=[
                        '--no-sandbox',
                        '--disable-setuid-sandbox',
                        '--disable-dev-shm-usage',
                        '--disable-accelerated-2d-canvas',
                        '--disable-gpu',
                        '--window-size=1920x1080'
                    ]
                )
                
                context = browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent=self.HEADERS["User-Agent"]
                )
                
                page = context.new_page()
                
                logger.info(f"[SCRAPER] Acessando {self.BASE_URL}")
                page.goto(self.BASE_URL, wait_until="networkidle", timeout=self.timeout)
                
                # Aguarda conteúdo carregar
                page.wait_for_selector(".online-matches-match", timeout=10000)
                
                # Coleta TODAS as partidas ao vivo
                matches = self._extract_live_matches(page)
                
                browser.close()
                
                logger.info(f"[SCRAPER] {len(matches)} partidas AO VIVO encontradas")
                return matches

        except Exception as e:
            logger.exception(f"[SCRAPER] Erro crítico: {e}")
            return []

    def _extract_live_matches(self, page) -> List[Dict]:
        """Extrai TODAS as partidas ao vivo (incluindo 0-0)"""
        results = []
        
        try:
            # Pega todos os cards de partidas
            match_cards = page.query_selector_all(".online-matches-match")
            
            logger.info(f"[SCRAPER] Analisando {len(match_cards)} partidas ao vivo")
            
            for card in match_cards:
                try:
                    match_data = self._parse_live_match(card)
                    if match_data:
                        results.append(match_data)
                        logger.info(f"[SCRAPER] ✓ AO VIVO: {match_data['home']} vs {match_data['away']} ({match_data['score']})")
                except Exception as e:
                    logger.warning(f"[SCRAPER] Erro ao parsear card: {e}")
                    continue
            
        except Exception as e:
            logger.error(f"[SCRAPER] Erro ao extrair partidas: {e}")
        
        return results

    def _parse_live_match(self, card) -> Dict | None:
        """
        Extrai dados de partidas AO VIVO
        Coleta TODAS as partidas, incluindo 0-0
        """
        
        try:
            # Liga/Torneio
            league_elem = card.query_selector(".online-matches-console-details .subcaption-2")
            league = league_elem.inner_text().strip() if league_elem else "Unknown League"
            
            # Data/Hora
            date_elem = card.query_selector(".online-matches-console-details .subcaption-1")
            match_date = date_elem.inner_text().strip() if date_elem else ""
            
            # Console/Local
            console_elem = card.query_selector(".online-matches-console-label")
            console = console_elem.inner_text().strip() if console_elem else ""
            
            # Pega os dois times
            stats_items = card.query_selector_all(".online-matches-stats-item")
            
            if len(stats_items) < 2:
                logger.debug(f"[SCRAPER] Card sem 2 times, ignorando")
                return None
            
            # Time 1 (Home)
            home_item = stats_items[0]
            home_team_elem = home_item.query_selector(".subcaption-1")
            home_team = home_team_elem.inner_text().strip() if home_team_elem else "Unknown"
            
            home_player_elem = home_item.query_selector(".online-matches-stats-item-link")
            home_player = home_player_elem.inner_text().strip() if home_player_elem else "Unknown"
            
            home_score_elem = home_item.query_selector(".online-matches-stats-item-score")
            home_score = home_score_elem.inner_text().strip() if home_score_elem else "0"
            
            # Time 2 (Away)
            away_item = stats_items[1]
            away_team_elem = away_item.query_selector(".subcaption-1")
            away_team = away_team_elem.inner_text().strip() if away_team_elem else "Unknown"
            
            away_player_elem = away_item.query_selector(".online-matches-stats-item-link")
            away_player = away_player_elem.inner_text().strip() if away_player_elem else "Unknown"
            
            away_score_elem = away_item.query_selector(".online-matches-stats-item-score")
            away_score = away_score_elem.inner_text().strip() if away_score_elem else "0"
            
            # Valida apenas se os nomes não são vazios
            if home_team == "Unknown" or away_team == "Unknown":
                logger.debug(f"[SCRAPER] Partida com times inválidos, ignorando")
                return None
            
            # Retorna a partida AO VIVO (mesmo que seja 0-0)
            return {
                "league": league,
                "home": f"{home_team} ({home_player})",
                "away": f"{away_team} ({away_player})",
                "score": f"{home_score}-{away_score}",
                "stadium": f"Console {console}" if console else "Virtual Stadium",
                "status": "LIVE",
                "collected_at": datetime.utcnow()
            }
            
        except Exception as e:
            logger.warning(f"[SCRAPER] Erro ao parsear match: {e}")
            return None