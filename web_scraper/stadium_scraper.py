import logging
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List, Dict
import time

logger = logging.getLogger(__name__)

class StadiumScraper:
    """
    Scraper LEVE usando apenas requests
    Tenta acessar a página renderizada do site
    """

    # Tenta usar a versão renderizada ou API
    BASE_URL = "https://football.esportsbattle.com/en/live"
    
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
    }

    def __init__(self, timeout: int = 15):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)

    def collect(self) -> List[Dict]:
        logger.info("[SCRAPER] 🚀 Iniciando coleta LEVE (sem Playwright)")

        try:
            logger.info(f"[SCRAPER] 🔗 Requisitando {self.BASE_URL}")
            
            response = self.session.get(self.BASE_URL, timeout=self.timeout)
            response.raise_for_status()
            
            logger.info(f"[SCRAPER] ✅ Página carregada ({len(response.text)} bytes)")
            
            # Tenta parsear
            matches = self._extract_from_html(response.text)
            
            logger.info(f"[SCRAPER] 🎯 {len(matches)} partidas encontradas!")
            return matches

        except Exception as e:
            logger.exception(f"[SCRAPER] ❌ Erro: {e}")
            return []

    def _extract_from_html(self, html: str) -> List[Dict]:
        """Tenta extrair partidas do HTML"""
        results = []
        
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Verifica se tem o texto esperado
            html_lower = html.lower()
            if 'online-matches' in html_lower:
                logger.info("[SCRAPER] ✓ HTML contém 'online-matches'")
            else:
                logger.warning("[SCRAPER] ✗ HTML NÃO contém 'online-matches' - Site não carregou completamente")
                
            # Tenta encontrar cards
            cards = soup.find_all(class_=lambda x: x and 'online-matches-match' in x)
            logger.info(f"[SCRAPER] 📋 Encontrados {len(cards)} cards potenciais")
            
            if len(cards) == 0:
                # Fallback: cria dados de teste para verificar se o resto funciona
                logger.warning("[SCRAPER] ⚠️ Nenhum card encontrado - retornando dados de teste")
                return self._generate_test_data()
            
            for idx, card in enumerate(cards, 1):
                try:
                    match = self._parse_card(card, idx)
                    if match:
                        results.append(match)
                        logger.info(f"[SCRAPER] ✓ [{idx}] {match['home']} vs {match['away']}")
                except Exception as e:
                    logger.warning(f"[SCRAPER] ✗ [{idx}] Erro: {e}")
            
        except Exception as e:
            logger.error(f"[SCRAPER] ❌ Erro ao parsear: {e}")
        
        return results

    def _parse_card(self, card, idx) -> Dict | None:
        """Tenta extrair dados de um card"""
        try:
            # Busca texto que contenha nomes de times
            text = card.get_text(separator=' | ', strip=True)
            
            # Exemplo: "Super Lig 2025-12-20 | Galatasaray | Maki | 2 | Besiktas | lzrn | 0"
            parts = [p.strip() for p in text.split('|') if p.strip()]
            
            if len(parts) < 4:
                return None
            
            return {
                "league": parts[0] if len(parts) > 0 else "Unknown",
                "home": parts[1] if len(parts) > 1 else "Team A",
                "away": parts[2] if len(parts) > 2 else "Team B",
                "score": f"{parts[3]}-{parts[4]}" if len(parts) > 4 else "0-0",
                "stadium": "Virtual Stadium",
                "status": "LIVE",
                "collected_at": datetime.utcnow()
            }
        except:
            return None

    def _generate_test_data(self) -> List[Dict]:
        """Gera dados de teste para verificar se o resto do sistema funciona"""
        logger.info("[SCRAPER] 🧪 Gerando dados de TESTE")
        
        now = datetime.utcnow()
        
        return [
            {
                "league": "TEST Super Lig 2025",
                "home": "Test Team A (Player1)",
                "away": "Test Team B (Player2)",
                "score": "1-1",
                "stadium": "Test Virtual Stadium",
                "status": "LIVE",
                "collected_at": now
            },
            {
                "league": "TEST Champions League",
                "home": "Test City (TestPlayer)",
                "away": "Test United (TestGamer)",
                "score": "2-0",
                "stadium": "Test Arena",
                "status": "LIVE",
                "collected_at": now
            }
        ]