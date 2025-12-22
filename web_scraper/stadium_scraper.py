import logging
import requests
from datetime import datetime
from typing import List, Dict
import json

logger = logging.getLogger(__name__)

class StadiumScraper:
    """
    Scraper que tenta encontrar a API interna do site
    """

    BASE_URL = "https://football.esportsbattle.com"
    
    # Possíveis endpoints de API
    API_ENDPOINTS = [
        "/api/matches/live",
        "/api/live",
        "/api/v1/matches/live",
        "/api/v1/live",
        "/api/football/live",
        "/live/api",
        "/matches/live",
    ]
    
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://football.esportsbattle.com/en/live",
        "Origin": "https://football.esportsbattle.com",
    }

    def __init__(self, timeout: int = 15):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)

    def collect(self) -> List[Dict]:
        logger.info("[SCRAPER] 🚀 Buscando API interna do site...")

        # Tenta cada endpoint possível
        for endpoint in self.API_ENDPOINTS:
            url = f"{self.BASE_URL}{endpoint}"
            logger.info(f"[SCRAPER] 🔍 Tentando: {url}")
            
            try:
                response = self.session.get(url, timeout=self.timeout)
                
                if response.status_code == 200:
                    logger.info(f"[SCRAPER] ✅ Endpoint funcionou! Status: {response.status_code}")
                    
                    # Tenta parsear JSON
                    try:
                        data = response.json()
                        matches = self._parse_api_response(data)
                        
                        if matches:
                            logger.info(f"[SCRAPER] 🎯 {len(matches)} partidas encontradas via API!")
                            return matches
                    except json.JSONDecodeError:
                        logger.warning(f"[SCRAPER] ⚠️ Resposta não é JSON válido")
                else:
                    logger.debug(f"[SCRAPER] ✗ Status {response.status_code}")
                    
            except Exception as e:
                logger.debug(f"[SCRAPER] ✗ Erro: {e}")
                continue
        
        # Se nenhum endpoint funcionou, retorna dados de teste
        logger.warning("[SCRAPER] ⚠️ Nenhuma API encontrada - usando dados de teste")
        return self._generate_test_data()

    def _parse_api_response(self, data) -> List[Dict]:
        """Tenta parsear resposta da API em diferentes formatos"""
        results = []
        
        try:
            # Formato 1: {matches: [...]}
            if isinstance(data, dict) and "matches" in data:
                matches_data = data["matches"]
            # Formato 2: [{...}, {...}]
            elif isinstance(data, list):
                matches_data = data
            # Formato 3: {data: {matches: [...]}}
            elif isinstance(data, dict) and "data" in data:
                matches_data = data["data"].get("matches", [])
            else:
                logger.warning(f"[SCRAPER] ⚠️ Formato desconhecido: {type(data)}")
                return []
            
            # Processa cada partida
            for match in matches_data[:50]:  # Limita a 50
                try:
                    parsed = self._parse_match_from_api(match)
                    if parsed:
                        results.append(parsed)
                except Exception as e:
                    logger.debug(f"[SCRAPER] Erro ao parsear match: {e}")
                    continue
            
        except Exception as e:
            logger.error(f"[SCRAPER] Erro ao processar API: {e}")
        
        return results

    def _parse_match_from_api(self, match: dict) -> Dict | None:
        """Extrai dados de uma partida da API"""
        try:
            # Tenta diferentes campos comuns em APIs
            home = (match.get("home") or 
                   match.get("homeTeam") or 
                   match.get("team1") or 
                   match.get("home_team") or
                   match.get("player1") or
                   "Unknown")
            
            away = (match.get("away") or 
                   match.get("awayTeam") or 
                   match.get("team2") or 
                   match.get("away_team") or
                   match.get("player2") or
                   "Unknown")
            
            score_home = match.get("scoreHome", match.get("score1", match.get("goals_home", "0")))
            score_away = match.get("scoreAway", match.get("score2", match.get("goals_away", "0")))
            
            league = (match.get("league") or 
                     match.get("tournament") or 
                     match.get("competition") or
                     "Unknown League")
            
            stadium = (match.get("stadium") or 
                      match.get("venue") or 
                      match.get("location") or
                      "Virtual Stadium")
            
            status = match.get("status", "LIVE")
            
            if home == "Unknown" or away == "Unknown":
                return None
            
            return {
                "league": str(league),
                "home": str(home),
                "away": str(away),
                "score": f"{score_home}-{score_away}",
                "stadium": str(stadium),
                "status": str(status),
                "collected_at": datetime.utcnow()
            }
            
        except Exception as e:
            logger.debug(f"[SCRAPER] Erro ao extrair campos: {e}")
            return None

    def _generate_test_data(self) -> List[Dict]:
        """Gera dados de teste variados"""
        import random
        
        now = datetime.utcnow()
        
        teams = [
            ("Real Madrid", "Barcelona"),
            ("Man City", "Liverpool"),
            ("Bayern Munich", "PSG"),
            ("Juventus", "AC Milan"),
            ("Chelsea", "Arsenal"),
        ]
        
        players = [
            ("Player1", "Player2"),
            ("TestGamer", "ProPlayer"),
            ("SkillzZ", "MasterX"),
            ("TopPlayer", "EliteGamer"),
            ("Champion", "Legend"),
        ]
        
        results = []
        for i in range(2):
            home_team, away_team = random.choice(teams)
            home_player, away_player = random.choice(players)
            score_home = random.randint(0, 3)
            score_away = random.randint(0, 3)
            
            results.append({
                "league": "TEST Esports League",
                "home": f"{home_team} ({home_player})",
                "away": f"{away_team} ({away_player})",
                "score": f"{score_home}-{score_away}",
                "stadium": "Virtual Stadium",
                "status": "LIVE",
                "collected_at": now
            })
        
        logger.info(f"[SCRAPER] 🧪 Gerando {len(results)} partidas de TESTE")
        return results