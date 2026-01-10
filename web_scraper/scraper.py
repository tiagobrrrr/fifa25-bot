import requests
from bs4 import BeautifulSoup
import logging
from datetime import datetime
import json

logger = logging.getLogger(__name__)

class FIFA25Scraper:
    """Scraper melhorado para partidas FIFA25"""
    
    def __init__(self):
        self.base_url = "https://football.esportsbattle.com"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
    
    def get_live_matches(self):
        """Coleta partidas ao vivo"""
        try:
            logger.info("🔴 Coletando partidas AO VIVO...")
            
            url = f"{self.base_url}/api/live-matches"
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                matches = self._parse_live_matches(data)
                logger.info(f"✅ {len(matches)} partidas ao vivo encontradas")
                return matches
            else:
                logger.warning(f"⚠️  Status {response.status_code} ao coletar partidas ao vivo")
                return []
                
        except Exception as e:
            logger.error(f"❌ Erro ao coletar partidas ao vivo: {e}")
            return []
    
    def get_recent_matches(self):
        """Coleta partidas recentes"""
        try:
            logger.info("📋 Coletando partidas recentes...")
            
            url = f"{self.base_url}/api/nearest-matches"
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                matches = self._parse_recent_matches(data)
                logger.info(f"✅ {len(matches)} partidas recentes encontradas")
                return matches
            else:
                logger.warning(f"⚠️  Status {response.status_code} ao coletar partidas recentes")
                return []
                
        except Exception as e:
            logger.error(f"❌ Erro ao coletar partidas recentes: {e}")
            return []
    
    def _parse_live_matches(self, data):
        """Parse das partidas ao vivo"""
        matches = []
        
        try:
            if isinstance(data, list):
                for item in data:
                    match = self._extract_match_data(item, is_live=True)
                    if match:
                        matches.append(match)
            elif isinstance(data, dict) and 'matches' in data:
                for item in data['matches']:
                    match = self._extract_match_data(item, is_live=True)
                    if match:
                        matches.append(match)
        except Exception as e:
            logger.error(f"❌ Erro ao fazer parse de partidas ao vivo: {e}")
        
        return matches
    
    def _parse_recent_matches(self, data):
        """Parse das partidas recentes"""
        matches = []
        
        try:
            if isinstance(data, list):
                for item in data:
                    match = self._extract_match_data(item, is_live=False)
                    if match:
                        matches.append(match)
            elif isinstance(data, dict) and 'matches' in data:
                for item in data['matches']:
                    match = self._extract_match_data(item, is_live=False)
                    if match:
                        matches.append(match)
        except Exception as e:
            logger.error(f"❌ Erro ao fazer parse de partidas recentes: {e}")
        
        return matches
    
    def _extract_match_data(self, item, is_live=False):
        """Extrai dados de uma partida"""
        try:
            match_id = str(item.get('id', ''))
            
            if not match_id:
                return None
            
            # Dados dos jogadores
            p1 = item.get('participant1', {})
            p2 = item.get('participant2', {})
            
            player1_name = p1.get('nickname', 'Unknown')
            player2_name = p2.get('nickname', 'Unknown')
            
            player1_team = p1.get('team', {}).get('name') if p1.get('team') else None
            player2_team = p2.get('team', {}).get('name') if p2.get('team') else None
            
            # Placar
            score1 = item.get('score1')
            score2 = item.get('score2')
            
            # Data
            date_str = item.get('date')
            date = None
            if date_str:
                try:
                    date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                except:
                    date = datetime.utcnow()
            else:
                date = datetime.utcnow()
            
            # Status
            status_id = item.get('status_id', 0)
            if is_live:
                status = 'live'
            elif status_id == 3:
                status = 'finished'
            else:
                status = 'scheduled'
            
            # Outras informações
            location = item.get('location', {}).get('token', '') if item.get('location') else None
            console = item.get('console', {}).get('token', '') if item.get('console') else None
            tournament = item.get('tournament', {}).get('name') if item.get('tournament') else None
            round_info = item.get('round', {}).get('name') if item.get('round') else None
            
            return {
                'match_id': match_id,
                'player1_name': player1_name,
                'player2_name': player2_name,
                'player1_team': player1_team,
                'player2_team': player2_team,
                'score1': score1,
                'score2': score2,
                'date': date,
                'status': status,
                'location': location,
                'console': console,
                'tournament': tournament,
                'round': round_info
            }
            
        except Exception as e:
            logger.error(f"❌ Erro ao extrair dados da partida: {e}")
            return None
