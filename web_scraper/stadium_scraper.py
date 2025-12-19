import logging
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from datetime import datetime
from typing import List, Dict

logger = logging.getLogger(__name__)

class StadiumScraper:
    """
    Scraper usando Playwright para sites SPA (Single Page Application)
    Compatível com Render
    """

    BASE_URL = "https://football.esportsbattle.com/en/live"
    
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }

    def __init__(self, timeout: int = 30):
        self.timeout = timeout * 1000  # Converte para ms

    # =====================================================
    # MÉTODO PRINCIPAL
    # =====================================================
    def collect(self) -> List[Dict]:
        logger.info("[SCRAPER] Coleta iniciada com Playwright")

        try:
            with sync_playwright() as p:
                # Lança browser headless
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
                
                # Acessa página
                logger.info(f"[SCRAPER] Acessando {self.BASE_URL}")
                page.goto(self.BASE_URL, wait_until="networkidle", timeout=self.timeout)
                
                # Aguarda conteúdo carregar (tenta múltiplos seletores)
                matches = self._wait_and_extract(page)
                
                browser.close()
                
                logger.info(f"[SCRAPER] {len(matches)} partidas encontradas")
                return matches

        except Exception as e:
            logger.exception(f"[SCRAPER] Erro crítico: {e}")
            return []

    # =====================================================
    # EXTRAÇÃO DE DADOS
    # =====================================================
    def _wait_and_extract(self, page) -> List[Dict]:
        """Aguarda e extrai dados com múltiplas estratégias"""
        
        # Lista de seletores possíveis (do mais específico ao mais genérico)
        selectors_to_try = [
            ".match-card",
            ".match-item",
            ".game-card",
            "[class*='match']",
            "[class*='game']",
            ".event-row",
            ".fixture"
        ]
        
        matches_elements = []
        
        for selector in selectors_to_try:
            try:
                logger.info(f"[SCRAPER] Tentando seletor: {selector}")
                page.wait_for_selector(selector, timeout=5000)
                matches_elements = page.query_selector_all(selector)
                
                if matches_elements and len(matches_elements) > 0:
                    logger.info(f"[SCRAPER] ✓ Seletor funcionou: {selector} ({len(matches_elements)} elementos)")
                    break
            except PlaywrightTimeout:
                continue
        
        if not matches_elements:
            logger.warning("[SCRAPER] Nenhum seletor funcionou, tentando extrair todo conteúdo...")
            return self._extract_from_full_page(page)
        
        # Extrai dados dos elementos encontrados
        results = []
        for elem in matches_elements[:50]:  # Limita a 50 partidas
            try:
                match_data = self._parse_match_element(elem, page)
                if match_data:
                    results.append(match_data)
            except Exception as e:
                logger.warning(f"[SCRAPER] Erro ao parsear elemento: {e}")
                continue
        
        return results

    # =====================================================
    # PARSER DE ELEMENTO INDIVIDUAL
    # =====================================================
    def _parse_match_element(self, element, page) -> Dict | None:
        """Extrai dados de um elemento de partida"""
        
        def safe_extract(selectors_list):
            """Tenta múltiplos seletores"""
            for sel in selectors_list:
                try:
                    el = element.query_selector(sel)
                    if el:
                        text = el.inner_text().strip()
                        if text:
                            return text
                except:
                    continue
            return None
        
        # Tenta extrair informações
        league = safe_extract([
            ".league", ".tournament", ".competition", 
            "[class*='league']", "[class*='tournament']"
        ])
        
        home = safe_extract([
            ".home-team", ".team-home", ".team1", ".player1",
            "[class*='home']", "[class*='team1']"
        ])
        
        away = safe_extract([
            ".away-team", ".team-away", ".team2", ".player2",
            "[class*='away']", "[class*='team2']"
        ])
        
        score = safe_extract([
            ".score", ".result", ".goals", 
            "[class*='score']", "[class*='result']"
        ])
        
        status = safe_extract([
            ".status", ".live", ".state",
            "[class*='status']", "[class*='live']"
        ])
        
        # Valida se tem dados mínimos
        if not home or not away:
            return None
        
        return {
            "league": league or "Unknown League",
            "home": home,
            "away": away,
            "score": score or "-",
            "stadium": "Virtual Stadium",
            "status": status or "scheduled",
            "collected_at": datetime.utcnow()
        }

    # =====================================================
    # FALLBACK: EXTRAÇÃO DA PÁGINA COMPLETA
    # =====================================================
    def _extract_from_full_page(self, page) -> List[Dict]:
        """Última tentativa: extrai texto completo e tenta parsear"""
        
        try:
            # Pega screenshot para debug (opcional)
            # page.screenshot(path="debug.png")
            
            # Extrai todo texto da página
            content = page.content()
            
            logger.info("[SCRAPER] Tentando extrair do conteúdo completo da página...")
            logger.info(f"[SCRAPER] Tamanho do HTML: {len(content)} caracteres")
            
            # Se ainda está vazio, o site pode estar bloqueando
            if len(content) < 1000:
                logger.error("[SCRAPER] Página muito pequena, possível bloqueio")
                return []
            
            # Aqui você pode adicionar lógica customizada
            # baseada no HTML específico do site
            
            return []
            
        except Exception as e:
            logger.exception(f"[SCRAPER] Erro no fallback: {e}")
            return []