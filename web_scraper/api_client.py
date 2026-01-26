# -*- coding: utf-8 -*-
"""
web_scraper/api_client.py

Cliente da API ESportsBattle (football.esportsbattle.com)
Versão corrigida baseada na estrutura real da API

ESTRUTURA DA API CONFIRMADA:
- GET /api/locations → Lista direta de locations
- GET /api/tournaments?page=N → {totalPages: int, tournaments: []}
- GET /api/teams?page=N → {totalPages: int, teams: []}
- GET /api/tournaments/{id}/matches → Lista de partidas
"""

import requests
import logging
from typing import List, Dict, Optional
from datetime import datetime
import time

logger = logging.getLogger(__name__)


class FIFA25APIClient:
    """
    Cliente da API do ESportsBattle
    
    Uso:
        client = FIFA25APIClient()
        data = client.scrape_all_data()
        print(f"Torneios: {len(data['tournaments'])}")
    """
    
    def __init__(self):
        self.base_url = "https://football.esportsbattle.com"
        self.session = self._create_session()
        
        # Cache para evitar requisições desnecessárias
        self._cache = {}
        self._cache_duration = 60  # 60 segundos
        
    def _create_session(self) -> requests.Session:
        """Cria sessão HTTP com headers apropriados"""
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9,pt-BR;q=0.8,pt;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Referer': f'{self.base_url}/en/',
            'Origin': self.base_url,
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
        })
        return session
    
    def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """
        Faz requisição HTTP com tratamento de erros
        
        Args:
            endpoint: Endpoint da API (ex: '/api/tournaments')
            params: Parâmetros query string
            
        Returns:
            Dados JSON ou None se erro
        """
        url = f"{self.base_url}{endpoint}"
        
        try:
            logger.debug(f"Requisitando: {url} com params: {params}")
            response = self.session.get(url, params=params, timeout=15)
            
            if response.status_code == 200:
                try:
                    return response.json()
                except ValueError as e:
                    logger.error(f"Resposta não é JSON válido: {e}")
                    return None
            elif response.status_code == 404:
                logger.debug(f"Endpoint não encontrado: {endpoint}")
                return None
            elif response.status_code == 403:
                logger.warning(f"Acesso proibido (403): {endpoint}")
                return None
            elif response.status_code == 429:
                logger.warning(f"Rate limit atingido (429): {endpoint}")
                time.sleep(5)
                return None
            else:
                logger.warning(f"Status {response.status_code}: {endpoint}")
                return None
                
        except requests.exceptions.Timeout:
            logger.error(f"Timeout ao acessar: {endpoint}")
            return None
        except requests.exceptions.ConnectionError:
            logger.error(f"Erro de conexão: {endpoint}")
            return None
        except Exception as e:
            logger.error(f"Erro inesperado em {endpoint}: {e}")
            return None
    
    def get_locations(self) -> List[Dict]:
        """
        Busca todas as locations (estádios/locais)
        
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
        
        Returns:
            Lista de locations
        """
        # Verificar cache
        cache_key = 'locations'
        if cache_key in self._cache:
            cache_time, cache_data = self._cache[cache_key]
            if (datetime.now().timestamp() - cache_time) < self._cache_duration:
                logger.debug("Usando locations do cache")
                return cache_data
        
        logger.info("📍 Buscando locations...")
        
        data = self._make_request('/api/locations')
        
        if not data:
            logger.warning("Nenhuma location encontrada")
            return []
        
        # API retorna lista direta
        locations = data if isinstance(data, list) else []
        
        logger.info(f"✅ {len(locations)} location(s) encontrada(s)")
        
        # Log detalhado
        for loc in locations:
            loc_name = loc.get('token_international') or loc.get('token', 'N/A')
            logger.info(f"   🏟️  {loc_name} (ID: {loc.get('id')})")
        
        # Atualizar cache
        self._cache[cache_key] = (datetime.now().timestamp(), locations)
        
        return locations
    
    def get_tournaments(self, page: int = 1, location_id: Optional[int] = None) -> Dict:
        """
        Busca torneios com paginação
        
        Retorna estrutura:
        {
            "totalPages": 0,
            "tournaments": []
        }
        
        Args:
            page: Número da página (padrão: 1)
            location_id: Filtrar por location específica (opcional)
            
        Returns:
            Dict com totalPages e tournaments
        """
        params = {'page': page}
        if location_id:
            params['location'] = location_id
        
        log_msg = f"🏆 Buscando torneios (página {page}"
        if location_id:
            log_msg += f", location {location_id}"
        log_msg += ")..."
        logger.info(log_msg)
        
        data = self._make_request('/api/tournaments', params)
        
        if not data:
            logger.warning("Endpoint de torneios não retornou dados")
            return {'totalPages': 0, 'tournaments': []}
        
        # Estrutura confirmada da API
        total_pages = data.get('totalPages', 0)
        tournaments = data.get('tournaments', [])
        
        logger.info(f"📊 Total de páginas: {total_pages}")
        logger.info(f"✅ {len(tournaments)} torneio(s) nesta página")
        
        # Log detalhado dos torneios
        if tournaments:
            for t in tournaments:
                t_id = t.get('id', 'N/A')
                t_name = t.get('name') or t.get('token', 'N/A')
                t_status = t.get('status', 'N/A')
                logger.info(f"   🏆 ID {t_id}: {t_name} (Status: {t_status})")
        
        return {
            'totalPages': total_pages,
            'tournaments': tournaments
        }
    
    def get_all_tournaments(self, location_id: Optional[int] = None) -> List[Dict]:
        """
        Busca TODOS os torneios de todas as páginas
        
        Args:
            location_id: Filtrar por location específica (opcional)
            
        Returns:
            Lista com todos os torneios
        """
        logger.info("🔄 Buscando todos os torneios (todas as páginas)...")
        
        all_tournaments = []
        page = 1
        max_pages = 100  # Segurança para evitar loop infinito
        
        while page <= max_pages:
            result = self.get_tournaments(page, location_id)
            tournaments = result['tournaments']
            total_pages = result['totalPages']
            
            all_tournaments.extend(tournaments)
            
            # Se não há mais páginas ou não há torneios, parar
            if page >= total_pages or not tournaments or total_pages == 0:
                break
            
            page += 1
            time.sleep(0.5)  # Rate limiting
        
        logger.info(f"✅ Total de {len(all_tournaments)} torneios coletados")
        return all_tournaments
    
    def get_tournament_details(self, tournament_id: int) -> Optional[Dict]:
        """
        Busca detalhes de um torneio específico
        
        Args:
            tournament_id: ID do torneio
            
        Returns:
            Dados do torneio ou None
        """
        logger.debug(f"Buscando detalhes do torneio {tournament_id}...")
        
        # Tentar diferentes endpoints possíveis
        endpoints = [
            f'/api/tournaments/{tournament_id}',
            f'/api/tournaments/{tournament_id}/details',
        ]
        
        for endpoint in endpoints:
            data = self._make_request(endpoint)
            if data:
                logger.debug(f"✓ Detalhes encontrados via {endpoint}")
                return data
        
        logger.debug(f"Nenhum detalhe encontrado para torneio {tournament_id}")
        return None
    
    def get_matches(self, tournament_id: Optional[int] = None) -> List[Dict]:
        """
        Busca partidas
        
        Args:
            tournament_id: Filtrar por torneio específico (opcional)
            
        Returns:
            Lista de partidas
        """
        if tournament_id:
            logger.info(f"⚽ Buscando partidas do torneio {tournament_id}...")
            
            # Tentar diferentes endpoints
            endpoints = [
                f'/api/tournaments/{tournament_id}/matches',
                f'/api/matches?tournament={tournament_id}',
                f'/api/matches?tournamentId={tournament_id}',
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
    
    def _extract_matches(self, data: Optional[Dict]) -> List[Dict]:
        """
        Extrai partidas de diferentes estruturas de resposta
        
        Args:
            data: Resposta da API
            
        Returns:
            Lista de partidas
        """
        if not data:
            return []
        
        # Se já é uma lista
        if isinstance(data, list):
            return data
        
        # Se é um dicionário, tentar diferentes chaves
        if isinstance(data, dict):
            for key in ['matches', 'data', 'items', 'results']:
                if key in data:
                    matches = data[key]
                    if isinstance(matches, list):
                        return matches
        
        return []
    
    def get_teams(self, page: int = 1) -> Dict:
        """
        Busca teams com paginação
        
        Retorna estrutura:
        {
            "totalPages": 1,
            "teams": [...]
        }
        
        Args:
            page: Número da página (padrão: 1)
            
        Returns:
            Dict com totalPages e teams
        """
        params = {'page': page}
        
        logger.info(f"👥 Buscando teams (página {page})...")
        
        data = self._make_request('/api/teams', params)
        
        if not data:
            logger.warning("Endpoint de teams não retornou dados")
            return {'totalPages': 0, 'teams': []}
        
        total_pages = data.get('totalPages', 0)
        teams = data.get('teams', [])
        
        logger.info(f"✅ {len(teams)} team(s) encontrado(s)")
        
        return {
            'totalPages': total_pages,
            'teams': teams
        }
    
    def get_all_teams(self) -> List[Dict]:
        """
        Busca TODOS os teams de todas as páginas
        
        Returns:
            Lista com todos os teams
        """
        logger.info("🔄 Buscando todos os teams (todas as páginas)...")
        
        all_teams = []
        page = 1
        max_pages = 100  # Segurança
        
        while page <= max_pages:
            result = self.get_teams(page)
            teams = result['teams']
            total_pages = result['totalPages']
            
            all_teams.extend(teams)
            
            if page >= total_pages or not teams or total_pages == 0:
                break
            
            page += 1
            time.sleep(0.5)  # Rate limiting
        
        logger.info(f"✅ Total de {len(all_teams)} teams coletados")
        return all_teams
    
    def scrape_all_data(self) -> Dict:
        """
        Coleta TODOS os dados disponíveis
        
        Este é o método principal para usar no bot.
        Coleta: locations, torneios, partidas e teams
        
        Returns:
            Dict com todos os dados e resumo
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
                'timestamp': datetime.now().isoformat(),
                'success': False
            }
        }
        
        try:
            # 1. Buscar locations
            logger.info("\n[1/4] Buscando locations...")
            results['locations'] = self.get_locations()
            results['summary']['locations_count'] = len(results['locations'])
            time.sleep(0.5)
            
            # 2. Buscar torneios (todas as páginas)
            logger.info("\n[2/4] Buscando torneios...")
            results['tournaments'] = self.get_all_tournaments()
            results['summary']['tournaments_count'] = len(results['tournaments'])
            
            # Se não encontrou torneios gerais, tentar por location
            if not results['tournaments'] and results['locations']:
                logger.info("Nenhum torneio geral encontrado, tentando por location...")
                for location in results['locations']:
                    loc_id = location.get('id')
                    if loc_id:
                        tournaments = self.get_all_tournaments(loc_id)
                        results['tournaments'].extend(tournaments)
                        time.sleep(0.3)
                
                results['summary']['tournaments_count'] = len(results['tournaments'])
            
            time.sleep(0.5)
            
            # 3. Buscar partidas de cada torneio
            logger.info("\n[3/4] Buscando partidas...")
            if results['tournaments']:
                logger.info(f"Processando {len(results['tournaments'])} torneios...")
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
            
            # 4. Buscar teams (todas as páginas)
            logger.info("\n[4/4] Buscando teams...")
            results['teams'] = self.get_all_teams()
            results['summary']['teams_count'] = len(results['teams'])
            
            # Marcar como sucesso
            results['summary']['success'] = True
            
        except Exception as e:
            logger.error(f"❌ Erro durante coleta de dados: {e}")
            results['summary']['error'] = str(e)
        
        # Log resumo final
        logger.info("")
        logger.info("="*80)
        logger.info("📊 RESUMO DA COLETA")
        logger.info("="*80)
        logger.info(f"   Locations: {results['summary']['locations_count']}")
        logger.info(f"   Torneios: {results['summary']['tournaments_count']}")
        logger.info(f"   Partidas: {results['summary']['matches_count']}")
        logger.info(f"   Teams: {results['summary']['teams_count']}")
        logger.info("="*80)
        
        # Status final
        if results['summary']['matches_count'] > 0:
            logger.info("✅ SUCESSO - Partidas encontradas!")
        elif results['summary']['tournaments_count'] > 0:
            logger.warning("⚠️  Torneios encontrados mas sem partidas ainda")
        else:
            logger.warning("⚠️  Nenhum torneio ativo no momento")
            logger.info("💡 Tente novamente em horário de jogos (10h-23h UTC)")
        
        return results
    
    def get_summary(self) -> Dict:
        """
        Retorna resumo rápido dos dados disponíveis
        Útil para verificações rápidas
        
        Returns:
            Dict com contagem de locations e torneios
        """
        locations = self.get_locations()
        tournaments_result = self.get_tournaments()
        
        return {
            'locations_count': len(locations),
            'tournaments_count': len(tournaments_result['tournaments']),
            'tournaments_pages': tournaments_result['totalPages'],
            'timestamp': datetime.now().isoformat()
        }


# Classe para compatibilidade com código antigo
class FIFA25Scraper:
    """
    Alias para manter compatibilidade com código existente
    """
    
    def __init__(self):
        self.client = FIFA25APIClient()
    
    def get_live_matches(self):
        """Busca partidas (compatibilidade)"""
        return self.client.get_matches()
    
    def get_recent_matches(self):
        """Busca partidas (compatibilidade)"""
        return self.client.get_matches()
    
    def scrape_all_data(self):
        """Compatibilidade"""
        return self.client.scrape_all_data()


# Teste rápido quando executado diretamente
if __name__ == "__main__":
    import sys
    
    # Configurar logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    print("\n" + "="*80)
    print("TESTE DA API ESportsBattle")
    print("="*80 + "\n")
    
    client = FIFA25APIClient()
    
    # Teste rápido
    try:
        summary = client.get_summary()
        
        print("Resultados:")
        print(f"  Locations: {summary['locations_count']}")
        print(f"  Torneios (página 1): {summary['tournaments_count']}")
        print(f"  Total de páginas: {summary['tournaments_pages']}")
        
        print("\n" + "="*80)
        
        if summary['tournaments_count'] > 0:
            print("✅ API funcionando - há torneios ativos!")
        else:
            print("✅ API funcionando - aguardando torneios ativos")
            print("💡 Torneios geralmente ocorrem entre 10h-23h UTC")
        
        print("="*80 + "\n")
        
    except Exception as e:
        print(f"❌ Erro: {e}")
        sys.exit(1)