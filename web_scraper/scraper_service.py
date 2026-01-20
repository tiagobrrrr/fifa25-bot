from datetime import datetime
import logging
import time
from web_scraper.api_client import FIFA25APIClient

logger = logging.getLogger(__name__)


class ScraperService:
    """Serviço responsável por executar o scraping e processar os dados"""
    
    def __init__(self, db, models):
        """
        Args:
            db: Instância do SQLAlchemy
            models: Tupla com (Match, Tournament, Player, ScraperLog)
        """
        self.db = db
        self.Match, self.Tournament, self.Player, self.ScraperLog = models
        self.api_client = FIFA25APIClient()
    
    def run(self):
        """
        Executa uma rodada completa de scraping
        
        Returns:
            dict: Estatísticas da execução
        """
        start_time = time.time()
        stats = {
            'matches_found': 0,
            'matches_new': 0,
            'matches_updated': 0,
            'tournaments_found': 0,
            'tournaments_new': 0,
            'status': 'success',
            'message': ''
        }
        
        try:
            logger.info("=" * 80)
            logger.info("🔄 Executando scraping...")
            logger.info("=" * 80)
            
            # 1. Coletar partidas da API
            matches_data, tournaments_data = self.api_client.get_all_active_matches()
            
            stats['matches_found'] = len(matches_data)
            stats['tournaments_found'] = len(tournaments_data)
            
            if not matches_data:
                logger.warning("⚠️  Nenhuma partida encontrada")
                stats['message'] = "Nenhuma partida encontrada"
                self._save_log(stats, time.time() - start_time)
                return stats
            
            # 2. Processar torneios
            logger.info(f"\n📋 Processando {len(tournaments_data)} torneios...")
            stats['tournaments_new'] = self._process_tournaments(tournaments_data)
            
            # 3. Processar partidas
            logger.info(f"\n🎮 Processando {len(matches_data)} partidas...")
            new_count, updated_count = self._process_matches(matches_data)
            
            stats['matches_new'] = new_count
            stats['matches_updated'] = updated_count
            
            # 4. Commit no banco
            self.db.session.commit()
            
            # 5. Estatísticas finais
            execution_time = time.time() - start_time
            
            logger.info("\n" + "=" * 80)
            logger.info("✅ Scraping concluído")
            logger.info(f"📊 Partidas: {new_count} novas, {updated_count} atualizadas")
            logger.info(f"📋 Torneios: {stats['tournaments_new']} novos")
            logger.info(f"⏱️  Tempo de execução: {execution_time:.2f}s")
            logger.info("=" * 80)
            
            stats['message'] = f"{new_count} novas, {updated_count} atualizadas"
            
            # Salvar log
            self._save_log(stats, execution_time)
            
            return stats
            
        except Exception as e:
            logger.error(f"❌ Erro no scraping: {e}", exc_info=True)
            self.db.session.rollback()
            
            stats['status'] = 'error'
            stats['message'] = str(e)
            
            # Salvar log de erro
            self._save_log(stats, time.time() - start_time)
            
            return stats
    
    def _process_tournaments(self, tournaments_data):
        """
        Processa e salva torneios no banco
        
        Args:
            tournaments_data (list): Lista de dados de torneios
            
        Returns:
            int: Número de novos torneios
        """
        new_count = 0
        
        for tournament_data in tournaments_data:
            try:
                tournament_id = tournament_data.get('id')
                
                if not tournament_id:
                    continue
                
                # Verificar se já existe
                existing = self.Tournament.query.filter_by(tournament_id=tournament_id).first()
                
                if existing:
                    # Atualizar status se mudou
                    if existing.status_id != tournament_data.get('status_id'):
                        existing.status_id = tournament_data.get('status_id')
                        existing.updated_at = datetime.utcnow()
                else:
                    # Criar novo torneio
                    new_tournament = self.Tournament.from_api_data(tournament_data)
                    self.db.session.add(new_tournament)
                    new_count += 1
                    
                    logger.debug(f"   ✅ Novo torneio: {new_tournament.name_international}")
            
            except Exception as e:
                logger.error(f"   ❌ Erro ao processar torneio: {e}")
                continue
        
        return new_count
    
    def _process_matches(self, matches_data):
        """
        Processa e salva partidas no banco
        
        Args:
            matches_data (list): Lista de dados de partidas
            
        Returns:
            tuple: (novas, atualizadas)
        """
        new_count = 0
        updated_count = 0
        
        for match_data in matches_data:
            try:
                match_id = match_data.get('id')
                
                if not match_id:
                    logger.warning(f"   ⚠️  Partida sem ID: {match_data}")
                    continue
                
                # Verificar se já existe
                existing = self.Match.query.filter_by(match_id=match_id).first()
                
                if existing:
                    # Verificar se houve mudanças
                    p1_score = match_data.get('participant1', {}).get('score', 0)
                    p2_score = match_data.get('participant2', {}).get('score', 0)
                    status_id = match_data.get('status_id')
                    
                    needs_update = (
                        existing.player1_score != p1_score or
                        existing.player2_score != p2_score or
                        existing.status_id != status_id
                    )
                    
                    if needs_update:
                        # Atualizar partida
                        existing.player1_score = p1_score
                        existing.player2_score = p2_score
                        existing.status_id = status_id
                        existing.updated_at = datetime.utcnow()
                        
                        updated_count += 1
                        
                        logger.info(f"   🔄 Atualizada: {existing.player1_nickname} {p1_score}-{p2_score} {existing.player2_nickname}")
                        
                        # Se a partida foi finalizada, atualizar estatísticas
                        if status_id == 3 and existing.status_id != 3:
                            self._update_player_stats(match_data)
                else:
                    # Criar nova partida
                    new_match = self.Match.from_api_data(match_data)
                    self.db.session.add(new_match)
                    new_count += 1
                    
                    logger.info(f"   ✅ Nova: {new_match.player1_nickname} vs {new_match.player2_nickname} ({new_match.location})")
                    
                    # Se já está finalizada, atualizar estatísticas
                    if match_data.get('status_id') == 3:
                        self._update_player_stats(match_data)
            
            except Exception as e:
                logger.error(f"   ❌ Erro ao processar partida {match_id}: {e}")
                continue
        
        return new_count, updated_count
    
    def _update_player_stats(self, match_data):
        """
        Atualiza estatísticas dos jogadores após uma partida
        
        Args:
            match_data (dict): Dados da partida
        """
        try:
            p1 = match_data.get('participant1', {})
            p2 = match_data.get('participant2', {})
            
            p1_nickname = p1.get('nickname')
            p2_nickname = p2.get('nickname')
            
            p1_score = p1.get('score', 0)
            p2_score = p2.get('score', 0)
            
            if not p1_nickname or not p2_nickname:
                return
            
            # Atualizar jogador 1
            player1 = self.Player.query.filter_by(nickname=p1_nickname).first()
            if not player1:
                player1 = self.Player(nickname=p1_nickname)
                self.db.session.add(player1)
            
            player1.last_seen = datetime.utcnow()
            player1.total_matches += 1
            player1.goals_for += p1_score
            player1.goals_against += p2_score
            
            if p1_score > p2_score:
                player1.wins += 1
            elif p1_score < p2_score:
                player1.losses += 1
            else:
                player1.draws += 1
            
            # Atualizar jogador 2
            player2 = self.Player.query.filter_by(nickname=p2_nickname).first()
            if not player2:
                player2 = self.Player(nickname=p2_nickname)
                self.db.session.add(player2)
            
            player2.last_seen = datetime.utcnow()
            player2.total_matches += 1
            player2.goals_for += p2_score
            player2.goals_against += p1_score
            
            if p2_score > p1_score:
                player2.wins += 1
            elif p2_score < p1_score:
                player2.losses += 1
            else:
                player2.draws += 1
            
            logger.debug(f"   📊 Stats atualizadas: {p1_nickname}, {p2_nickname}")
            
        except Exception as e:
            logger.error(f"❌ Erro ao atualizar estatísticas: {e}")
    
    def _save_log(self, stats, execution_time):
        """
        Salva log da execução
        
        Args:
            stats (dict): Estatísticas da execução
            execution_time (float): Tempo de execução em segundos
        """
        try:
            log = self.ScraperLog(
                timestamp=datetime.utcnow(),
                status=stats['status'],
                message=stats['message'],
                matches_found=stats['matches_found'],
                matches_new=stats['matches_new'],
                matches_updated=stats['matches_updated'],
                execution_time=execution_time
            )
            
            self.db.session.add(log)
            self.db.session.commit()
            
        except Exception as e:
            logger.error(f"❌ Erro ao salvar log: {e}")
            self.db.session.rollback()