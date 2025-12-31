"""
Web Scraper para ESportsBattle Football
Versão com logs detalhados e tratamento de erros
"""

import requests
from bs4 import BeautifulSoup
import logging
from datetime import datetime
import time
import random

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class FIFA25Scraper:
    """Scraper para coletar dados de partidas FIFA 25"""
    
    def __init__(self):
        self.base_url = "https://football.esportsbattle.com/en/"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        self.session = requests.Session()
        logger.info("✅ FIFA25Scraper inicializado")
    
    def _get_page(self, url=None, retries=3):
        """Faz requisição HTTP com retry"""
        if url is None:
            url = self.base_url
        
        for attempt in range(retries):
            try:
                logger.info(f"🌐 Acessando {url} (tentativa {attempt + 1}/{retries})")
                
                response = self.session.get(
                    url, 
                    headers=self.headers, 
                    timeout=15
                )
                
                if response.status_code == 200:
                    logger.info(f"✅ Status 200 - {len(response.content)} bytes recebidos")
                    return response
                else:
                    logger.warning(f"⚠️ Status {response.status_code}")
                    
            except requests.exceptions.Timeout:
                logger.error(f"⏱️ Timeout na tentativa {attempt + 1}")
            except requests.exceptions.ConnectionError:
                logger.error(f"🔌 Erro de conexão na tentativa {attempt + 1}")
            except Exception as e:
                logger.error(f"❌ Erro inesperado: {type(e).__name__}: {e}")
            
            # Aguardar antes de tentar novamente
            if attempt < retries - 1:
                wait_time = random.uniform(2, 5)
                logger.info(f"⏳ Aguardando {wait_time:.1f}s antes de nova tentativa...")
                time.sleep(wait_time)
        
        logger.error(f"❌ Falha após {retries} tentativas")
        return None
    
    def get_live_matches(self):
        """Coleta partidas ao vivo"""
        logger.info("🎮 Iniciando coleta de partidas AO VIVO...")
        
        response = self._get_page()
        if not response:
            logger.error("❌ Não foi possível obter a página")
            return []
        
        soup = BeautifulSoup(response.content, 'html.parser')
        matches = []
        
        # Buscar container de partidas ao vivo
        live_section = soup.find('section', class_='online-matches-section')
        
        if not live_section:
            logger.warning("⚠️ Seção de partidas ao vivo não encontrada!")
            return []
        
        # Buscar cada partida individual
        match_divs = live_section.find_all('div', class_='online-matches-match')
        logger.info(f"📊 Encontrados {len(match_divs)} containers de partida")
        
        for i, match_div in enumerate(match_divs, 1):
            try:
                match_data = self._parse_live_match(match_div)
                if match_data:
                    matches.append(match_data)
                    logger.info(f"✅ Partida {i} coletada: {match_data['team1']} vs {match_data['team2']}")
                else:
                    logger.warning(f"⚠️ Partida {i} sem dados válidos")
                    
            except Exception as e:
                logger.error(f"❌ Erro ao processar partida {i}: {e}")
                continue
        
        logger.info(f"🎯 Total coletado: {len(matches)} partidas ao vivo")
        return matches
    
    def _parse_live_match(self, match_div):
        """Extrai dados de uma partida ao vivo"""
        try:
            # Buscar informações da partida
            stats_div = match_div.find('div', class_='online-matches-match-stats')
            
            if not stats_div:
                return None
            
            # Buscar os dois times/jogadores
            stats_items = stats_div.find_all('div', class_='online-matches-stats-item', limit=2)
            
            if len(stats_items) < 2:
                logger.warning("⚠️ Menos de 2 times encontrados")
                return None
            
            # Time 1
            team1_div = stats_items[0].find('div', class_='subcaption-1')
            player1_link = stats_items[0].find('a', class_='text-link')
            score1_span = stats_items[0].find('span', class_='online-matches-stats-item-score')
            
            # Time 2
            team2_div = stats_items[1].find('div', class_='subcaption-1')
            player2_link = stats_items[1].find('a', class_='text-link')
            score2_span = stats_items[1].find('span', class_='online-matches-stats-item-score')
            
            # Extrair textos
            team1 = team1_div.get_text(strip=True) if team1_div else "N/A"
            player1 = player1_link.get_text(strip=True) if player1_link else "N/A"
            score1 = score1_span.get_text(strip=True) if score1_span else "0"
            
            team2 = team2_div.get_text(strip=True) if team2_div else "N/A"
            player2 = player2_link.get_text(strip=True) if player2_link else "N/A"
            score2 = score2_span.get_text(strip=True) if score2_span else "0"
            
            # Buscar informações adicionais (console, horário)
            console_div = match_div.find('div', class_='online-matches-console-details')
            tournament = ""
            match_time = ""
            
            if console_div:
                tournament_div = console_div.find('div', class_='subcaption-2')
                time_span = console_div.find('span', class_='subcaption-1')
                
                tournament = tournament_div.get_text(strip=True) if tournament_div else ""
                match_time = time_span.get_text(strip=True) if time_span else ""
            
            match_data = {
                'team1': team1,
                'team2': team2,
                'player1': player1,
                'player2': player2,
                'score1': int(score1) if score1.isdigit() else 0,
                'score2': int(score2) if score2.isdigit() else 0,
                'tournament': tournament,
                'match_time': match_time,
                'status': 'live',
                'scraped_at': datetime.now()
            }
            
            return match_data
            
        except Exception as e:
            logger.error(f"❌ Erro no parse: {e}")
            return None
    
    def get_recent_matches(self):
        """Coleta próximas partidas"""
        logger.info("📅 Iniciando coleta de PRÓXIMAS partidas...")
        
        response = self._get_page()
        if not response:
            return []
        
        soup = BeautifulSoup(response.content, 'html.parser')
        matches = []
        
        # Buscar lista de próximas partidas
        recent_section = soup.find('section', class_='nearest-matches')
        
        if not recent_section:
            logger.warning("⚠️ Seção de próximas partidas não encontrada!")
            return []
        
        match_items = recent_section.find_all('li', class_='nearest-matches-list-item')
        logger.info(f"📊 Encontrados {len(match_items)} itens de próximas partidas")
        
        for i, item in enumerate(match_items, 1):
            try:
                match_data = self._parse_recent_match(item)
                if match_data:
                    matches.append(match_data)
                    logger.debug(f"✅ Próxima partida {i} coletada")
                    
            except Exception as e:
                logger.error(f"❌ Erro ao processar próxima partida {i}: {e}")
                continue
        
        logger.info(f"🎯 Total coletado: {len(matches)} próximas partidas")
        return matches
    
    def _parse_recent_match(self, item):
        """Extrai dados de uma próxima partida"""
        try:
            # Buscar horário
            date_span = item.find('span', class_='subcaption-1')
            match_time = date_span.get_text(strip=True) if date_span else ""
            
            # Buscar confronto
            teams_div = item.find('div', class_='subcaption-2')
            confronto = teams_div.get_text(strip=True) if teams_div else ""
            
            # Tentar separar os times
            if ' x ' in confronto or ' - ' in confronto:
                parts = confronto.replace(' x ', '|').replace(' - ', '|').split('|')
                if len(parts) == 2:
                    team1_full = parts[0].strip()
                    team2_full = parts[1].strip()
                else:
                    team1_full = confronto
                    team2_full = ""
            else:
                team1_full = confronto
                team2_full = ""
            
            match_data = {
                'team1': team1_full,
                'team2': team2_full,
                'match_time': match_time,
                'status': 'scheduled',
                'scraped_at': datetime.now()
            }
            
            return match_data
            
        except Exception as e:
            logger.error(f"❌ Erro no parse de próxima partida: {e}")
            return None
    
    def get_tournament_results(self, tournament_url=None):
        """Coleta resultados de um torneio específico"""
        logger.info("🏆 Iniciando coleta de resultados do torneio...")
        
        # Implementar conforme necessário
        return []

# Função auxiliar para testes rápidos
def quick_test():
    """Teste rápido do scraper"""
    scraper = FIFA25Scraper()
    
    print("\n" + "="*60)
    print("🎮 TESTE RÁPIDO DO SCRAPER")
    print("="*60)
    
    # Testar partidas ao vivo
    print("\n📺 PARTIDAS AO VIVO:")
    live = scraper.get_live_matches()
    for i, match in enumerate(live, 1):
        print(f"\n{i}. {match['team1']} ({match['player1']}) {match['score1']} x {match['score2']} {match['team2']} ({match['player2']})")
        print(f"   🏆 {match['tournament']}")
        print(f"   🕐 {match['match_time']}")
    
    # Testar próximas partidas
    print("\n\n📅 PRÓXIMAS PARTIDAS:")
    recent = scraper.get_recent_matches()
    for i, match in enumerate(recent[:5], 1):
        print(f"\n{i}. {match['team1']} vs {match['team2']}")
        print(f"   🕐 {match['match_time']}")
    
    print("\n" + "="*60)
    print(f"✅ Teste concluído: {len(live)} ao vivo, {len(recent)} agendadas")
    print("="*60)

if __name__ == "__main__":
    quick_test()