import requests
import logging
from datetime import datetime
from typing import List, Dict, Any
import json

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
            # Fonte 1: Próximas partidas
            logger.info(f"🔍 API 1: Buscando nearest-matches")
            nearest = self._fetch_nearest_matches()
            logger.info(f"📊 API 1 retornou {len(nearest)} partidas")
            all_matches.extend(nearest)
            
            # Fonte 2: Streaming locations
            logger.info(f"🔍 API 2: Buscando streaming locations")
            streaming = self._fetch_streaming_locations()
            logger.info(f"📊 API 2 retornou {len(streaming)} partidas")
            all_matches.extend(streaming)
            
            # Remover duplicatas
            unique_matches = self._remove_duplicates(all_matches)
            
            logger.info(f"✅ {len(unique_matches)} partidas ao vivo coletadas (após remover duplicatas)")
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
            
            # Usar API de nearest matches
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
            
            # 🔍 DEBUG: Mostrar estrutura da resposta
            logger.info(f"🔎 DEBUG - Tipo da resposta: {type(data).__name__}")
            if isinstance(data, list):
                logger.info(f"🔎 DEBUG - Lista com {len(data)} items")
                if len(data) > 0:
                    logger.info(f"🔎 DEBUG - Primeira entrada: {json.dumps(data[0], indent=2)[:500]}")
            elif isinstance(data, dict):
                logger.info(f"🔎 DEBUG - Dict com chaves: {list(data.keys())}")
                
            matches = self._parse_nearest_matches(data)
            logger.info(f"📊 Parse nearest-matches: {len(matches)} partidas extraídas")
            return matches
            
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
            
            # 🔍 DEBUG: Mostrar estrutura
            logger.info(f"🔎 DEBUG - Streaming tipo: {type(data).__name__}")
            if isinstance(data, list):
                logger.info(f"🔎 DEBUG - Streaming lista: {len(data)} items")
            
            matches = self._parse_streaming_data(data)
            logger.info(f"📊 Parse streaming: {len(matches)} partidas extraídas")
            return matches
            
        except Exception as e:
            logger.error(f"❌ Erro na API streaming: {e}")
            return []
    
    def _parse_nearest_matches(self, data: Any) -> List[Dict[str, Any]]:
        """
        Parse da API nearest-matches
        """
        matches = []
        
        try:
            # Lista direta
            if isinstance(data, list):
                logger.info(f"🔎 Processando lista com {len(data)} items")
                for idx, item in enumerate(data):
                    logger.info(f"🔎 Item {idx}: tipo={type(item).__name__}, keys={list(item.keys()) if isinstance(item, dict) else 'N/A'}")
                    
                    # Se o item tem "results", é um torneio com participantes
                    if isinstance(item, dict) and ('results' in item or 'resultados' in item):
                        logger.info(f"✅ Item {idx} é um TORNEIO com participantes")
                        match = self._extract_match_from_tournament(item)
                        if match:
                            matches.append(match)
                            logger.info(f"✅ Partida extraída: {match.get('player1')} vs {match.get('player2')}")
                    else:
                        # Tentar como partida direta
                        match = self._extract_basic_match_data(item) if isinstance(item, dict) else None
                        if match and 'team1' in match:
                            matches.append(match)
                            logger.info(f"✅ Partida extraída (básica): {match.get('player1')} vs {match.get('player2')}")
            
            # Dict com listas
            elif isinstance(data, dict):
                logger.info(f"🔎 Processando dict com chaves: {list(data.keys())}")
                for key in ['matches', 'tournaments', 'games', 'data', 'items']:
                    if key in data and isinstance(data[key], list):
                        logger.info(f"🔎 Encontrou chave '{key}' com {len(data[key])} items")
                        for item in data[key]:
                            match = self._extract_match_from_tournament(item)
                            if match:
                                matches.append(match)
        
        except Exception as e:
            logger.error(f"❌ Parse error nearest-matches: {e}")
            import traceback
            logger.error(traceback.format_exc())
        
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
            
            # Torneio
            match_data['tournament'] = item.get('token') or item.get('token_international') or 'FIFA 25'
            
            # Results/Resultados = participantes
            results = item.get('results') or item.get('resultados', [])
            
            if len(results) >= 2:
                # Jogador 1
                p1 = results[0]
                participant1 = p1.get('participant') or p1.get('participante', {})
                match_data['player1'] = participant1.get('nickname') or participant1.get('apelido', 'Jogador 1')
                
                team1 = participant1.get('team') or participant1.get('equipe', {})
                match_data['team1'] = team1.get('token') or team1.get('token_international', 'Time 1')
                
                # Jogador 2
                p2 = results[1]
                participant2 = p2.get('participant') or p2.get('participante', {})
                match_data['player2'] = participant2.get('nickname') or participant2.get('apelido', 'Jogador 2')
                
                team2 = participant2.get('team') or participant2.get('equipe', {})
                match_data['team2'] = team2.get('token') or team2.get('token_international', 'Time 2')
                
                # Placar dos details
                details1 = p1.get('details') or p1.get('detalhes', {})
                details2 = p2.get('details') or p2.get('detalhes', {})
                
                gf1 = details1.get('GF', 0)
                gf2 = details2.get('GF', 0)
                match_data['score'] = f"{gf1}-{gf2}"
            
            # Horário
            match_data['match_time'] = item.get('time') or item.get('date') or datetime.now().strftime('%H:%M')
            if match_data['match_time'] and len(str(match_data['match_time'])) > 10:
                # Se é data completa, extrair só hora
                try:
                    dt = datetime.fromisoformat(str(match_data['match_time']).replace('Z', '+00:00'))
                    match_data['match_time'] = dt.strftime('%H:%M')
                except:
                    match_data['match_time'] = datetime.now().strftime('%H:%M')
            
            # ✅ CORRIGIDO: Location como STRING
            location_data = item.get('location', 'Online')
            if isinstance(location_data, dict):
                match_data['location'] = location_data.get('token') or location_data.get('token_international', 'Online')
            else:
                match_data['location'] = str(location_data) if location_data else 'Online'
            
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
            
            # ✅ CORRIGIDO: Location como STRING
            location_data = stream.get('name') or stream.get('location', 'Online')
            if isinstance(location_data, dict):
                match_data['location'] = location_data.get('token') or location_data.get('token_international', 'Online')
            else:
                match_data['location'] = str(location_data) if location_data else 'Online'
            
            match_data['tournament'] = stream.get('tournament', 'FIFA 25')
            
            if 'match' in stream:
                match_data.update(self._extract_basic_match_data(stream['match']))
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
        
        # ✅ CORRIGIDO: Extrair de participant1/participant2
        p1 = data.get('participant1', {})
        p2 = data.get('participant2', {})
        
        if p1:
            result['player1'] = p1.get('nickname') or p1.get('name', 'Jogador 1')
            team1_data = p1.get('team', {})
            if isinstance(team1_data, dict):
                result['team1'] = team1_data.get('token') or team1_data.get('token_international') or team1_data.get('name', 'Time 1')
            else:
                result['team1'] = 'Time 1'
        else:
            result['team1'] = data.get('team1') or data.get('homeTeam', 'Time 1')
            result['player1'] = data.get('player1') or data.get('homePlayer', 'Jogador 1')
        
        if p2:
            result['player2'] = p2.get('nickname') or p2.get('name', 'Jogador 2')
            team2_data = p2.get('team', {})
            if isinstance(team2_data, dict):
                result['team2'] = team2_data.get('token') or team2_data.get('token_international') or team2_data.get('name', 'Time 2')
            else:
                result['team2'] = 'Time 2'
        else:
            result['team2'] = data.get('team2') or data.get('awayTeam', 'Time 2')
            result['player2'] = data.get('player2') or data.get('awayPlayer', 'Jogador 2')
        
        # Placar
        score1 = data.get('score1', data.get('homeScore', 0))
        score2 = data.get('score2', data.get('awayScore', 0))
        result['score'] = f"{score1}-{score2}"
        
        # Torneio
        result['tournament'] = data.get('tournament', 'FIFA 25')
        
        # Horário
        match_time = data.get('time') or data.get('date') or datetime.now().strftime('%H:%M')
        if match_time and len(str(match_time)) > 10:
            # Se é data completa, extrair só hora
            try:
                dt = datetime.fromisoformat(str(match_time).replace('Z', '+00:00'))
                result['match_time'] = dt.strftime('%H:%M')
            except:
                result['match_time'] = datetime.now().strftime('%H:%M')
        else:
            result['match_time'] = str(match_time) if match_time else datetime.now().strftime('%H:%M')
        
        # ✅ CORRIGIDO: Location como STRING
        location_data = data.get('location', 'Online')
        if isinstance(location_data, dict):
            result['location'] = location_data.get('token') or location_data.get('token_international') or location_data.get('name', 'Online')
        else:
            result['location'] = str(location_data) if location_data else 'Online'
        
        return result
    
    def _remove_duplicates(self, matches: List[Dict]) -> List[Dict]:
        """
        Remove partidas duplicadas
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
            print("\n📋 Partidas encontradas:")
            for i, match in enumerate(live, 1):
                print(f"\n{i}. {match.get('player1')} vs {match.get('player2')}")
                print(f"   Times: {match.get('team1')} vs {match.get('team2')}")
                print(f"   Score: {match.get('score')}")
    else:
        print("❌ Falha na conexão")