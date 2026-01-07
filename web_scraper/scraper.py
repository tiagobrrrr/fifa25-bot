import requests
import logging
from datetime import datetime
from typing import List, Dict, Any

logger = logging.getLogger('FIFA25Scraper')


class FIFA25Scraper:
    """
    Scraper para coletar dados de partidas FIFA 25
    usando múltiplas APIs do ESportsBattle
    """
    
    def __init__(self):
        self.base_url = "https://football.esportsbattle.com"
        
        # APIs disponíveis
        self.api_endpoints = {
            'streaming': f"{self.base_url}/api/locations/streaming",
            'location_stream': f"{self.base_url}/api/locations/1/streaming",
            'nearest_matches': f"{self.base_url}/api/tournaments/nearest-matches",
            'tournament_results': f"{self.base_url}/api/tournaments/{{id}}/results"
        }
        
        self.headers = {
            'Accept': '*/*',
            'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36',
            'Referer': f'{self.base_url}/en/',
            'Origin': self.base_url,
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin'
        }
        
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        
        logger.info("✅ FIFA25Scraper inicializado com múltiplas APIs")
    
    def get_live_matches(self) -> List[Dict[str, Any]]:
        """
        Coleta partidas ao vivo de múltiplas fontes
        """
        all_matches = []
        
        try:
            # Fonte 1: Próximas partidas (geralmente inclui ao vivo)
            logger.info(f"🔍 API 1: Buscando nearest-matches")
            nearest = self._fetch_nearest_matches()
            all_matches.extend(nearest)
            
            # Fonte 2: Streaming locations
            logger.info(f"🔍 API 2: Buscando streaming locations")
            streaming = self._fetch_streaming_locations()
            all_matches.extend(streaming)
            
            # Remover duplicatas
            unique_matches = self._remove_duplicates(all_matches)
            
            logger.info(f"✅ {len(unique_matches)} partidas ao vivo coletadas")
            return unique_matches
            
        except Exception as e:
            logger.error(f"❌ Erro ao buscar partidas ao vivo: {e}")
            return []
    
    def get_recent_matches(self, limit=20) -> List[Dict[str, Any]]:
        """
        Coleta partidas recentes/finalizadas
        """
        try:
            logger.info(f"🔍 Buscando partidas recentes")
            
            # Usar API de nearest matches que pode ter finalizadas também
            matches = self._fetch_nearest_matches()
            
            # Filtrar apenas finalizadas
            finished = [m for m in matches if m.get('status') in ['finished', 'completed']]
            
            logger.info(f"✅ {len(finished)} partidas recentes coletadas")
            return finished[:limit]
            
        except Exception as e:
            logger.error(f"❌ Erro ao buscar partidas recentes: {e}")
            return []
    
    def _fetch_nearest_matches(self) -> List[Dict[str, Any]]:
        """
        Busca na API de próximas partidas
        """
        try:
            url = self.api_endpoints['nearest_matches']
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            
            data = response.json()
            return self._parse_nearest_matches(data)
            
        except Exception as e:
            logger.error(f"❌ Erro na API nearest-matches: {e}")
            return []
    
    def _fetch_streaming_locations(self) -> List[Dict[str, Any]]:
        """
        Busca na API de streaming locations
        """
        try:
            url = self.api_endpoints['streaming']
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            
            data = response.json()
            return self._parse_streaming_data(data)
            
        except Exception as e:
            logger.error(f"❌ Erro na API streaming: {e}")
            return []
    
    def _parse_nearest_matches(self, data: Any) -> List[Dict[str, Any]]:
        """
        Parse da API nearest-matches
        """
        matches = []
        
        try:
            if isinstance(data, list):
                for item in data:
                    match = self._extract_match_from_tournament(item)
                    if match:
                        matches.append(match)
            
            elif isinstance(data, dict):
                # Pode ter múltiplas chaves
                for key in ['matches', 'tournaments', 'games', 'data']:
                    if key in data and isinstance(data[key], list):
                        for item in data[key]:
                            match = self._extract_match_from_tournament(item)
                            if match:
                                matches.append(match)
        
        except Exception as e:
            logger.error(f"❌ Parse error nearest-matches: {e}")
        
        return matches
    
    def _parse_streaming_data(self, data: Any) -> List[Dict[str, Any]]:
        """
        Parse da API streaming
        """
        matches = []
        
        try:
            if isinstance(data, list):
                for stream in data:
                    match = self._extract_match_from_stream(stream)
                    if match:
                        matches.append(match)
        
        except Exception as e:
            logger.error(f"❌ Parse error streaming: {e}")
        
        return matches
    
    def _extract_match_from_tournament(self, item: Dict) -> Dict[str, Any]:
        """
        Extrai partida de dados de torneio
        """
        try:
            match_data = {
                'scraped_at': datetime.utcnow(),
                'status': 'live'
            }
            
            # Extrair do torneio/match
            match_data['tournament'] = item.get('token') or item.get('token_international') or 'FIFA 25'
            
            # Se tem "results", são os participantes/jogadores
            if 'results' in item or 'resultados' in item:
                results = item.get('results') or item.get('resultados', [])
                
                if len(results) >= 2:
                    # Jogador 1
                    p1 = results[0]
                    if 'participant' in p1 or 'participante' in p1:
                        participant1 = p1.get('participant') or p1.get('participante', {})
                        match_data['player1'] = participant1.get('nickname') or participant1.get('apelido', 'Jogador 1')
                        
                        team1 = participant1.get('team') or participant1.get('equipe', {})
                        match_data['team1'] = team1.get('token') or team1.get('token_international', 'Time 1')
                    
                    # Jogador 2
                    p2 = results[1]
                    if 'participant' in p2 or 'participante' in p2:
                        participant2 = p2.get('participant') or p2.get('participante', {})
                        match_data['player2'] = participant2.get('nickname') or participant2.get('apelido', 'Jogador 2')
                        
                        team2 = participant2.get('team') or participant2.get('equipe', {})
                        match_data['team2'] = team2.get('token') or team2.get('token_international', 'Time 2')
                    
                    # Extrair placar dos details
                    details1 = p1.get('details') or p1.get('detalhes', {})
                    details2 = p2.get('details') or p2.get('detalhes', {})
                    
                    gf1 = details1.get('GF', 0)
                    gf2 = details2.get('GF', 0)
                    match_data['score'] = f"{gf1}-{gf2}"
            
            # Extrair horário/data
            match_data['match_time'] = item.get('time') or item.get('startTime') or datetime.now().strftime('%H:%M')
            match_data['location'] = item.get('location') or 'Online'
            
            # Verificar se tem dados mínimos
            if 'team1' in match_data and 'team2' in match_data:
                return match_data
            
            return None
            
        except Exception as e:
            logger.debug(f"Erro ao extrair torneio: {e}")
            return None
    
    def _extract_match_from_stream(self, stream: Dict) -> Dict[str, Any]:
        """
        Extrai partida de dados de stream
        """
        try:
            match_data = {
                'scraped_at': datetime.utcnow(),
                'status': 'live'
            }
            
            # Extrair informações básicas
            match_data['location'] = stream.get('name') or stream.get('location', 'Online')
            match_data['tournament'] = stream.get('tournament') or 'FIFA 25'
            
            # Se tem "match" dentro
            if 'match' in stream:
                match = stream['match']
                match_data.update(self._extract_basic_match_data(match))
            else:
                match_data.update(self._extract_basic_match_data(stream))
            
            if 'team1' in match_data and 'team2' in match_data:
                return match_data
            
            return None
            
        except Exception as e:
            logger.debug(f"Erro ao extrair stream: {e}")
            return None
    
    def _extract_basic_match_data(self, data: Dict) -> Dict[str, Any]:
        """
        Extração genérica de dados de partida
        """
        result = {}
        
        # Times
        result['team1'] = (
            data.get('team1') or 
            data.get('homeTeam') or 
            data.get('home_team') or
            'Time 1'
        )
        
        result['team2'] = (
            data.get('team2') or 
            data.get('awayTeam') or 
            data.get('away_team') or
            'Time 2'
        )
        
        # Jogadores
        result['player1'] = (
            data.get('player1') or 
            data.get('homePlayer') or 
            'Jogador 1'
        )
        
        result['player2'] = (
            data.get('player2') or 
            data.get('awayPlayer') or 
            'Jogador 2'
        )
        
        # Placar
        score1 = data.get('score1', data.get('homeScore', 0))
        score2 = data.get('score2', data.get('awayScore', 0))
        result['score'] = f"{score1}-{score2}"
        
        # Outros
        result['tournament'] = data.get('tournament', 'FIFA 25')
        result['match_time'] = data.get('time', datetime.now().strftime('%H:%M'))
        result['location'] = data.get('location', 'Online')
        
        return result
    
    def _remove_duplicates(self, matches: List[Dict]) -> List[Dict]:
        """
        Remove partidas duplicadas baseado em time1, time2, player1, player2
        """
        seen = set()
        unique = []
        
        for match in matches:
            key = (
                match.get('team1', ''),
                match.get('team2', ''),
                match.get('player1', ''),
                match.get('player2', '')
            )
            
            if key not in seen:
                seen.add(key)
                unique.append(match)
        
        return unique
    
    def test_connection(self) -> bool:
        """
        Testa as APIs disponíveis
        """
        try:
            logger.info("🔍 Testando APIs...")
            
            # Teste 1: Nearest matches
            url1 = self.api_endpoints['nearest_matches']
            r1 = self.session.get(url1, timeout=10)
            logger.info(f"  ✅ nearest-matches: {r1.status_code} ({len(r1.text)} bytes)")
            
            # Teste 2: Streaming
            url2 = self.api_endpoints['streaming']
            r2 = self.session.get(url2, timeout=10)
            logger.info(f"  ✅ streaming: {r2.status_code} ({len(r2.text)} bytes)")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro de conexão: {e}")
            return False


# Teste
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    scraper = FIFA25Scraper()
    
    print("\n🔍 Testando APIs...")
    if scraper.test_connection():
        print("\n✅ Conexão OK\n")
        
        print("🔍 Buscando partidas ao vivo...")
        live = scraper.get_live_matches()
        print(f"✅ {len(live)} partidas encontradas\n")
        
        if live:
            print("\n📋 Exemplo de partida:")
            for key, value in live[0].items():
                print(f"  {key}: {value}")
    else:
        print("❌ Falha na conexão")