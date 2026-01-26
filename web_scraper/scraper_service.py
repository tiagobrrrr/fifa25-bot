# -*- coding: utf-8 -*-
"""
web_scraper/scraper_service.py

Serviço de scraping que coordena a coleta de dados
e integração com o banco de dados
"""

import logging
from datetime import datetime
from typing import Dict, List
from .api_client import FIFA25APIClient

logger = logging.getLogger(__name__)


class ScraperService:
    """
    Serviço de scraping para ESportsBattle
    
    Responsabilidades:
    - Coordenar coleta de dados da API
    - Processar e validar dados
    - Salvar no banco de dados
    - Gerenciar estado e estatísticas
    """
    
    def __init__(self):
        self.client = FIFA25APIClient()
        
        # Estatísticas
        self.stats = {
            'total_runs': 0,
            'successful_runs': 0,
            'failed_runs': 0,
            'last_run': None,
            'last_success': None,
            'last_tournaments_count': 0,
            'last_matches_count': 0,
            'consecutive_empty': 0
        }
    
    def run_scraping(self) -> Dict:
        """
        Executa ciclo completo de scraping
        
        Returns:
            Dict com resultado da execução
        """
        logger.info("="*80)
        logger.info("🔄 Executando scraping ESportsBattle")
        logger.info(f"⏰ Horário: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("="*80)
        
        self.stats['total_runs'] += 1
        self.stats['last_run'] = datetime.now().isoformat()
        
        try:
            # Coletar dados da API
            data = self.client.scrape_all_data()
            
            if not data['summary']['success']:
                raise Exception("Falha na coleta de dados da API")
            
            # Processar dados
            result = self._process_data(data)
            
            # Atualizar estatísticas
            if result['success']:
                self.stats['successful_runs'] += 1
                self.stats['last_success'] = datetime.now().isoformat()
                
                current_tournaments = data['summary']['tournaments_count']
                current_matches = data['summary']['matches_count']
                
                # Detectar mudanças
                if current_tournaments != self.stats['last_tournaments_count']:
                    logger.info(f"🔔 Mudança detectada: {current_tournaments} torneios "
                              f"(antes: {self.stats['last_tournaments_count']})")
                
                if current_matches != self.stats['last_matches_count']:
                    logger.info(f"🔔 Mudança detectada: {current_matches} partidas "
                              f"(antes: {self.stats['last_matches_count']})")
                
                self.stats['last_tournaments_count'] = current_tournaments
                self.stats['last_matches_count'] = current_matches
                
                # Reset contador de vazios
                if current_tournaments > 0:
                    self.stats['consecutive_empty'] = 0
                else:
                    self.stats['consecutive_empty'] += 1
            else:
                self.stats['failed_runs'] += 1
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Erro durante scraping: {e}")
            self.stats['failed_runs'] += 1
            
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def _process_data(self, data: Dict) -> Dict:
        """
        Processa dados coletados e salva no banco
        
        Args:
            data: Dados retornados pela API
            
        Returns:
            Dict com resultado do processamento
        """
        summary = data['summary']
        
        logger.info("\n" + "="*80)
        logger.info("📊 PROCESSANDO DADOS")
        logger.info("="*80)
        
        result = {
            'success': True,
            'processed': {
                'locations': 0,
                'tournaments': 0,
                'matches': 0,
                'teams': 0
            },
            'errors': [],
            'timestamp': datetime.now().isoformat()
        }
        
        # 1. Processar locations
        if data['locations']:
            try:
                logger.info(f"\n[1/4] Processando {len(data['locations'])} locations...")
                processed = self._process_locations(data['locations'])
                result['processed']['locations'] = processed
                logger.info(f"✅ {processed} location(s) processada(s)")
            except Exception as e:
                logger.error(f"❌ Erro ao processar locations: {e}")
                result['errors'].append(f"Locations: {str(e)}")
        
        # 2. Processar torneios
        if data['tournaments']:
            try:
                logger.info(f"\n[2/4] Processando {len(data['tournaments'])} torneios...")
                processed = self._process_tournaments(data['tournaments'])
                result['processed']['tournaments'] = processed
                logger.info(f"✅ {processed} torneio(s) processado(s)")
            except Exception as e:
                logger.error(f"❌ Erro ao processar torneios: {e}")
                result['errors'].append(f"Tournaments: {str(e)}")
        else:
            logger.info("\n[2/4] ⏰ Nenhum torneio para processar")
        
        # 3. Processar partidas
        if data['matches']:
            try:
                logger.info(f"\n[3/4] Processando {len(data['matches'])} partidas...")
                processed = self._process_matches(data['matches'])
                result['processed']['matches'] = processed
                logger.info(f"✅ {processed} partida(s) processada(s)")
            except Exception as e:
                logger.error(f"❌ Erro ao processar partidas: {e}")
                result['errors'].append(f"Matches: {str(e)}")
        else:
            logger.info("\n[3/4] ⏰ Nenhuma partida para processar")
        
        # 4. Processar teams (opcional - apenas se necessário)
        if data['teams'] and len(data['teams']) < 50:  # Processar apenas se mudou
            try:
                logger.info(f"\n[4/4] Processando {len(data['teams'])} teams...")
                processed = self._process_teams(data['teams'])
                result['processed']['teams'] = processed
                logger.info(f"✅ {processed} team(s) processado(s)")
            except Exception as e:
                logger.error(f"❌ Erro ao processar teams: {e}")
                result['errors'].append(f"Teams: {str(e)}")
        else:
            logger.info(f"\n[4/4] Teams já processados ({len(data['teams'])} no total)")
        
        # Log final
        logger.info("\n" + "="*80)
        logger.info("✅ PROCESSAMENTO CONCLUÍDO")
        logger.info("="*80)
        logger.info(f"   Locations: {result['processed']['locations']}")
        logger.info(f"   Torneios: {result['processed']['tournaments']}")
        logger.info(f"   Partidas: {result['processed']['matches']}")
        logger.info(f"   Teams: {result['processed']['teams']}")
        
        if result['errors']:
            logger.warning(f"   Erros: {len(result['errors'])}")
            for error in result['errors']:
                logger.warning(f"      - {error}")
        
        logger.info("="*80)
        
        return result
    
    def _process_locations(self, locations: List[Dict]) -> int:
        """
        Processa e salva locations no banco
        
        Args:
            locations: Lista de locations da API
            
        Returns:
            Número de locations processadas
        """
        # TODO: Implementar salvamento no banco de dados
        # from models import Location
        
        processed = 0
        
        for loc in locations:
            try:
                loc_id = loc.get('id')
                name = loc.get('token_international') or loc.get('token')
                
                if not loc_id or not name:
                    logger.warning(f"Location inválida: {loc}")
                    continue
                
                # Salvar no banco (exemplo)
                # Location.objects.update_or_create(
                #     id=loc_id,
                #     defaults={
                #         'name': name,
                #         'token': loc.get('token'),
                #         'color': loc.get('color'),
                #         'status_id': loc.get('status_id'),
                #         'updated_at': datetime.now()
                #     }
                # )
                
                logger.debug(f"   ✓ Location {loc_id}: {name}")
                processed += 1
                
            except Exception as e:
                logger.error(f"   ✗ Erro ao processar location {loc.get('id')}: {e}")
        
        return processed
    
    def _process_tournaments(self, tournaments: List[Dict]) -> int:
        """
        Processa e salva torneios no banco
        
        Args:
            tournaments: Lista de torneios da API
            
        Returns:
            Número de torneios processados
        """
        # TODO: Implementar salvamento no banco de dados
        # from models import Tournament
        
        processed = 0
        
        for tournament in tournaments:
            try:
                tournament_id = tournament.get('id')
                name = tournament.get('name') or tournament.get('token')
                
                if not tournament_id:
                    logger.warning(f"Torneio inválido: {tournament}")
                    continue
                
                # Salvar no banco (exemplo)
                # Tournament.objects.update_or_create(
                #     id=tournament_id,
                #     defaults={
                #         'name': name,
                #         'status': tournament.get('status'),
                #         'location_id': tournament.get('location', {}).get('id'),
                #         'data': tournament,
                #         'updated_at': datetime.now()
                #     }
                # )
                
                logger.debug(f"   ✓ Torneio {tournament_id}: {name}")
                processed += 1
                
            except Exception as e:
                logger.error(f"   ✗ Erro ao processar torneio {tournament.get('id')}: {e}")
        
        return processed
    
    def _process_matches(self, matches: List[Dict]) -> int:
        """
        Processa e salva partidas no banco
        
        Args:
            matches: Lista de partidas da API
            
        Returns:
            Número de partidas processadas
        """
        # TODO: Implementar salvamento no banco de dados
        # from models import Match
        
        processed = 0
        
        for match in matches:
            try:
                match_id = match.get('id')
                tournament_id = match.get('tournament_id') or match.get('tournamentId')
                
                if not match_id:
                    logger.warning(f"Partida inválida: {match}")
                    continue
                
                # Salvar no banco (exemplo)
                # Match.objects.update_or_create(
                #     id=match_id,
                #     defaults={
                #         'tournament_id': tournament_id,
                #         'team1': match.get('team1'),
                #         'team2': match.get('team2'),
                #         'score': match.get('score'),
                #         'status': match.get('status'),
                #         'start_time': match.get('start_time'),
                #         'data': match,
                #         'updated_at': datetime.now()
                #     }
                # )
                
                logger.debug(f"   ✓ Partida {match_id}")
                processed += 1
                
            except Exception as e:
                logger.error(f"   ✗ Erro ao processar partida {match.get('id')}: {e}")
        
        return processed
    
    def _process_teams(self, teams: List[Dict]) -> int:
        """
        Processa e salva teams no banco
        
        Args:
            teams: Lista de teams da API
            
        Returns:
            Número de teams processados
        """
        # TODO: Implementar salvamento no banco de dados
        # from models import Team
        
        processed = 0
        
        for team in teams:
            try:
                team_id = team.get('id')
                name = team.get('token_international') or team.get('token')
                
                if not team_id or not name:
                    continue
                
                # Salvar no banco (exemplo)
                # Team.objects.update_or_create(
                #     id=team_id,
                #     defaults={
                #         'name': name,
                #         'token': team.get('token'),
                #         'updated_at': datetime.now()
                #     }
                # )
                
                logger.debug(f"   ✓ Team {team_id}: {name}")
                processed += 1
                
            except Exception as e:
                logger.error(f"   ✗ Erro ao processar team {team.get('id')}: {e}")
        
        return processed
    
    def get_stats(self) -> Dict:
        """
        Retorna estatísticas do serviço
        
        Returns:
            Dict com estatísticas
        """
        return {
            **self.stats,
            'success_rate': (
                (self.stats['successful_runs'] / self.stats['total_runs'] * 100)
                if self.stats['total_runs'] > 0 else 0
            )
        }
    
    def should_run(self) -> bool:
        """
        Verifica se deve executar scraping agora
        Considera horário de jogos
        
        Returns:
            True se deve executar, False caso contrário
        """
        now = datetime.utcnow()
        hour = now.hour
        
        # Horário provável de torneios: 10h-23h UTC
        if 10 <= hour <= 23:
            return True
        
        # Fora do horário, verificar menos frequentemente
        # Apenas se já passou muito tempo sem torneios
        if self.stats['consecutive_empty'] > 50:  # Mais de 50 verificações vazias
            logger.debug("Muitas verificações vazias, reduzindo frequência")
            return False
        
        return True


# Exemplo de uso standalone
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    service = ScraperService()
    
    # Executar scraping
    result = service.run_scraping()
    
    # Mostrar resultado
    print("\n" + "="*80)
    print("RESULTADO DO SCRAPING")
    print("="*80)
    print(f"Sucesso: {result['success']}")
    print(f"Processados:")
    for key, value in result.get('processed', {}).items():
        print(f"  {key}: {value}")
    
    if result.get('errors'):
        print(f"\nErros: {len(result['errors'])}")
        for error in result['errors']:
            print(f"  - {error}")
    
    # Estatísticas
    stats = service.get_stats()
    print(f"\nEstatísticas:")
    print(f"  Total de execuções: {stats['total_runs']}")
    print(f"  Bem-sucedidas: {stats['successful_runs']}")
    print(f"  Taxa de sucesso: {stats['success_rate']:.1f}%")
    print("="*80)