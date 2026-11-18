"""
FIFA 25 Web Scraper - ESportsBattle
Scraper atualizado com os novos endpoints da API
"""

import requests
import logging
from datetime import datetime
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class FIFA25Scraper:
    """Scraper para o site ESportsBattle"""
    
    BASE_URL = "https://football.esportsbattle.com"
    
    # Endpoints da API (atualizados)
    ENDPOINTS = {
        'nearest_matches': '/api/tournaments/nearest-matches',
        'streaming_all': '/api/locations/streaming',
        'streaming_location': '/api/locations/{location_id}/streaming',
        'statuses': '/api/statuses',
        'tournament_results': '/api/tournaments/{tournament_id}/results',
    }
    
    # Status das partidas
    STATUS = {
        1: 'Planned',      # Planejada
        2: 'Started',      # Ao vivo
        3: 'Finished',     # Finalizada
        4: 'Canceled'      # Cancelada
    }
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate',
            'Referer': self.BASE_URL + '/',
            'Origin': self.BASE_URL,
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
        })
        logger.info("✅ FIFA25Scraper inicializado")
    
    def _make_request(self, endpoint: str, params: Dict = None) -> Optional[Dict]:
        """Faz uma requisição GET para a API"""
        try:
            url = f"{self.BASE_URL}{endpoint}"
            logger.debug(f"📡 Requisição: {url}")
            
            response = self.session.get(url, params=params, timeout=15)
            if response.status_code == 403:
                server = response.headers.get('Server', '?')
                cf_ray = response.headers.get('CF-RAY')
                snippet = response.text[:200].replace('\n', ' ')
                logger.error(
                    f"🚫 403 em {endpoint} | Server={server} | CF-RAY={cf_ray} | corpo: {snippet}"
                )
            response.raise_for_status()
            
            data = response.json()
            logger.debug(f"✅ Resposta recebida: {type(data)}")
            
            return data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Erro na requisição {endpoint}: {e}")
            return None
        except ValueError as e:
            logger.error(f"❌ Erro ao parsear JSON: {e}")
            return None
    
    def get_nearest_matches(self) -> List[Dict]:
        """
        Busca as próximas partidas (endpoint principal)
        Retorna lista de partidas ordenadas por data
        """
        try:
            data = self._make_request(self.ENDPOINTS['nearest_matches'])
            
            if not data or not isinstance(data, list):
                logger.warning("⚠️ Nenhuma partida próxima encontrada")
                return []
            
            logger.info(f"📊 {len(data)} partidas próximas encontradas")
            return data
            
        except Exception as e:
            logger.error(f"❌ Erro ao buscar nearest matches: {e}")
            return []
    
    def get_streaming_matches(self) -> List[Dict]:
        """
        Busca todas as partidas em streaming COM PLACARES
        Retorna lista de partidas de todas as locations
        """
        try:
            # Primeiro busca todas as locations com streaming
            locations = self._make_request(self.ENDPOINTS['streaming_all'])
            
            if not locations or not isinstance(locations, list):
                logger.warning("⚠️ Nenhuma location em streaming")
                return []
            
            logger.info(f"📺 {len(locations)} locations em streaming")
            
            all_matches = []
            tournament_ids_processed = set()
            
            # Para cada location, buscar as partidas
            for location in locations:
                location_id = location.get('id')
                match_count = location.get('matchCount', 0)
                
                if match_count > 0:
                    logger.debug(f"🔍 Buscando {match_count} partidas da location {location_id}")
                    
                    location_data = self._make_request(
                        self.ENDPOINTS['streaming_location'].format(location_id=location_id)
                    )
                    
                    if location_data and isinstance(location_data, list):
                        # Extrair partidas dos torneios
                        for tournament in location_data:
                            tournament_id = tournament.get('id')
                            tournament_status = tournament.get('status_id')
                            matches = tournament.get('matches', [])
                            
                            # Se o torneio está finalizado (status_id=3 ou 4), buscar resultados
                            if tournament_status in [3, 4] and tournament_id and tournament_id not in tournament_ids_processed:
                                logger.info(f"🏆 Buscando resultados finais do torneio {tournament_id}")
                                tournament_ids_processed.add(tournament_id)
                                
                                results_data = self.get_tournament_results(tournament_id)
                                if results_data:
                                    # Atualizar placares das partidas com os resultados
                                    results_matches = results_data.get('matches', [])
                                    
                                    # Criar dicionário de resultados por match_id
                                    results_by_match_id = {}
                                    for result_match in results_matches:
                                        match_id = result_match.get('id')
                                        if match_id:
                                            results_by_match_id[match_id] = result_match
                                    
                                    # Atualizar matches com os resultados
                                    for match in matches:
                                        match_id = match.get('id')
                                        if match_id in results_by_match_id:
                                            result = results_by_match_id[match_id]
                                            match['score1'] = result.get('score1')
                                            match['score2'] = result.get('score2')
                                            logger.debug(f"✅ Placar atualizado: Match {match_id} = {match['score1']} x {match['score2']}")
                            
                            all_matches.extend(matches)
            
            logger.info(f"✅ Total de {len(all_matches)} partidas em streaming coletadas")
            return all_matches
            
        except Exception as e:
            logger.error(f"❌ Erro ao buscar streaming matches: {e}")
            return []
    
    def get_live_matches(self) -> List[Dict]:
        """
        Busca apenas partidas ao vivo (status_id = 2)
        """
        try:
            # Buscar de ambas as fontes
            nearest = self.get_nearest_matches()
            streaming = self.get_streaming_matches()
            
            # Combinar e filtrar apenas as ao vivo
            all_matches = nearest + streaming
            live_matches = [m for m in all_matches if m.get('status_id') == 2]
            
            # Remover duplicatas (baseado no ID)
            unique_matches = {m['id']: m for m in live_matches}.values()
            
            logger.info(f"🔴 {len(unique_matches)} partidas ao vivo")
            return list(unique_matches)
            
        except Exception as e:
            logger.error(f"❌ Erro ao buscar live matches: {e}")
            return []
    
    def get_recent_matches(self, limit: int = 50) -> List[Dict]:
        """
        Busca partidas recentes (finalizadas recentemente)
        """
        try:
            nearest = self.get_nearest_matches()
            streaming = self.get_streaming_matches()
            
            # Combinar todas
            all_matches = nearest + streaming
            
            # Filtrar finalizadas
            finished = [m for m in all_matches if m.get('status_id') == 3]
            
            # Ordenar por data (mais recente primeiro)
            finished.sort(
                key=lambda x: x.get('date', ''),
                reverse=True
            )
            
            # Remover duplicatas
            unique_matches = []
            seen_ids = set()
            
            for match in finished:
                match_id = match.get('id')
                if match_id not in seen_ids:
                    seen_ids.add(match_id)
                    unique_matches.append(match)
                    
                    if len(unique_matches) >= limit:
                        break
            
            logger.info(f"📜 {len(unique_matches)} partidas recentes encontradas")
            return unique_matches
            
        except Exception as e:
            logger.error(f"❌ Erro ao buscar recent matches: {e}")
            return []
    
    def get_match_results(self, match_id: int) -> Optional[Dict]:
        """
        Busca resultado específico de uma partida
        Para partidas finalizadas, busca no endpoint de resultados do torneio
        """
        try:
            # Primeiro busca a partida
            nearest = self.get_nearest_matches()
            streaming = self.get_streaming_matches()
            
            all_matches = nearest + streaming
            
            match = None
            for m in all_matches:
                if m.get('id') == match_id:
                    match = m
                    break
            
            if not match:
                logger.warning(f"⚠️ Partida {match_id} não encontrada")
                return None
            
            # Se a partida já tem score1 e score2, retornar
            if 'score1' in match and 'score2' in match:
                return match
            
            # Se não tem, buscar do torneio
            tournament_id = match.get('tournament_id')
            if not tournament_id:
                return match
            
            # Buscar resultados do torneio
            results = self.get_tournament_results(tournament_id)
            if not results:
                return match
            
            # Procurar o placar da partida nos resultados
            # Nota: A estrutura pode variar, adaptar conforme necessário
            return match
            
        except Exception as e:
            logger.error(f"❌ Erro ao buscar resultado da partida {match_id}: {e}")
            return None
    
    def enrich_matches_with_scores(self, matches: List[Dict]) -> List[Dict]:
        """
        Enriquece partidas finalizadas com placares do endpoint de resultados
        """
        try:
            enriched_matches = []
            tournaments_cache = {}
            
            for match in matches:
                match_id = match.get('id')
                status_id = match.get('status_id')
                tournament_id = match.get('tournament_id')
                
                # Se já tem placares, adicionar e continuar
                if match.get('score1') is not None and match.get('score2') is not None:
                    enriched_matches.append(match)
                    continue
                
                # Se não é finalizada, adicionar sem placares
                if status_id != 3:
                    enriched_matches.append(match)
                    continue
                
                # Se é finalizada mas não tem tournament_id, adicionar sem placares
                if not tournament_id:
                    enriched_matches.append(match)
                    continue
                
                # Buscar resultados do torneio (usar cache)
                if tournament_id not in tournaments_cache:
                    results = self.get_tournament_results(tournament_id)
                    tournaments_cache[tournament_id] = results
                else:
                    results = tournaments_cache[tournament_id]
                
                if not results:
                    enriched_matches.append(match)
                    continue
                
                # Procurar os placares nos resultados
                # A API de results retorna uma lista de participantes com suas estatísticas
                # Mas NÃO retorna placares por partida individual
                # Vamos tentar extrair do campo 'matches' se existir
                
                # Por enquanto, adicionar sem placares
                # TODO: Investigar estrutura exata da API de results
                enriched_matches.append(match)
            
            return enriched_matches
            
        except Exception as e:
            logger.error(f"❌ Erro ao enriquecer partidas com placares: {e}")
            return matches
        """
        Busca resultados de um torneio específico
        """
        try:
            endpoint = self.ENDPOINTS['tournament_results'].format(tournament_id=tournament_id)
            data = self._make_request(endpoint)
            
            if data:
                logger.info(f"🏆 Resultados do torneio {tournament_id} obtidos")
                return data
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Erro ao buscar resultados do torneio {tournament_id}: {e}")
            return None
    
    def get_statuses(self) -> Optional[Dict]:
        """
        Busca todos os status disponíveis (partidas e torneios)
        """
        try:
            data = self._make_request(self.ENDPOINTS['statuses'])
            
            if data:
                logger.info("📋 Status obtidos com sucesso")
                return data
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Erro ao buscar statuses: {e}")
            return None
    
    def get_match_by_id(self, match_id: int) -> Optional[Dict]:
        """
        Busca uma partida específica pelo ID
        (procura em nearest e streaming)
        IMPORTANTE: Para partidas finalizadas, pode ter placares atualizados
        """
        try:
            # Buscar em nearest matches
            nearest = self.get_nearest_matches()
            for match in nearest:
                if match.get('id') == match_id:
                    logger.info(f"✅ Partida {match_id} encontrada em nearest")
                    # Log se tem placares
                    if 'score1' in match and 'score2' in match:
                        logger.info(f"⚽ Placares: {match.get('score1')} x {match.get('score2')}")
                    return match
            
            # Buscar em streaming
            streaming = self.get_streaming_matches()
            for match in streaming:
                if match.get('id') == match_id:
                    logger.info(f"✅ Partida {match_id} encontrada em streaming")
                    # Log se tem placares
                    if 'score1' in match and 'score2' in match:
                        logger.info(f"⚽ Placares: {match.get('score1')} x {match.get('score2')}")
                    return match
            
            logger.warning(f"⚠️ Partida {match_id} não encontrada")
            return None
            
        except Exception as e:
            logger.error(f"❌ Erro ao buscar partida {match_id}: {e}")
            return None
    
    def get_matches_by_location(self, location_code: str) -> List[Dict]:
        """
        Busca todas as partidas de uma location específica
        """
        try:
            nearest = self.get_nearest_matches()
            streaming = self.get_streaming_matches()
            
            all_matches = nearest + streaming
            
            # Filtrar por location
            location_matches = [
                m for m in all_matches
                if m.get('location', {}).get('code') == location_code
            ]
            
            # Remover duplicatas
            unique_matches = {m['id']: m for m in location_matches}.values()
            
            logger.info(f"📍 {len(unique_matches)} partidas na location {location_code}")
            return list(unique_matches)
            
        except Exception as e:
            logger.error(f"❌ Erro ao buscar partidas da location {location_code}: {e}")
            return []
    
    def get_matches_by_player(self, player_nickname: str) -> List[Dict]:
        """
        Busca todas as partidas de um jogador específico
        """
        try:
            nearest = self.get_nearest_matches()
            streaming = self.get_streaming_matches()
            
            all_matches = nearest + streaming
            
            # Filtrar por jogador
            player_matches = [
                m for m in all_matches
                if (m.get('participant1', {}).get('nickname') == player_nickname or
                    m.get('participant2', {}).get('nickname') == player_nickname)
            ]
            
            # Remover duplicatas
            unique_matches = {m['id']: m for m in player_matches}.values()
            
            logger.info(f"👤 {len(unique_matches)} partidas do jogador {player_nickname}")
            return list(unique_matches)
            
        except Exception as e:
            logger.error(f"❌ Erro ao buscar partidas do jogador {player_nickname}: {e}")
            return []
    
    def format_match_info(self, match: Dict) -> str:
        """
        Formata informações da partida para exibição
        """
        try:
            match_id = match.get('id', 'N/A')
            status_id = match.get('status_id', 1)
            status = self.STATUS.get(status_id, 'Unknown')
            
            date_str = match.get('date', '')
            if date_str:
                try:
                    date_obj = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                    date_formatted = date_obj.strftime('%Y-%m-%d %H:%M')
                except:
                    date_formatted = date_str
            else:
                date_formatted = 'N/A'
            
            p1 = match.get('participant1', {})
            p2 = match.get('participant2', {})
            
            p1_nick = p1.get('nickname', 'TBD')
            p2_nick = p2.get('nickname', 'TBD')
            
            p1_team = p1.get('team', {}).get('token_international', p1.get('team', {}).get('token', 'N/A'))
            p2_team = p2.get('team', {}).get('token_international', p2.get('team', {}).get('token', 'N/A'))
            
            score1 = match.get('score1', '-')
            score2 = match.get('score2', '-')
            
            location = match.get('location', {})
            location_name = location.get('token_international', location.get('token', 'N/A'))
            
            tournament = match.get('tournament', {})
            tournament_name = tournament.get('token_international', tournament.get('token', 'N/A'))
            
            info = f"""
🎮 Match #{match_id}
📅 {date_formatted}
🏆 {tournament_name}
📍 {location_name}
🔴 Status: {status}

👤 {p1_nick} ({p1_team}) {score1} x {score2} {p2_nick} ({p2_team})
"""
            return info.strip()
            
        except Exception as e:
            logger.error(f"❌ Erro ao formatar match info: {e}")
            return f"Match #{match.get('id', 'N/A')}"
    
    def get_tournament_results(self, tournament_id: int) -> Optional[Dict]:
        """
        Busca resultados finais de um torneio
        Retorna estatísticas dos participantes
        """
        try:
            url = self.ENDPOINTS['tournament_results'].format(tournament_id=tournament_id)
            logger.debug(f"🏆 Buscando resultados do torneio {tournament_id}")
            results = self._make_request(url)
            
            if results:
                logger.debug(f"✅ Resultados do torneio {tournament_id} obtidos")
                return results
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Erro ao buscar resultados do torneio {tournament_id}: {e}")
            return None


