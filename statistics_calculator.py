# statistics_calculator.py - NOVO ARQUIVO
# Calcula estatísticas dos jogadores baseado nas partidas finalizadas

import logging
from collections import defaultdict
from sqlalchemy import func

logger = logging.getLogger(__name__)

class StatisticsCalculator:
    """
    Calcula e mantém estatísticas atualizadas dos jogadores
    """
    
    def __init__(self):
        self.cache = {}
        self.cache_timestamp = None
    
    def calculate_player_statistics(self, player_name=None, stadium=None):
        """
        Calcula estatísticas de um jogador ou todos os jogadores
        
        Args:
            player_name: nome do jogador (None para todos)
            stadium: filtrar por estádio (None para todos)
            
        Returns:
            dict com estatísticas
        """
        from models import Match
        
        try:
            # Query base: apenas partidas finalizadas
            query = Match.query.filter_by(status='finished')
            
            # Filtros opcionais
            if stadium:
                query = query.filter_by(location=stadium)
            
            matches = query.all()
            
            # Dicionário para armazenar stats
            stats = defaultdict(lambda: {
                'matches': 0,
                'wins': 0,
                'losses': 0,
                'draws': 0,
                'goals_scored': 0,
                'goals_conceded': 0,
                'goal_difference': 0,
                'win_rate': 0.0,
                'stadiums': set(),
                'tournaments': set()
            })
            
            # Processa cada partida
            for match in matches:
                # Valida dados
                if not match.home_player or not match.away_player:
                    continue
                if match.final_score_home is None or match.final_score_away is None:
                    continue
                
                home_player = match.home_player
                away_player = match.away_player
                home_score = match.final_score_home
                away_score = match.final_score_away
                
                # Atualiza estatísticas do jogador da casa
                stats[home_player]['matches'] += 1
                stats[home_player]['goals_scored'] += home_score
                stats[home_player]['goals_conceded'] += away_score
                stats[home_player]['stadiums'].add(match.location)
                if match.tournament:
                    stats[home_player]['tournaments'].add(match.tournament)
                
                if home_score > away_score:
                    stats[home_player]['wins'] += 1
                elif home_score < away_score:
                    stats[home_player]['losses'] += 1
                else:
                    stats[home_player]['draws'] += 1
                
                # Atualiza estatísticas do jogador visitante
                stats[away_player]['matches'] += 1
                stats[away_player]['goals_scored'] += away_score
                stats[away_player]['goals_conceded'] += home_score
                stats[away_player]['stadiums'].add(match.location)
                if match.tournament:
                    stats[away_player]['tournaments'].add(match.tournament)
                
                if away_score > home_score:
                    stats[away_player]['wins'] += 1
                elif away_score < home_score:
                    stats[away_player]['losses'] += 1
                else:
                    stats[away_player]['draws'] += 1
            
            # Calcula métricas derivadas
            for player, data in stats.items():
                data['goal_difference'] = data['goals_scored'] - data['goals_conceded']
                
                if data['matches'] > 0:
                    data['win_rate'] = (data['wins'] / data['matches']) * 100
                
                # Converte sets para listas para JSON
                data['stadiums'] = list(data['stadiums'])
                data['tournaments'] = list(data['tournaments'])
            
            # Filtra por jogador específico se solicitado
            if player_name:
                return {player_name: stats.get(player_name, stats[player_name])}
            
            return dict(stats)
            
        except Exception as e:
            logger.error(f"Erro ao calcular estatísticas: {e}")
            return {}
    
    def get_statistics_by_stadium(self):
        """
        Retorna estatísticas agrupadas por estádio
        
        Returns:
            dict: {
                'Anfield': {
                    'player1': {...},
                    'player2': {...}
                },
                'Hillsborough': {...}
            }
        """
        from models import Match
        
        try:
            # Busca todos os estádios
            stadiums = Match.query.with_entities(Match.location)\
                                 .filter_by(status='finished')\
                                 .distinct()\
                                 .all()
            
            result = {}
            
            for (stadium,) in stadiums:
                if stadium:
                    result[stadium] = self.calculate_player_statistics(stadium=stadium)
            
            return result
            
        except Exception as e:
            logger.error(f"Erro ao obter estatísticas por estádio: {e}")
            return {}
    
    def get_top_scorers(self, limit=10, stadium=None):
        """
        Retorna maiores artilheiros
        
        Args:
            limit: número de jogadores a retornar
            stadium: filtrar por estádio
            
        Returns:
            list de dicts com jogadores ordenados por gols
        """
        stats = self.calculate_player_statistics(stadium=stadium)
        
        # Ordena por gols marcados
        top_scorers = sorted(
            stats.items(),
            key=lambda x: x[1]['goals_scored'],
            reverse=True
        )[:limit]
        
        return [
            {
                'player': player,
                'goals': data['goals_scored'],
                'matches': data['matches'],
                'avg_goals_per_match': round(data['goals_scored'] / data['matches'], 2) if data['matches'] > 0 else 0
            }
            for player, data in top_scorers
        ]
    
    def get_top_winners(self, limit=10, stadium=None):
        """
        Retorna jogadores com mais vitórias
        """
        stats = self.calculate_player_statistics(stadium=stadium)
        
        # Ordena por vitórias
        top_winners = sorted(
            stats.items(),
            key=lambda x: (x[1]['wins'], x[1]['win_rate']),
            reverse=True
        )[:limit]
        
        return [
            {
                'player': player,
                'wins': data['wins'],
                'matches': data['matches'],
                'win_rate': round(data['win_rate'], 1)
            }
            for player, data in top_winners
        ]
    
    def get_player_head_to_head(self, player1, player2):
        """
        Retorna confronto direto entre dois jogadores
        
        Returns:
            dict com estatísticas do confronto
        """
        from models import Match
        
        try:
            # Busca partidas entre os dois jogadores
            matches = Match.query.filter(
                Match.status == 'finished',
                ((Match.home_player == player1) & (Match.away_player == player2)) |
                ((Match.home_player == player2) & (Match.away_player == player1))
            ).all()
            
            stats = {
                'total_matches': len(matches),
                f'{player1}_wins': 0,
                f'{player2}_wins': 0,
                'draws': 0,
                f'{player1}_goals': 0,
                f'{player2}_goals': 0,
                'matches_details': []
            }
            
            for match in matches:
                home_score = match.final_score_home
                away_score = match.final_score_away
                
                # Identifica quem é player1 e player2 na partida
                if match.home_player == player1:
                    stats[f'{player1}_goals'] += home_score
                    stats[f'{player2}_goals'] += away_score
                    
                    if home_score > away_score:
                        stats[f'{player1}_wins'] += 1
                    elif away_score > home_score:
                        stats[f'{player2}_wins'] += 1
                    else:
                        stats['draws'] += 1
                else:
                    stats[f'{player1}_goals'] += away_score
                    stats[f'{player2}_goals'] += home_score
                    
                    if away_score > home_score:
                        stats[f'{player1}_wins'] += 1
                    elif home_score > away_score:
                        stats[f'{player2}_wins'] += 1
                    else:
                        stats['draws'] += 1
                
                # Adiciona detalhes da partida
                stats['matches_details'].append({
                    'date': match.match_date.strftime('%d/%m/%Y %H:%M') if match.match_date else 'N/A',
                    'score': f"{home_score} x {away_score}",
                    'winner': match.winner,
                    'tournament': match.tournament
                })
            
            return stats
            
        except Exception as e:
            logger.error(f"Erro ao calcular head-to-head: {e}")
            return {}
    
    def get_tournament_statistics(self, tournament_name=None):
        """
        Retorna estatísticas por torneio
        """
        from models import Match
        
        try:
            query = Match.query.filter_by(status='finished')
            
            if tournament_name:
                query = query.filter_by(tournament=tournament_name)
            
            matches = query.all()
            
            stats = {
                'total_matches': len(matches),
                'total_goals': 0,
                'avg_goals_per_match': 0,
                'highest_scoring_match': None,
                'most_wins': None
            }
            
            player_wins = defaultdict(int)
            total_goals = 0
            highest_score = 0
            highest_match = None
            
            for match in matches:
                if match.final_score_home is not None and match.final_score_away is not None:
                    match_total = match.final_score_home + match.final_score_away
                    total_goals += match_total
                    
                    if match_total > highest_score:
                        highest_score = match_total
                        highest_match = {
                            'home_player': match.home_player,
                            'away_player': match.away_player,
                            'score': f"{match.final_score_home} x {match.final_score_away}",
                            'total_goals': match_total
                        }
                    
                    if match.winner and match.winner != 'Empate':
                        player_wins[match.winner] += 1
            
            stats['total_goals'] = total_goals
            stats['avg_goals_per_match'] = round(total_goals / len(matches), 2) if matches else 0
            stats['highest_scoring_match'] = highest_match
            
            if player_wins:
                most_wins_player = max(player_wins.items(), key=lambda x: x[1])
                stats['most_wins'] = {
                    'player': most_wins_player[0],
                    'wins': most_wins_player[1]
                }
            
            return stats
            
        except Exception as e:
            logger.error(f"Erro ao calcular estatísticas de torneio: {e}")
            return {}
    
    def refresh_cache(self):
        """
        Atualiza cache de estatísticas
        """
        from datetime import datetime
        
        self.cache = {
            'all_players': self.calculate_player_statistics(),
            'by_stadium': self.get_statistics_by_stadium(),
            'top_scorers': self.get_top_scorers(),
            'top_winners': self.get_top_winners()
        }
        
        self.cache_timestamp = datetime.now()
        logger.info("✅ Cache de estatísticas atualizado")
    
    def get_cached_statistics(self, force_refresh=False):
        """
        Retorna estatísticas do cache (atualiza se necessário)
        """
        from datetime import datetime, timedelta
        
        # Atualiza cache se:
        # 1. Nunca foi criado
        # 2. Tem mais de 5 minutos
        # 3. Force refresh
        if (force_refresh or 
            not self.cache or 
            not self.cache_timestamp or
            datetime.now() - self.cache_timestamp > timedelta(minutes=5)):
            
            self.refresh_cache()
        
        return self.cache


