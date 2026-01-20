"""
FIFA 25 Bot - Scraper Otimizado
Busca partidas diretamente de /locations/streaming
"""

import requests
import logging
from typing import List, Dict, Optional
from datetime import datetime
import pytz
import time

logger = logging.getLogger(__name__)


class FIFA25Scraper:
    """Scraper para coletar dados do eSports Battle FIFA 25"""
    
    BASE_URL = "https://football.esportsbattle.com/api"
    
    def __init__(self):
        """Inicializa o scraper"""
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
            'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
            'Referer': 'https://football.esportsbattle.com/en/',
        })
        self.tz_brasilia = pytz.timezone('America/Sao_Paulo')
    
    def _fetch_api(self, url: str) -> Optional[Dict]:
        """Faz requisição para a API"""
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.debug(f"Erro ao acessar {url}: {str(e)}")
            return None
    
    def _extract_match_data(self, match: Dict, location_name: str = "Unknown") -> Optional[Dict]:
        """Extrai dados de uma partida"""
        try:
            if 'participant1' not in match or 'participant2' not in match:
                return None
            
            p1 = match['participant1']
            p2 = match['participant2']
            
            # Jogadores
            home_player = p1.get('nickname', 'Desconhecido')
            away_player = p2.get('nickname', 'Desconhecido')
            
            # Times
            home_club = "N/A"
            away_club = "N/A"
            
            if 'team' in p1 and isinstance(p1['team'], dict):
                home_club = p1['team'].get('token_international') or p1['team'].get('token') or 'N/A'
            
            if 'team' in p2 and isinstance(p2['team'], dict):
                away_club = p2['team'].get('token_international') or p2['team'].get('token') or 'N/A'
            
            # Placar
            home_score = p1.get('score', 0)
            away_score = p2.get('score', 0)
            
            # Estádio
            stadium = location_name
            if 'location' in match and isinstance(match['location'], dict):
                stadium = (
                    match['location'].get('token_international') or 
                    match['location'].get('token') or 
                    location_name
                )
            
            # Status
            status_id = match.get('status_id', 0)
            is_live = status_id in [1, 2]
            status = 'live' if is_live else ('finished' if status_id == 3 else 'scheduled')
            
            # Torneio
            tournament = match.get('tournament', {})
            tournament_name = "Unknown"
            if isinstance(tournament, dict):
                tournament_name = (
                    tournament.get('token_international') or 
                    tournament.get('token') or 
                    'Unknown'
                )
            
            # Data/hora
            date_str = match.get('date')
            start_time = None
            if date_str:
                try:
                    dt_utc = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                    dt_brasilia = dt_utc.astimezone(self.tz_brasilia)
                    start_time = dt_brasilia.replace(tzinfo=None)
                except:
                    pass
            
            return {
                'id': str(match.get('id', '')),
                'home_player': home_player,
                'away_player': away_player,
                'home_club': home_club,
                'away_club': away_club,
                'home_score': int(home_score) if home_score else 0,
                'away_score': int(away_score) if away_score else 0,
                'status': status,
                'is_live': is_live,
                'stadium': stadium,
                'tournament': tournament_name,
                'start_time': start_time,
                'minute': 0,
                'raw_data': match
            }
            
        except Exception as e:
            logger.error(f"Erro ao extrair partida: {str(e)}")
            return None
    
    def _get_tournament_matches_from_api(self, tournament_id: int) -> List[Dict]:
        """
        Busca partidas de um torneio usando endpoint /tournaments/{id}
        Este endpoint retorna os dados completos do torneio
        """
        url = f"{self.BASE_URL}/tournaments/{tournament_id}"
        data = self._fetch_api(url)
        
        if not data:
            return []
        
        matches = []
        
        # Se for um array (resposta wrapper)
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and 'matches' in item:
                    if isinstance(item['matches'], list):
                        matches.extend(item['matches'])
        
        # Se for um dict direto
        elif isinstance(data, dict):
            if 'matches' in data and isinstance(data['matches'], list):
                matches.extend(data['matches'])
        
        return matches
    
    def scrape_all(self) -> Dict:
        """Coleta partidas de TODOS os estádios"""
        logger.info("=" * 80)
        logger.info("🚀 INICIANDO COLETA (TODOS OS ESTÁDIOS)")
        logger.info("=" * 80)
        
        all_matches = []
        
        # Busca locations/streaming
        endpoint = f"{self.BASE_URL}/locations/streaming"
        data = self._fetch_api(endpoint)
        
        if not data:
            logger.warning("⚠️ Nenhum dado retornado de /locations/streaming")
            return self._build_response([])
        
        # Extrai todas as locations
        locations = []
        
        # Se retornou array de locations
        if isinstance(data, list):
            locations = data
        # Se retornou dict com locations
        elif isinstance(data, dict):
            if 'locations' in data:
                locations = data['locations']
            else:
                locations = [data]
        
        logger.info(f"📍 Encontradas {len(locations)} locations")
        
        # Para cada location/estádio
        for location in locations:
            if not isinstance(location, dict):
                continue
            
            location_name = (
                location.get('token_international') or 
                location.get('token') or 
                'Unknown'
            )
            
            match_count = location.get('matchCount', 0)
            
            if match_count == 0:
                logger.debug(f"   🏟️  {location_name}: 0 partidas")
                continue
            
            logger.info(f"   🏟️  {location_name}: {match_count} partida(s)")
            
            # PRIORIDADE 1: Se já tem 'matches' diretamente na location
            if 'matches' in location and isinstance(location['matches'], list):
                logger.info(f"      ✅ Partidas encontradas diretamente na location")
                for match in location['matches']:
                    if isinstance(match, dict):
                        processed = self._extract_match_data(match, location_name)
                        if processed:
                            all_matches.append(processed)
                            logger.info(
                                f"         ⚽ {processed['home_player']} ({processed['home_club']}) "
                                f"{processed['home_score']}-{processed['away_score']} "
                                f"({processed['away_club']}) {processed['away_player']}"
                            )
            
            # PRIORIDADE 2: Busca nos torneios
            if 'tournaments' in location and isinstance(location['tournaments'], list):
                for tid in location['tournaments']:
                    try:
                        tid = int(tid)
                    except:
                        continue
                    
                    logger.info(f"      🔍 Buscando torneio {tid}...")
                    tournament_matches = self._get_tournament_matches_from_api(tid)
                    
                    if tournament_matches:
                        logger.info(f"         ✅ {len(tournament_matches)} partida(s) encontrada(s)")
                        for match in tournament_matches:
                            processed = self._extract_match_data(match, location_name)
                            if processed:
                                all_matches.append(processed)
                                logger.info(
                                    f"            ⚽ {processed['home_player']} ({processed['home_club']}) "
                                    f"{processed['home_score']}-{processed['away_score']} "
                                    f"({processed['away_club']}) {processed['away_player']}"
                                )
                    else:
                        logger.debug(f"         ℹ️ Nenhuma partida no torneio {tid}")
                    
                    time.sleep(0.2)
        
        return self._build_response(all_matches)
    
    def _build_response(self, matches: List[Dict]) -> Dict:
        """Constrói resposta final"""
        # Remove duplicatas
        unique_matches = {}
        for match in matches:
            match_id = match['id']
            if match_id not in unique_matches:
                unique_matches[match_id] = match
        
        final_matches = list(unique_matches.values())
        
        # Horário em Brasília
        now_brasilia = datetime.now(self.tz_brasilia)
        
        logger.info("=" * 80)
        logger.info("✅ FINALIZADO")
        logger.info(f"📊 Total coletado: {len(final_matches)} partidas únicas")
        logger.info(f"🕐 Horário: {now_brasilia.strftime('%d/%m/%Y %H:%M:%S')} (Brasília)")
        logger.info("=" * 80)
        
        return {
            'live': [m for m in final_matches if m['is_live']],
            'recent': [m for m in final_matches if not m['is_live']],
            'timestamp': now_brasilia.isoformat()
        }


def scrape_matches() -> Dict:
    """Função auxiliar para executar scraping"""
    scraper = FIFA25Scraper()
    return scraper.scrape_all()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    results = scrape_matches()
    
    print("\n" + "=" * 80)
    print("RESUMO")
    print("=" * 80)
    print(f"Ao vivo: {len(results['live'])}")
    print(f"Recentes: {len(results['recent'])}")
    
    if results['live']:
        print("\nPartidas ao vivo:")
        for m in results['live'][:5]:
            print(f"  🏟️ {m['stadium']}: {m['home_player']} {m['home_score']}-{m['away_score']} {m['away_player']}")