import logging
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from datetime import datetime
from typing import List, Dict
import time

logger = logging.getLogger(__name__)

class StadiumScraper:
    """
    Scraper usando Playwright - COLETA PARTIDAS AO VIVO 24/7
    Otimizado para lidar com carregamento lento
    """

    BASE_URL = "https://football.esportsbattle.com/en/live"
    
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/120.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }

    def __init__(self, timeout: int = 60):
        self.timeout = timeout * 1000  # 60 segundos

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
                
                # Carrega a página com timeout maior
                page.goto(self.BASE_URL, wait_until="domcontentloaded", timeout=self.timeout)
                
                # Aguarda um pouco para o JavaScript executar
                logger.info("[SCRAPER] Aguardando JavaScript carregar...")
                time.sleep(3)
                
                # Tenta aguardar o seletor com timeout maior
                try:
                    page.wait_for_selector(".online-matches-match", timeout=20000)
                    logger.info("[SCRAPER] Cards de partidas encontrados!")
                except PlaywrightTimeout:
                    logger.warning("[SCRAPER] Timeout ao aguardar cards, tentando extrair mesmo assim...")
                
                # Tenta extrair mesmo se der timeout
                matches = self._extract_live_matches(page)
                
                browser.close()
                
                logger.info(f"[SCRAPER] {len(matches)} partidas AO VIVO encontradas")
                return matches

        except Exception as e:
            logger.exception(f"[SCRAPER] Erro crítico: {e}")
            return []

    def _extract_live_matches(self, page) -> List[Dict]:
        """Extrai TODAS as partidas ao vivo"""
        results = []
        
        try:
            # Tenta múltiplas estratégias de seleção
            match_cards = page.query_selector_all(".online-matches-match")
            
            if not match_cards:
                logger.warning("[SCRAPER] Nenhum card encontrado com .online-matches-match")
                # Tenta seletor alternativo
                match_cards = page.query_selector_all("div[class*='online-matches']")
                logger.info(f"[SCRAPER] Tentativa alternativa encontrou {len(match_cards)} elementos")
            
            logger.info(f"[SCRAPER] Analisando {len(match_cards)} partidas ao vivo")
            
            for idx, card in enumerate(match_cards):
                try:
                    match_data = self._parse_live_match(card)
                    if match_data:
                        results.append(match_data)
                        logger.info(f"[SCRAPER] ✓ [{idx+1}] AO VIVO: {match_data['home']} vs {match_data['away']} ({match_data['score']})")
                except Exception as e:
                    logger.warning(f"[SCRAPER] Erro ao parsear card {idx+1}: {e}")
                    continue
            
        except Exception as e:
            logger.error(f"[SCRAPER] Erro ao extrair partidas: {e}")
        
        return results

    def _parse_live_match(self, card) -> Dict | None:
        """
        Extrai dados de partidas AO VIVO
        Mais robusto com tratamento de erros
        """
        
        try:
            # Liga/Torneio
            league = self._safe_text(card, [
                ".online-matches-console-details .subcaption-2",
                ".subcaption-2",
                "[class*='console-details'] [class*='subcaption']"
            ])
            
            # Data/Hora
            match_date = self._safe_text(card, [
                ".online-matches-console-details .subcaption-1",
                ".subcaption-1"
            ])
            
            # Console/Local
            console = self._safe_text(card, [
                ".online-matches-console-label",
                "[class*='console-label']"
            ])
            
            # Pega os dois times
            stats_items = card.query_selector_all(".online-matches-stats-item")
            
            if not stats_items:
                stats_items = card.query_selector_all("[class*='stats-item']")
            
            if len(stats_items) < 2:
                logger.debug(f"[SCRAPER] Card sem 2 times ({len(stats_items)} encontrados), ignorando")
                return None
            
            # Time 1 (Home)
            home_team = self._safe_text(stats_items[0], [
                ".subcaption-1",
                "[class*='subcaption']"
            ])
            
            home_player = self._safe_text(stats_items[0], [
                ".online-matches-stats-item-link",
                "a[href*='participants']",
                ".text-link"
            ])
            
            home_score = self._safe_text(stats_items[0], [
                ".online-matches-stats-item-score",
                "[class*='score']",
                "span:last-child"
            ])
            
            # Time 2 (Away)
            away_team = self._safe_text(stats_items[1], [
                ".subcaption-1",
                "[class*='subcaption']"
            ])
            
            away_player = self._safe_text(stats_items[1], [
                ".online-matches-stats-item-link",
                "a[href*='participants']",
                ".text-link"
            ])
            
            away_score = self._safe_text(stats_items[1], [
                ".online-matches-stats-item-score",
                "[class*='score']",
                "span:last-child"
            ])
            
            # Valida dados mínimos
            if not home_team or not away_team:
                logger.debug(f"[SCRAPER] Partida com times inválidos, ignorando")
                return None
            
            # Limpa os textos
            home_team = home_team.strip()
            away_team = away_team.strip()
            home_player = home_player.strip() if home_player else "Unknown"
            away_player = away_player.strip() if away_player else "Unknown"
            home_score = home_score.strip() if home_score else "0"
            away_score = away_score.strip() if away_score else "0"
            
            # Retorna a partida
            return {
                "league": league or "Unknown League",
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
    
    def _safe_text(self, element, selectors: list) -> str:
        """Tenta múltiplos seletores até encontrar um que funcione"""
        for selector in selectors:
            try:
                elem = element.query_selector(selector)
                if elem:
                    text = elem.inner_text().strip()
                    if text:
                        return text
            except:
                continue
        return ""