# Teste standalone
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    scraper = FIFA25Scraper()
    
    print("\n" + "="*80)
    print("🔍 TESTANDO SCRAPER FIFA25")
    print("="*80)
    
    # Teste 1: Nearest Matches
    print("\n📊 Buscando Nearest Matches...")
    nearest = scraper.get_nearest_matches()
    print(f"✅ Encontradas: {len(nearest)}")
    if nearest:
        print("\n" + scraper.format_match_info(nearest[0]))
    
    # Teste 2: Streaming Matches
    print("\n📺 Buscando Streaming Matches...")
    streaming = scraper.get_streaming_matches()
    print(f"✅ Encontradas: {len(streaming)}")
    
    # Teste 3: Live Matches
    print("\n🔴 Buscando Live Matches...")
    live = scraper.get_live_matches()
    print(f"✅ Ao vivo: {len(live)}")
    
    # Teste 4: Recent Matches
    print("\n📜 Buscando Recent Matches...")
    recent = scraper.get_recent_matches(10)
    print(f"✅ Recentes: {len(recent)}")
    
    # Teste 5: Statuses
    print("\n📋 Buscando Statuses...")
    statuses = scraper.get_statuses()
    if statuses:
        print(f"✅ Match statuses: {len(statuses.get('match', []))}")
        print(f"✅ Tournament statuses: {len(statuses.get('tournament', []))}")
    
    print("\n" + "="*80)
    print("✅ TESTES CONCLUÍDOS")
    print("="*80 + "\n")