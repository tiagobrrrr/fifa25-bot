# web_scraper.py - ARQUIVO COMPLETO CORRIGIDO
"""
Scraper completo para FIFA25 ESportsBattle
Inclui detecção de partidas finalizadas e coleta de resultados
"""

import requests
from bs4 import BeautifulSoup
import logging
from datetime import datetime, timedelta
import re
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FIFA25Scraper:
    """Classe para fazer scraping do site football.esportsbattle.com"""
    
    def __init__(self):
        self.base_url = "https://football.esportsbattle.com"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def get_upcoming_matches(self):
        """
        Coleta partidas agendadas (próximas)
        
        Returns:
            list: lista de dicts com dados das partidas
        """
        try:
            url = f"{self.base_url}/upcoming"
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            matches = []
            
            # Ajustar seletores conforme HTML real do site
            match_cards = soup.find_all('div', class_=re.compile(r'match|game', re.I))
            
            for card in match_cards:
                try:
                    match_data = self._parse_match_card(card, status='scheduled')
                    if match_data:
                        matches.append(match_data)
                except Exception as e:
                    logger.error(f"Erro ao processar card de partida: {e}")
                    continue
            
            logger.info(f"📊 {len(matches)} partidas próximas encontradas")
            return matches
            
        except Exception as e:
            logger.error(f"Erro ao buscar partidas agendadas: {e}")
            return []
    
    def get_live_matches(self):
        """
        Coleta partidas ao vivo
        
        Returns:
            list: lista de dicts com dados das partidas
        """
        try:
            url = f"{self.base_url}/live"
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            matches = []
            
            match_cards = soup.find_all('div', class_=re.compile(r'match|game', re.I))
            
            for card in match_cards:
                try:
                    match_data = self._parse_match_card(card, status='live')
                    if match_data:
                        matches.append(match_data)
                except Exception as e:
                    logger.error(f"Erro ao processar card de partida ao vivo: {e}")
                    continue
            
            logger.info(f"📺 {len(matches)} partidas ao vivo encontradas")
            return matches
            
        except Exception as e:
            logger.error(f"Erro ao buscar partidas ao vivo: {e}")
            return []
    
    def _parse_match_card(self, card, status='scheduled'):
        """
        Extrai dados de um card de partida
        
        Args:
            card: elemento BeautifulSoup do card
            status: status inicial da partida
            
        Returns:
            dict com dados da partida
        """
        match_data = {
            'match_id': None,
            'home_player': None,
            'away_player': None,
            'home_team': None,
            'away_team': None,
            'tournament': None,
            'location': None,
            'match_date': None,
            'status': status,
            'stream_url': None,
            'url': None
        }
        
        # Extrair dados (ajustar seletores conforme HTML real)
        try:
            # Match ID
            match_id_elem = card.find(text=re.compile(r'Match #\d+', re.I))
            if match_id_elem:
                match_id = re.search(r'#(\d+)', match_id_elem).group(1)
                match_data['match_id'] = match_id
                match_data['url'] = f"{self.base_url}/match/{match_id}"
            
            # Jogadores
            players = card.find_all(text=True)
            # Lógica para extrair nomes dos jogadores
            # Ajustar conforme estrutura real
            
            # Times
            teams = card.find_all('img', alt=True)
            if len(teams) >= 2:
                match_data['home_team'] = teams[0].get('alt')
                match_data['away_team'] = teams[1].get('alt')
            
            # Torneio
            tournament_elem = card.find(text=re.compile(r'Champions|International|Liga', re.I))
            if tournament_elem:
                match_data['tournament'] = tournament_elem.strip()
            
            # Local/Estádio
            location_elem = card.find(text=re.compile(r'Anfield|Hillsborough|Old Trafford|Wembley|Etihad', re.I))
            if location_elem:
                match_data['location'] = location_elem.strip()
            
            return match_data
            
        except Exception as e:
            logger.error(f"Erro ao parsear card: {e}")
            return None
    
    def check_match_status_and_score(self, match_url):
        """
        Verifica status atual da partida e coleta placar se finalizada
        
        Args:
            match_url: URL da partida
            
        Returns:
            dict: {
                'status': 'scheduled' | 'live' | 'finished',
                'home_score': int,
                'away_score': int,
                'winner': str ou None,
                'finished_at': datetime ou None
            }
        """
        try:
            response = self.session.get(match_url, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Detecta status
            status = self._detect_match_status(soup)
            
            # Coleta placar
            score = self._extract_final_score(soup)
            
            # Determina vencedor se partida finalizada
            winner = None
            if status == 'finished' and score:
                winner = self._determine_winner(score, soup)
            
            result = {
                'status': status,
                'home_score': score.get('home', 0) if score else 0,
                'away_score': score.get('away', 0) if score else 0,
                'winner': winner,
                'finished_at': datetime.utcnow() if status == 'finished' else None
            }
            
            logger.info(f"✅ Status da partida: {status} | Placar: "
                       f"{result['home_score']} x {result['away_score']}")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Erro ao verificar status da partida {match_url}: {e}")
            return None
    
    def _detect_match_status(self, soup):
        """
        Detecta se partida está agendada, ao vivo ou finalizada
        
        Estratégias de detecção:
        1. Procurar por badge "FINALIZADA" / "FINISHED" / "FT"
        2. Procurar por badge "AO VIVO" / "LIVE"
        3. Verificar se há placar definitivo
        4. Verificar timestamp da partida
        """
        
        # Estratégia 1: Badge de status
        status_badges = soup.find_all(['span', 'div'], class_=re.compile(r'badge|status|label', re.I))
        
        for badge in status_badges:
            text = badge.get_text().strip().lower()
            
            # Partida finalizada
            if any(keyword in text for keyword in ['finalizada', 'finished', 'final', 'ft', 'fim', 'encerrada', 'terminada']):
                return 'finished'
            
            # Partida ao vivo
            if any(keyword in text for keyword in ['ao vivo', 'live', 'em jogo', 'playing', 'em andamento']):
                return 'live'
        
        # Estratégia 2: Verificar se há indicador de "Full Time"
        ft_indicator = soup.find(text=re.compile(r'FT|Full Time|Finalizado|Encerrado', re.I))
        if ft_indicator:
            return 'finished'
        
        # Estratégia 3: Verificar classe do container principal
        match_container = soup.find('div', class_=re.compile(r'match-container|match-card|match-wrapper', re.I))
        if match_container:
            classes = ' '.join(match_container.get('class', []))
            
            if 'finished' in classes.lower() or 'ended' in classes.lower() or 'final' in classes.lower():
                return 'finished'
            
            if 'live' in classes.lower() or 'playing' in classes.lower() or 'ongoing' in classes.lower():
                return 'live'
        
        # Estratégia 4: Verificar se há cronômetro/minuto
        # Se tem minuto (ex: "67'"), está ao vivo
        minute_elem = soup.find(text=re.compile(r"\d{1,3}'"))
        if minute_elem:
            minute_text = minute_elem.strip()
            minute = int(re.search(r'\d+', minute_text).group())
            
            # Se passou de 90 minutos, provavelmente finalizou
            if minute >= 90:
                # Verificar se ainda está atualizando
                live_badge = soup.find(text=re.compile(r'ao vivo|live', re.I))
                if not live_badge:
                    return 'finished'
            
            return 'live'
        
        # Estratégia 5: Se tem placar mas não está ao vivo, está finalizada
        score_elem = soup.find('div', class_=re.compile(r'score|result', re.I))
        live_elem = soup.find(text=re.compile(r'ao vivo|live', re.I))
        
        if score_elem and not live_elem:
            score_text = score_elem.get_text().strip()
            # Se tem placar tipo "2 - 1", provavelmente finalizou
            if re.search(r'\d+\s*[-:x]\s*\d+', score_text):
                return 'finished'
        
        # Estratégia 6: Verificar meta tag
        status_meta = soup.find('meta', attrs={'name': 'match-status'})
        if status_meta:
            meta_content = status_meta.get('content', '').lower()
            if 'finished' in meta_content or 'ended' in meta_content:
                return 'finished'
            if 'live' in meta_content:
                return 'live'
        
        # Default: se não detectou nada, considera agendada
        return 'scheduled'
    
    def _extract_final_score(self, soup):
        """
        Extrai placar final da partida
        
        Procura por diferentes estruturas HTML:
        - <span class="score">2</span> <span class="score">1</span>
        - <div class="home-score">2</div> <div class="away-score">1</div>
        - <div class="score">2 - 1</div>
        """
        
        # Estratégia 1: Scores separados por classe home/away
        home_score_elem = soup.find(['span', 'div'], class_=re.compile(r'home.*score|score.*home', re.I))
        away_score_elem = soup.find(['span', 'div'], class_=re.compile(r'away.*score|score.*away', re.I))
        
        if home_score_elem and away_score_elem:
            try:
                home_text = home_score_elem.get_text().strip()
                away_text = away_score_elem.get_text().strip()
                
                home_score = int(re.search(r'\d+', home_text).group())
                away_score = int(re.search(r'\d+', away_text).group())
                
                return {'home': home_score, 'away': away_score}
            except:
                pass
        
        # Estratégia 2: Score combinado (ex: "2 - 1")
        score_container = soup.find(['div', 'span'], class_=re.compile(r'score|result|final', re.I))
        if score_container:
            score_text = score_container.get_text().strip()
            match = re.search(r'(\d+)\s*[-:x]\s*(\d+)', score_text)
            if match:
                return {'home': int(match.group(1)), 'away': int(match.group(2))}
        
        # Estratégia 3: Procurar em todo o HTML por padrão "X - Y"
        full_text = soup.get_text()
        score_pattern = re.search(r'(\d+)\s*[-:]\s*(\d+)', full_text)
        if score_pattern:
            home_score = int(score_pattern.group(1))
            away_score = int(score_pattern.group(2))
            
            # Valida se são placares razoáveis (0-20)
            if 0 <= home_score <= 20 and 0 <= away_score <= 20:
                return {'home': home_score, 'away': away_score}
        
        # Estratégia 4: Buscar na estrutura de times
        team_containers = soup.find_all(['div', 'section'], class_=re.compile(r'team', re.I))
        if len(team_containers) >= 2:
            scores = []
            for container in team_containers[:2]:
                score_elem = container.find(text=re.compile(r'^\d+$'))
                if score_elem:
                    score_num = int(score_elem.strip())
                    if 0 <= score_num <= 20:
                        scores.append(score_num)
            
            if len(scores) == 2:
                return {'home': scores[0], 'away': scores[1]}
        
        logger.warning("⚠️ Não foi possível extrair placar da partida")
        return None
    
    def _determine_winner(self, score, soup):
        """
        Determina o vencedor da partida
        
        Args:
            score: dict com 'home' e 'away'
            soup: BeautifulSoup object para extrair nomes dos jogadores
            
        Returns:
            str: nome do jogador vencedor, 'Empate', ou None
        """
        if not score:
            return None
        
        home_score = score['home']
        away_score = score['away']
        
        # Extrai nomes dos jogadores
        player_names = self._extract_player_names(soup)
        
        if home_score > away_score:
            return player_names.get('home', 'Home')
        elif away_score > home_score:
            return player_names.get('away', 'Away')
        else:
            return 'Empate'
    
    def _extract_player_names(self, soup):
        """
        Extrai nomes dos jogadores da partida
        
        Returns:
            dict: {'home': 'NomeJogador1', 'away': 'NomeJogador2'}
        """
        players = {'home': None, 'away': None}
        
        # Estratégia 1: Procurar por elementos com classe player/jogador
        home_player = soup.find(['span', 'div', 'p'], class_=re.compile(r'home.*player|player.*home|player.*1', re.I))
        away_player = soup.find(['span', 'div', 'p'], class_=re.compile(r'away.*player|player.*away|player.*2', re.I))
        
        if home_player:
            players['home'] = home_player.get_text().strip()
        if away_player:
            players['away'] = away_player.get_text().strip()
        
        # Estratégia 2: Procurar na estrutura de times
        if not players['home'] or not players['away']:
            team_containers = soup.find_all(['div', 'section'], class_=re.compile(r'team', re.I))
            if len(team_containers) >= 2:
                for idx, container in enumerate(team_containers[:2]):
                    player_elem = container.find(['span', 'div', 'p'], class_=re.compile(r'player|name|username', re.I))
                    if player_elem:
                        key = 'home' if idx == 0 else 'away'
                        if not players[key]:
                            players[key] = player_elem.get_text().strip()
        
        # Estratégia 3: Buscar por data attributes
        if not players['home']:
            home_elem = soup.find(attrs={'data-player': '1'}) or soup.find(attrs={'data-home-player': True})
            if home_elem:
                players['home'] = home_elem.get_text().strip()
        
        if not players['away']:
            away_elem = soup.find(attrs={'data-player': '2'}) or soup.find(attrs={'data-away-player': True})
            if away_elem:
                players['away'] = away_elem.get_text().strip()
        
        return players
    
    def get_all_live_matches_urls(self):
        """
        Coleta URLs de todas as partidas marcadas como 'live' no banco
        para verificar se finalizaram
        """
        from models import Match
        
        try:
            # Busca partidas com status 'live'
            live_matches = Match.query.filter_by(status='live').all()
            
            logger.info(f"🔍 Encontradas {len(live_matches)} partidas ao vivo no banco")
            
            return [(match.match_id, match.url) for match in live_matches]
            
        except Exception as e:
            logger.error(f"Erro ao buscar partidas ao vivo: {e}")
            return []


# ============================================================
# FUNÇÃO DE TESTE
# ============================================================

def test_match_status_detection(match_url):
    """
    Testa a detecção de status e placar de uma partida
    
    Usage:
        python -c "from web_scraper import test_match_status_detection; 
                   test_match_status_detection('https://football.esportsbattle.com/match/1930522')"
    """
    print("\n" + "="*60)
    print("🧪 TESTANDO DETECÇÃO DE STATUS E PLACAR")
    print("="*60)
    print(f"URL: {match_url}\n")
    
    scraper = FIFA25Scraper()
    result = scraper.check_match_status_and_score(match_url)
    
    if result:
        print(f"✅ RESULTADO DO TESTE:")
        print(f"   Status: {result['status']}")
        print(f"   Placar: {result['home_score']} x {result['away_score']}")
        print(f"   Vencedor: {result['winner']}")
        print(f"   Finalizada em: {result['finished_at']}")
    else:
        print("\n❌ FALHA NO TESTE")
    
    print("\n" + "="*60)


if __name__ == '__main__':
    # Teste rápido
    import sys
    
    if len(sys.argv) > 1:
        test_match_status_detection(sys.argv[1])
    else:
        print("Usage: python web_scraper.py <match_url>")
        print("Example: python web_scraper.py https://football.esportsbattle.com/match/1930522")
