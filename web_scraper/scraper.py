import requests
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class FIFA25Scraper:
    """Scraper para partidas FIFA25"""
    
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
                matches = self._parse_matches(data, is_live=True)
                logger.info(f"✅ {len(matches)} partidas ao vivo encontradas")
                return matches
            else:
                logger.warning(f"⚠️  Status {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"❌ Erro ao coletar ao vivo: {e}")
            return []
    
    def get_recent_matches(self):
        """Coleta partidas recentes"""
        try:
            logger.info("📋 Coletando partidas recentes...")
            
            url = f"{self.base_url}/api/nearest-matches"
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                matches = self._parse_matches(data, is_live=False)
                logger.info(f"✅ {len(matches)} partidas recentes encontradas")
                return matches
            else:
                logger.warning(f"⚠️  Status {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"❌ Erro ao coletar recentes: {e}")
            return []
    
    def _parse_matches(self, data, is_live=False):
        """Parse das partidas"""
        matches = []
        
        try:
            items = data if isinstance(data, list) else data.get('matches', [])
            
            for item in items:
                match = self._extract_match_data(item, is_live)
                if match:
                    matches.append(match)
        except Exception as e:
            logger.error(f"❌ Erro no parse: {e}")
        
        return matches
    
    def _extract_match_data(self, item, is_live=False):
        """Extrai dados de uma partida"""
        try:
            match_id = str(item.get('id', ''))
            if not match_id:
                return None
            
            p1 = item.get('participant1', {})
            p2 = item.get('participant2', {})
            
            player1_name = p1.get('nickname', 'Unknown')
            player2_name = p2.get('nickname', 'Unknown')
            
            player1_team = p1.get('team', {}).get('name') if p1.get('team') else None
            player2_team = p2.get('team', {}).get('name') if p2.get('team') else None
            
            score1 = item.get('score1')
            score2 = item.get('score2')
            
            date_str = item.get('date')
            date = None
            if date_str:
                try:
                    date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                except:
                    date = datetime.utcnow()
            else:
                date = datetime.utcnow()
            
            status_id = item.get('status_id', 0)
            if is_live:
                status = 'live'
            elif status_id == 3:
                status = 'finished'
            else:
                status = 'scheduled'
            
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
            logger.error(f"❌ Erro ao extrair: {e}")
            return None