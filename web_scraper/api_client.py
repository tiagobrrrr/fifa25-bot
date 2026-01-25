# -*- coding: utf-8 -*-
"""
api_client.py - VERSÃO FINAL CORRIGIDA
Baseado na estrutura REAL da API descoberta no api_findings.json

ESTRUTURA CONFIRMADA:
- /api/locations → retorna lista direta
- /api/tournaments → retorna {totalPages: int, tournaments: []}
- /api/teams → retorna {totalPages: int, teams: []}
"""

import requests
import logging
from typing import List, Dict, Optional
from datetime import datetime
import time

logger = logging.getLogger(__name__)


class FIFA25APIClient:
    """Cliente da API ESportsBattle com estrutura correta"""
    
    def __init__(self):
        self.base_url = "https://football.esportsbattle.com"
        self.session = self._create_session()
        
    def _create_session(self):
        """Cria sessão HTTP"""
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': f'{self.base_url}/en/',
            'Origin': self.base_url,
        })
        return session
    
    def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """Faz requisição HTTP"""
        url = f"{self.base_url}{endpoint}"
        
        try:
            response = self.session.get(url, params=params, timeout=15)
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                logger.debug(f"404: {endpoint}")
            else:
                logger.warning(f"Status {response.status_code}: {endpoint}")
            
            return None
            
        except Exception as e:
            logger.error(f"Erro em {endpoint}: {e}")
            return None
    
    def get_locations(self) -> List[Dict]:
        """
        Busca locations
        
        Retorna lista direta:
        [
            {
                "id": 1,
                "status_id": 1,
                "token": "Wembley",
                "token_international": "Wembley",
                "color": "#008080"
            }
        ]
        """
        logger.info("📍 Buscando locations...")
        
        data = self._make_request('/api/locations')
        
        if not data:
            logger.warning("Nenhuma location encontrada")
            return []
        
        # API retorna lista direta
        locations = data if isinstance(data, list) else []
        
        logger.info(f"✅ {len(locations)} location(s) encontrada(s)")
        
        for loc in locations:
            logger.info(f"   🏟️  {loc.get('token_international', loc.get('token', 'N/A'))}")
        
        return locations
    
    def get_tournaments(self, page: int = 1, location_id: Optional[int] = None) -> Dict:
        """
        Busca torneios (com paginação)
        
        Retorna estrutura:
        {
            "totalPages": 0,
            "tournaments": []
        }
        
        Args:
            page: Número da página (padrão: 1)
            location_id: Filtrar por location (opcional)
        """
        params = {'page': page}
        if location_id:
            params['location'] = location_id
        
        logger.info(f"🏆 Buscando torneios (página {page})...")
        
        data = self._make_request('/api/tournaments', params)
        
        if not data:
            logger.warning("Endpoint de torneios não retornou dados")
            return {'totalPages': 0, 'tournaments': []}
        
        # Estrutura confirmada da API
        total_pages = data.get('totalPages', 0)
        tournaments = data.get('tournaments', [])
        
        logger.info(f"📊 Total de páginas: {total_pages}")
        logger.info(f"✅ {len(tournaments)} torneio(s) nesta página")
        
        if tournaments:
            for t in tournaments:
                t_id = t.get('id', 'N/A')
                t_name = t.get('name', t.get('token', 'N/A'))
                logger.info(f"   🏆 ID {t_id}: {t_name}")
        
        return {
            'totalPages': total_pages,
            'tournaments': tournaments
        }
    
    def get_all_tournaments(self, location_id: Optional[int] = None) -> List[Dict]:
        """
        Busca TODOS os torneios (todas as páginas)
        
        Args:
            location_id: Filtrar por location (opcional)
        """
        logger.info("🔄 Buscando todos os torneios...")
        
        all_tournaments = []
        page = 1
        
        while True:
            result = self.get_tournaments(page, location_id)
            tournaments = result['tournaments']
            total_pages = result['totalPages']
            
            all_tournaments.extend(tournaments)
            
            # Se não há mais páginas, parar
            if page >= total_pages or not tournaments:
                break
            
            page += 1
            time.sleep(0.5)  # Rate limiting
        
        logger.info(f"✅ Total de torneios coletados: {len(all_tournaments)}")
        return all_tournaments
    
    def get_tournament_details(self, tournament_id: int) -> Optional[Dict]:
        """Busca detalhes de um torneio específico"""
        logger.debug(f"Buscando detalhes do torneio {tournament_id}...")
        
        endpoints = [
            f'/api/tournaments/{tournament_id}',
            f'/api/tournaments/{tournament_id}/details',
            f'/api/tournaments/{tournament_id}/matches'
        ]
        
        for endpoint in endpoints:
            data = self._make_request(endpoint)
            if data:
                logger.debug(f"✓ Detalhes encontrados via {endpoint}")
                return data
        
        return None
    
    def get_matches(self, tournament_id: Optional[int] = None) -> List[Dict]:
        """
        Busca partidas
        
        Args:
            tournament_id: Filtrar por torneio (opcional)
        """
        if tournament_id:
            logger.info(f"⚽ Buscando partidas do torneio {tournament_id}...")
            
            endpoints = [
                f'/api/tournaments/{tournament_id}/matches',
                f'/api/matches?tournament={tournament_id}',
                f'/api/matches?tournamentId={tournament_id}'
            ]
            
            for endpoint in endpoints:
                data = self._make_request(endpoint)
                if data:
                    matches = self._extract_matches(data)
                    if matches:
                        logger.info(f"✅ {len(matches)} partida(s) encontrada(s)")
                        return matches
            
            logger.warning(f"Nenhuma partida encontrada para torneio {tournament_id}")
            return []
        else:
            logger.info("⚽ Buscando todas as partidas...")
            data = self._make_request('/api/matches')
            matches = self._extract_matches(data)
            logger.info(f"✅ {len(matches)} partida(s) encontrada(s)")
            return matches
    
    def _extract_matches(self, data: Dict) -> List[Dict]:
        """Extrai partidas de diferentes estruturas de resposta"""
        if not data:
            return []
        
        if isinstance(data, list):
            return data
        
        if isinstance(data, dict):
            # Tentar diferentes chaves
            for key in ['matches', 'data', 'items', 'results']:
                if key in data:
                    matches = data[key]
                    return matches if isinstance(matches, list) else []
        
        return []
    
    def get_teams(self, page: int = 1) -> Dict:
        """
        Busca teams (com paginação)
        
        Retorna estrutura:
        {
            "totalPages": 1,
            "teams": [...]
        }
        """
        params = {'page': page}
        
        logger.info(f"👥 Buscando teams (página {page})...")
        
        data = self._make_request('/api/teams', params)
        
        if not data:
            return {'totalPages': 0, 'teams': []}
        
        total_pages = data.get('totalPages', 0)
        teams = data.get('teams', [])
        
        logger.info(f"✅ {len(teams)} team(s) encontrado(s)")
        
        return {
            'totalPages': total_pages,
            'teams': teams
        }
    
    def get_all_teams(self) -> List[Dict]:
        """Busca TODOS os teams (todas as páginas)"""
        logger.info("🔄 Buscando todos os teams...")
        
        all_teams = []
        page = 1
        
        while True:
            result = self.get_teams(page)
            teams = result['teams']
            total_pages = result['totalPages']
            
            all_teams.extend(teams)
            
            if page >= total_pages or not teams:
                break
            
            page += 1
            time.sleep(0.5)
        
        logger.info(f"✅ Total de teams coletados: {len(all_teams)}")
        return all_teams
    
    def scrape_all_data(self) -> Dict[str, any]:
        """
        Coleta TODOS os dados disponíveis
        Método principal para usar no bot
        """
        logger.info("="*80)
        logger.info("🔄 Iniciando coleta completa de dados ESportsBattle")
        logger.info("="*80)
        
        results = {
            'locations': [],
            'tournaments': [],
            'matches': [],
            'teams': [],
            'summary': {
                'locations_count': 0,
                'tournaments_count': 0,
                'matches_count': 0,
                'teams_count': 0,
                'timestamp': datetime.now().isoformat()
            }
        }
        
        try:
            # 1. Locations
            results['locations'] = self.get_locations()
            results['summary']['locations_count'] = len(results['locations'])
            time.sleep(0.5)
            
            # 2. Torneios (todas as páginas)
            results['tournaments'] = self.get_all_tournaments()
            results['summary']['tournaments_count'] = len(results['tournaments'])
            
            # Se não encontrou torneios gerais, tentar por location
            if not results['tournaments'] and results['locations']:
                logger.info("Tentando buscar torneios por location...")
                for location in results['locations']:
                    loc_id = location.get('id')
                    if loc_id:
                        tournaments = self.get_all_tournaments(loc_id)
                        results['tournaments'].extend(tournaments)
                        time.sleep(0.3)
                
                results['summary']['tournaments_count'] = len(results['tournaments'])
            
            time.sleep(0.5)
            
            # 3. Partidas de cada torneio
            if results['tournaments']:
                logger.info(f"🔍 Buscando partidas de {len(results['tournaments'])} torneios...")
                for tournament in results['tournaments']:
                    tournament_id = tournament.get('id')
                    if tournament_id:
                        matches = self.get_matches(tournament_id)
                        results['matches'].extend(matches)
                        time.sleep(0.3)
            else:
                # Tentar buscar partidas gerais
                logger.info("Tentando buscar partidas gerais...")
                results['matches'] = self.get_matches()
            
            results['summary']['matches_count'] = len(results['matches'])
            time.sleep(0.5)
            
            # 4. Teams (todas as páginas)
            results['teams'] = self.get_all_teams()
            results['summary']['teams_count'] = len(results['teams'])
            
        except Exception as e:
            logger.error(f"❌ Erro durante coleta: {e}")
        
        # Log resumo
        logger.info("")
        logger.info("="*80)
        logger.info("📊 RESUMO DA COLETA")
        logger.info("="*80)
        logger.info(f"   Locations: {results['summary']['locations_count']}")
        logger.info(f"   Torneios: {results['summary']['tournaments_count']}")
        logger.info(f"   Partidas: {results['summary']['matches_count']}")
        logger.info(f"   Teams: {results['summary']['teams_count']}")
        logger.info("="*80)
        
        # Status
        if results['summary']['matches_count'] > 0:
            logger.info("✅ SUCESSO - Partidas encontradas!")
        elif results['summary']['tournaments_count'] > 0:
            logger.warning("⚠️  Torneios encontrados mas sem partidas")
        else:
            logger.warning("⚠️  Nenhum torneio ativo no momento")
            logger.info("💡 Tente novamente em horário de jogos (10h-23h UTC)")
        
        return results
    
    def get_summary(self) -> Dict:
        """Retorna resumo rápido"""
        locations = self.get_locations()
        tournaments_result = self.get_tournaments()
        
        return {
            'locations_count': len(locations),
            'tournaments_count': len(tournaments_result['tournaments']),
            'tournaments_pages': tournaments_result['totalPages'],
            'timestamp': datetime.now().isoformat()
        }


