import requests
from bs4 import BeautifulSoup
import logging
from datetime import datetime
import time

logger = logging.getLogger('FIFA25Scraper')


class FIFA25Scraper:
    """
    Scraper para coletar dados de partidas FIFA 25
    do site football.esportsbattle.com
    """
    
    def __init__(self):
        self.base_url = "https://football.esportsbattle.com"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
            'Connection': 'keep-alive',
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        logger.info("✅ FIFA25Scraper inicializado")
    
    def get_live_matches(self):
        """
        Coleta partidas ao vivo
        """
        try:
            url = f"{self.base_url}/matches/live"
            logger.info(f"🔍 Buscando partidas ao vivo: {url}")
            
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            matches = self._parse_matches(soup, status='live')
            
            logger.info(f"✅ {len(matches)} partidas ao vivo coletadas")
            return matches
            
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Erro ao buscar partidas ao vivo: {e}")
            return []
        except Exception as e:
            logger.error(f"❌ Erro ao processar partidas ao vivo: {e}")
            return []
    
    def get_recent_matches(self, limit=20):
        """
        Coleta partidas recentes/finalizadas
        """
        try:
            url = f"{self.base_url}/matches/recent"
            logger.info(f"🔍 Buscando partidas recentes: {url}")
            
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            matches = self._parse_matches(soup, status='finished')
            
            logger.info(f"✅ {len(matches)} partidas recentes coletadas")
            return matches[:limit]
            
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Erro ao buscar partidas recentes: {e}")
            return []
        except Exception as e:
            logger.error(f"❌ Erro ao processar partidas recentes: {e}")
            return []
    
    def _parse_matches(self, soup, status='unknown'):
        """
        Faz o parse do HTML e extrai informações das partidas
        """
        matches = []
        
        try:
            # Procurar por containers de partidas
            # Ajuste os seletores de acordo com a estrutura real do site
            match_containers = soup.find_all('div', class_=['match-item', 'match-card', 'game-item'])
            
            if not match_containers:
                # Tentar seletores alternativos
                match_containers = soup.find_all('div', {'data-match': True})
            
            if not match_containers:
                logger.warning("⚠️  Nenhum container de partida encontrado")
                return []
            
            for container in match_containers:
                try:
                    match_data = self._extract_match_data(container, status)
                    if match_data:
                        matches.append(match_data)
                except Exception as e:
                    logger.debug(f"Erro ao processar container: {e}")
                    continue
            
        except Exception as e:
            logger.error(f"❌ Erro no parse de partidas: {e}")
        
        return matches
    
    def _extract_match_data(self, container, status):
        """
        Extrai dados de uma partida individual do container HTML
        """
        try:
            match_data = {
                'status': status,
                'scraped_at': datetime.utcnow()
            }
            
            # Extrair times (ajustar seletores conforme necessário)
            teams = container.find_all('div', class_=['team-name', 'team'])
            if len(teams) >= 2:
                match_data['team1'] = teams[0].get_text(strip=True)
                match_data['team2'] = teams[1].get_text(strip=True)
            
            # Extrair jogadores
            players = container.find_all('span', class_=['player-name', 'player'])
            if len(players) >= 2:
                match_data['player1'] = players[0].get_text(strip=True)
                match_data['player2'] = players[1].get_text(strip=True)
            
            # Extrair placar - ✅ AGORA SALVA COMO STRING ÚNICA
            score_elem = container.find('div', class_=['score', 'match-score', 'result'])
            if score_elem:
                score_text = score_elem.get_text(strip=True)
                match_data['score'] = score_text  # Ex: "2-1", "3-0"
            else:
                # Tentar extrair scores individuais e combinar
                scores = container.find_all('span', class_=['score-value', 'goals'])
                if len(scores) >= 2:
                    score1 = scores[0].get_text(strip=True)
                    score2 = scores[1].get_text(strip=True)
                    match_data['score'] = f"{score1}-{score2}"
                else:
                    match_data['score'] = "0-0"
            
            # Extrair torneio
            tournament = container.find('div', class_=['tournament', 'league', 'competition'])
            if tournament:
                match_data['tournament'] = tournament.get_text(strip=True)
            else:
                match_data['tournament'] = 'FIFA 25'
            
            # Extrair horário
            time_elem = container.find('time', class_=['match-time', 'time'])
            if time_elem:
                match_data['match_time'] = time_elem.get_text(strip=True)
            else:
                match_data['match_time'] = datetime.now().strftime('%H:%M')
            
            # Extrair localização (se disponível)
            location = container.find('span', class_=['location', 'venue'])
            if location:
                match_data['location'] = location.get_text(strip=True)
            else:
                match_data['location'] = 'Online'
            
            # Validar dados mínimos
            if not all(k in match_data for k in ['team1', 'team2']):
                return None
            
            return match_data
            
        except Exception as e:
            logger.debug(f"Erro ao extrair dados da partida: {e}")
            return None
    
    def get_match_details(self, match_id):
        """
        Obtém detalhes completos de uma partida específica
        """
        try:
            url = f"{self.base_url}/match/{match_id}"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            # Implementar parse de detalhes se necessário
            
            return {}
            
        except Exception as e:
            logger.error(f"❌ Erro ao buscar detalhes da partida {match_id}: {e}")
            return {}
    
    def test_connection(self):
        """
        Testa a conexão com o site
        """
        try:
            response = self.session.get(self.base_url, timeout=10)
            response.raise_for_status()
            logger.info(f"✅ Conexão OK - Status: {response.status_code}")
            return True
        except Exception as e:
            logger.error(f"❌ Erro de conexão: {e}")
            return False


# Teste rápido
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    scraper = FIFA25Scraper()
    
    print("\n🔍 Testando conexão...")
    if scraper.test_connection():
        print("✅ Conexão OK\n")
        
        print("🔍 Buscando partidas ao vivo...")
        live = scraper.get_live_matches()
        print(f"✅ {len(live)} partidas ao vivo encontradas\n")
        
        print("🔍 Buscando partidas recentes...")
        recent = scraper.get_recent_matches()
        print(f"✅ {len(recent)} partidas recentes encontradas\n")
        
        if live or recent:
            print("\n📋 Exemplo de partida:")
            example = live[0] if live else recent[0]
            for key, value in example.items():
                print(f"  {key}: {value}")
    else:
        print("❌ Falha na conexão")