import pandas as pd
from datetime import datetime, timedelta
from models import Match, Player, get_session
from sqlalchemy import func, and_, desc
import logging

logger = logging.getLogger('DataAnalyzer')


class DataAnalyzer:
    """
    Classe para análise de dados das partidas e jogadores
    """
    
    def __init__(self):
        self.session = None
    
    def _get_session(self):
        """Obtém uma sessão do banco de dados"""
        if not self.session:
            self.session = get_session()
        return self.session
    
    def close_session(self):
        """Fecha a sessão do banco de dados"""
        if self.session:
            self.session.close()
            self.session = None
    
    def get_matches_dataframe(self, days=7):
        """
        Retorna um DataFrame com partidas dos últimos N dias
        """
        try:
            session = self._get_session()
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            matches = session.query(Match).filter(
                Match.created_at >= cutoff_date
            ).all()
            
            if not matches:
                return pd.DataFrame()
            
            data = [m.to_dict() for m in matches]
            df = pd.DataFrame(data)
            
            return df
            
        except Exception as e:
            logger.error(f"Erro ao gerar DataFrame: {e}")
            return pd.DataFrame()
    
    def get_player_statistics(self, player_name=None):
        """
        Retorna estatísticas de um jogador específico ou todos
        """
        try:
            session = self._get_session()
            
            if player_name:
                player = session.query(Player).filter_by(name=player_name).first()
                if player:
                    return player.to_dict()
                return None
            else:
                players = session.query(Player).all()
                return [p.to_dict() for p in players]
            
        except Exception as e:
            logger.error(f"Erro ao buscar estatísticas: {e}")
            return None
    
    def get_top_players(self, metric='wins', limit=10):
        """
        Retorna os top jogadores por métrica específica
        """
        try:
            session = self._get_session()
            
            if metric == 'wins':
                players = session.query(Player).order_by(desc(Player.wins)).limit(limit).all()
            elif metric == 'total_matches':
                players = session.query(Player).order_by(desc(Player.total_matches)).limit(limit).all()
            elif metric == 'goals':
                players = session.query(Player).order_by(desc(Player.goals_scored)).limit(limit).all()
            elif metric == 'win_rate':
                # Calcula win rate e ordena
                players = session.query(Player).filter(Player.total_matches >= 5).all()
                players.sort(key=lambda p: (p.wins / p.total_matches) if p.total_matches > 0 else 0, reverse=True)
                players = players[:limit]
            else:
                return []
            
            return [p.to_dict() for p in players]
            
        except Exception as e:
            logger.error(f"Erro ao buscar top players: {e}")
            return []
    
    def get_match_statistics(self, days=7):
        """
        Retorna estatísticas gerais das partidas
        """
        try:
            session = self._get_session()
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            total_matches = session.query(func.count(Match.id)).filter(
                Match.created_at >= cutoff_date
            ).scalar() or 0
            
            # Contar partidas por status
            live_matches = session.query(func.count(Match.id)).filter(
                and_(
                    Match.status == 'live',
                    Match.created_at >= cutoff_date
                )
            ).scalar() or 0
            
            finished_matches = session.query(func.count(Match.id)).filter(
                and_(
                    Match.status == 'finished',
                    Match.created_at >= cutoff_date
                )
            ).scalar() or 0
            
            # Partidas por dia
            matches_by_day = {}
            for i in range(days):
                date = (datetime.utcnow() - timedelta(days=i)).date()
                count = session.query(func.count(Match.id)).filter(
                    func.date(Match.created_at) == date
                ).scalar() or 0
                matches_by_day[str(date)] = count
            
            return {
                'total_matches': total_matches,
                'live_matches': live_matches,
                'finished_matches': finished_matches,
                'matches_by_day': matches_by_day,
                'period_days': days
            }
            
        except Exception as e:
            logger.error(f"Erro ao calcular estatísticas: {e}")
            return {}
    
    def get_head_to_head(self, player1, player2):
        """
        Retorna estatísticas de confronto direto entre dois jogadores
        """
        try:
            session = self._get_session()
            
            # Buscar partidas onde os dois jogadores se enfrentaram
            matches = session.query(Match).filter(
                or_(
                    and_(Match.player1 == player1, Match.player2 == player2),
                    and_(Match.player1 == player2, Match.player2 == player1)
                )
            ).all()
            
            if not matches:
                return None
            
            stats = {
                'total_matches': len(matches),
                'player1_wins': 0,
                'player2_wins': 0,
                'draws': 0,
                'player1': player1,
                'player2': player2
            }
            
            for match in matches:
                try:
                    score1, score2 = map(int, match.score.split('-'))
                    
                    if match.player1 == player1:
                        if score1 > score2:
                            stats['player1_wins'] += 1
                        elif score1 < score2:
                            stats['player2_wins'] += 1
                        else:
                            stats['draws'] += 1
                    else:
                        if score2 > score1:
                            stats['player1_wins'] += 1
                        elif score2 < score1:
                            stats['player2_wins'] += 1
                        else:
                            stats['draws'] += 1
                except:
                    continue
            
            return stats
            
        except Exception as e:
            logger.error(f"Erro ao calcular H2H: {e}")
            return None
    
    def generate_report(self, days=7):
        """
        Gera um relatório completo das estatísticas
        """
        try:
            report = {
                'generated_at': datetime.utcnow().isoformat(),
                'period_days': days,
                'match_statistics': self.get_match_statistics(days),
                'top_players': {
                    'by_wins': self.get_top_players('wins', 5),
                    'by_matches': self.get_top_players('total_matches', 5),
                    'by_goals': self.get_top_players('goals', 5),
                    'by_win_rate': self.get_top_players('win_rate', 5)
                }
            }
            
            return report
            
        except Exception as e:
            logger.error(f"Erro ao gerar relatório: {e}")
            return {}
    
    def export_to_excel(self, filename='fifa25_report.xlsx', days=7):
        """
        Exporta dados para arquivo Excel
        """
        try:
            df_matches = self.get_matches_dataframe(days)
            df_players = pd.DataFrame(self.get_player_statistics())
            
            with pd.ExcelWriter(filename, engine='openpyxl') as writer:
                df_matches.to_excel(writer, sheet_name='Partidas', index=False)
                df_players.to_excel(writer, sheet_name='Jogadores', index=False)
            
            logger.info(f"✅ Relatório exportado: {filename}")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao exportar para Excel: {e}")
            return False


# Teste
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    analyzer = DataAnalyzer()
    
    print("\n📊 Gerando relatório...")
    report = analyzer.generate_report(days=7)
    
    print(f"\n📈 Estatísticas dos últimos 7 dias:")
    print(f"  Total de partidas: {report['match_statistics']['total_matches']}")
    print(f"  Partidas ao vivo: {report['match_statistics']['live_matches']}")
    print(f"  Partidas finalizadas: {report['match_statistics']['finished_matches']}")
    
    print("\n🏆 Top 5 Jogadores por Vitórias:")
    for i, player in enumerate(report['top_players']['by_wins'], 1):
        print(f"  {i}. {player['name']} - {player['wins']} vitórias")
    
    analyzer.close_session()