# Para compatibilidade com código antigo
class FIFA25Scraper:
    """Alias para compatibilidade"""
    
    def __init__(self):
        self.client = FIFA25APIClient()
    
    def get_live_matches(self):
        return self.client.get_matches()
    
    def get_recent_matches(self):
        return self.client.get_matches()


# Teste rápido
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    client = FIFA25APIClient()
    
    # Teste rápido
    print("\n" + "="*80)
    print("TESTE RÁPIDO DA API")
    print("="*80 + "\n")
    
    # 1. Locations
    locations = client.get_locations()
    print(f"✓ Locations: {len(locations)}")
    
    # 2. Torneios
    tournaments_data = client.get_tournaments()
    print(f"✓ Torneios (página 1): {len(tournaments_data['tournaments'])}")
    print(f"✓ Total de páginas: {tournaments_data['totalPages']}")
    
    # 3. Teams
    teams_data = client.get_teams()
    print(f"✓ Teams (página 1): {len(teams_data['teams'])}")
    
    print("\n" + "="*80)
    
    if tournaments_data['tournaments']:
        print("✅ API funcionando - há torneios ativos!")
    else:
        print("⚠️  API funcionando mas SEM torneios ativos no momento")
        print("💡 Isso é normal - tente em horário de jogos")
    
    print("="*80 + "\n")