# ============================================================
# INTEGRAÇÃO COM APP.PY
# ============================================================

"""
# No app.py:

from statistics_calculator import StatisticsCalculator

# Instanciar calculadora
stats_calculator = StatisticsCalculator()

# Rota para estatísticas
@app.route('/statistics')
def statistics_page():
    # Obtém estatísticas por estádio
    stats_by_stadium = stats_calculator.get_statistics_by_stadium()
    
    return render_template('statistics.html', stats=stats_by_stadium)

# API para estatísticas
@app.route('/api/statistics/player/<player_name>')
def api_player_stats(player_name):
    stats = stats_calculator.calculate_player_statistics(player_name=player_name)
    return jsonify(stats)

@app.route('/api/statistics/top-scorers')
def api_top_scorers():
    limit = request.args.get('limit', 10, type=int)
    stadium = request.args.get('stadium')
    
    scorers = stats_calculator.get_top_scorers(limit=limit, stadium=stadium)
    return jsonify(scorers)

@app.route('/api/statistics/head-to-head')
def api_head_to_head():
    player1 = request.args.get('player1')
    player2 = request.args.get('player2')
    
    if not player1 or not player2:
        return jsonify({'error': 'Parâmetros player1 e player2 são obrigatórios'}), 400
    
    h2h = stats_calculator.get_player_head_to_head(player1, player2)
    return jsonify(h2h)

# Job para atualizar cache
def update_statistics_cache():
    stats_calculator.refresh_cache()

scheduler.add_job(
    func=update_statistics_cache,
    trigger="interval",
    minutes=5,
    id="update_stats_cache",
    name="Atualizar Cache de Estatísticas",
    replace_existing=True
)

# Quando partida finalizar
def on_match_finished(match):
    # Força atualização do cache
    stats_calculator.refresh_cache()
"""
