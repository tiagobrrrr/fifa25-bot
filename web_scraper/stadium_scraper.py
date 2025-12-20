import logging
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from datetime import datetime
from typing import List, Dict
import time

logger = logging.getLogger(__name__)

class StadiumScraper:
    """
    Scraper usando Playwright - VERSÃO OTIMIZADA
    Mais rápido e com logs detalhados
    """

    BASE_URL = "https://football.esportsbattle.com/en/live"
    
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/120.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }

    def __init__(self, timeout: int = 45):
        self.timeout = timeout * 1000

    def collect(self) -> List[Dict]:
        logger.info("[SCRAPER] 🚀 Iniciando coleta de partidas AO VIVO")

        try:
            logger.info("[SCRAPER] 📦 Iniciando Playwright...")
            with sync_playwright() as p:
                logger.info("[SCRAPER] 🌐 Lançando browser...")
                browser = p.chromium.launch(
                    headless=True,
                    args=[
                        '--no-sandbox',
                        '--disable-setuid-sandbox',
                        '--disable-dev-shm-usage',
                        '--disable-gpu'
                    ]
                )
                
                page = browser.new_page()
                logger.info(f"[SCRAPER] 🔗 Acessando {self.BASE_URL}")
                
                # Carrega a página
                page.goto(self.BASE_URL, wait_until="load", timeout=self.timeout)
                logger.info("[SCRAPER] ⏳ Aguardando 5 segundos para JS carregar...")
                
                # Aguarda JavaScript executar
                time.sleep(5)
                
                logger.info("[SCRAPER] 🔍 Buscando cards de partidas...")
                matches = self._extract_live_matches(page)
                
                browser.close()
                logger.info(f"[SCRAPER] ✅ {len(matches)} partidas encontradas!")
                
                return matches

        except Exception as e:
            logger.exception(f"[SCRAPER] ❌ Erro crítico: {e}")
            return []

    def _extract_live_matches(self, page) -> List[Dict]:
        """Extrai partidas ao vivo"""
        results = []
        
        try:
            # Tenta encontrar os cards
            match_cards = page.query_selector_all(".online-matches-match")
            logger.info(f"[SCRAPER] 📋 Encontrados {len(match_cards)} cards")
            
            if len(match_cards) == 0:
                logger.warning("[SCRAPER] ⚠️ Nenhum card encontrado, salvando HTML para debug...")
                html = page.content()
                logger.info(f"[SCRAPER] 📝 Tamanho do HTML: {len(html)} caracteres")
                
                # Verifica se tem o texto esperado
                if "online-matches" in html:
                    logger.info("[SCRAPER] ✓ HTML contém 'online-matches'")
                else:
                    logger.warning("[SCRAPER] ✗ HTML NÃO contém 'online-matches'")
                
                return []
            
            for idx, card in enumerate(match_cards, 1):
                try:
                    match_data = self._parse_live_match(card, idx)
                    if match_data:
                        results.append(match_data)
                        logger.info(f"[SCRAPER] ✓ [{idx}] {match_data['home']} vs {match_data['away']} ({match_data['score']})")
                except Exception as e:
                    logger.warning(f"[SCRAPER] ✗ [{idx}] Erro: {e}")
            
        except Exception as e:
            logger.error(f"[SCRAPER] ❌ Erro na extração: {e}")
        
        return results

    def _parse_live_match(self, card, idx) -> Dict | None:
        """Extrai dados de uma partida"""
        
        try:
            # Liga
            league = self._safe_text(card, ".online-matches-console-details .subcaption-2", f"liga-{idx}")
            
            # Console
            console = self._safe_text(card, ".online-matches-console-label", f"console-{idx}")
            
            # Times
            stats_items = card.query_selector_all(".online-matches-stats-item")
            
            if len(stats_items) < 2:
                logger.debug(f"[SCRAPER] [{idx}] Apenas {len(stats_items)} times encontrados")
                return None
            
            # Home
            home_team = self._safe_text(stats_items[0], ".subcaption-1", f"home-team-{idx}")
            home_player = self._safe_text(stats_items[0], ".online-matches-stats-item-link", f"home-player-{idx}")
            home_score = self._safe_text(stats_items[0], ".online-matches-stats-item-score", f"home-score-{idx}")
            
            # Away
            away_team = self._safe_text(stats_items[1], ".subcaption-1", f"away-team-{idx}")
            away_player = self._safe_text(stats_items[1], ".online-matches-stats-item-link", f"away-player-{idx}")
            away_score = self._safe_text(stats_items[1], ".online-matches-stats-item-score", f"away-score-{idx}")
            
            if not home_team or not away_team:
                return None
            
            return {
                "league": league or "Unknown",
                "home": f"{home_team} ({home_player})" if home_player else home_team,
                "away": f"{away_team} ({away_player})" if away_player else away_team,
                "score": f"{home_score or '0'}-{away_score or '0'}",
                "stadium": f"Console {console}" if console else "Virtual Stadium",
                "status": "LIVE",
                "collected_at": datetime.utcnow()
            }
            
        except Exception as e:
            logger.warning(f"[SCRAPER] [{idx}] Parse error: {e}")
            return None
    
    def _safe_text(self, element, selector: str, debug_id: str = "") -> str:
        """Extrai texto com segurança"""
        try:
            elem = element.query_selector(selector)
            if elem:
                text = elem.inner_text().strip()
                if text:
                    return text
        except Exception as e:
            logger.debug(f"[SCRAPER] Erro ao extrair {debug_id}: {e}")
        return ""