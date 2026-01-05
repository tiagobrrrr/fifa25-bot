import requests
from bs4 import BeautifulSoup
import logging
from datetime import datetime

logger = logging.getLogger('FIFA25Scraper')

class FIFA25Scraper:
    def __init__(self):
        self.base_url = "https://football.esportsbattle.com"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        logger.info("✅ FIFA25Scraper inicializado")
    
    def get_live_matches(self):
        try:
            url = f"{self.base_url}/matches/live"
            logger.info(f"🔍 Buscando partidas ao vivo: {url}")
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            matches = self._parse_matches(soup, status='live')
            logger.info(f"✅ {len(matches)} partidas ao vivo coletadas")
            return matches
        except Exception as e:
            logger.error(f"❌ Erro: {e}")
            return []
    
    def get_recent_matches(self, limit=20):
        try:
            url = f"{self.base_url}/matches/recent"
            logger.info(f"🔍 Buscando partidas recentes")
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            matches = self._parse_matches(soup, status='finished')
            logger.info(f"✅ {len(matches)} partidas recentes coletadas")
            return matches[:limit]
        except Exception as e:
            logger.error(f"❌ Erro: {e}")
            return []
    
    def _parse_matches(self, soup, status='unknown'):
        matches = []
        try:
            match_containers = soup.find_all('div', class_=['match-item', 'match-card'])
            for container in match_containers:
                try:
                    match_data = self._extract_match_data(container, status)
                    if match_data:
                        matches.append(match_data)
                except:
                    continue
        except Exception as e:
            logger.error(f"❌ Parse error: {e}")
        return matches
    
    def _extract_match_data(self, container, status):
        try:
            match_data = {'status': status, 'scraped_at': datetime.utcnow()}
            
            teams = container.find_all('div', class_=['team-name', 'team'])
            if len(teams) >= 2:
                match_data['team1'] = teams[0].get_text(strip=True)
                match_data['team2'] = teams[1].get_text(strip=True)
            
            players = container.find_all('span', class_=['player-name', 'player'])
            if len(players) >= 2:
                match_data['player1'] = players[0].get_text(strip=True)
                match_data['player2'] = players[1].get_text(strip=True)
            
            score_elem = container.find('div', class_=['score', 'match-score'])
            if score_elem:
                match_data['score'] = score_elem.get_text(strip=True)
            else:
                match_data['score'] = "0-0"
            
            match_data['tournament'] = 'FIFA 25'
            match_data['match_time'] = datetime.now().strftime('%H:%M')
            match_data['location'] = 'Online'
            
            if 'team1' in match_data and 'team2' in match_data:
                return match_data
            return None
        except:
            return None
    
    def test_connection(self):
        try:
            response = self.session.get(self.base_url, timeout=10)
            response.raise_for_status()
            logger.info(f"✅ Conexão OK")
            return True
        except Exception as e:
            logger.error(f"❌ Erro: {e}")
            return False