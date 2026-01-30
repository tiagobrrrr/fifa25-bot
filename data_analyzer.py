"""
Analisador de Dados - FIFA 25 Bot
Análise e geração de estatísticas
"""

import logging
from datetime import datetime, timedelta
from collections import Counter
import json
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class DataAnalyzer:
    """Classe para análise de dados das partidas"""
    
    def __init__(self):
        logger.info("✅ DataAnalyzer inicializado")
    
    def analyze_matches(self, matches: List[Dict]) -> Dict:
        """
        Analisa uma lista de partidas e retorna estatísticas
        
        Args:
            matches: Lista de partidas
        
        Returns:
            Dicionário com estatísticas
        """
        try:
            if not matches:
                return self._empty_analysis()
            
            analysis = {
                'total_matches': len(matches),
                'by_status': self._count_by_status(matches),
                'by_location': self._count_by_location(matches),
                'by_tournament': self._count_by_tournament(matches),
                'top_players': self._get_top_players(matches),
                'top_teams': self._get_top_teams(matches),
                'score_stats': self._analyze_scores(matches),
                'time_distribution': self._analyze_time_distribution(matches)
            }
            
            logger.info(f"✅ Análise concluída: {len(matches)} partidas")
            return analysis
            
        except Exception as e:
            logger.error(f"❌ Erro ao analisar partidas: {e}")
            return self._empty_analysis()
    
    def _empty_analysis(self) -> Dict:
        """Retorna estrutura vazia de análise"""
        return {
            'total_matches': 0,
            'by_status': {},
            'by_location': {},
            'by_tournament': {},
            'top_players': [],
            'top_teams': [],
            'score_stats': {},
            'time_distribution': {}
        }
    
    def _count_by_status(self, matches: List[Dict]) -> Dict:
        """Conta partidas por status"""
        statuses = {
            1: 'Planned',
            2: 'Live',
            3: 'Finished',
            4: 'Canceled'
        }
        
        counter = Counter([m.get('status_id', 1) for m in matches])
        
        return {
            statuses.get(status_id, 'Unknown'): count
            for status_id, count in counter.items()
        }
    
    def _count_by_location(self, matches: List[Dict]) -> Dict:
        """Conta partidas por location"""
        locations = []
        
        for match in matches:
            location = match.get('location', {})
            location_name = location.get('token_international') or location.get('token')
            if location_name:
                locations.append(location_name)
        
        counter = Counter(locations)
        return dict(counter.most_common(10))
    
    def _count_by_tournament(self, matches: List[Dict]) -> Dict:
        """Conta partidas por torneio"""
        tournaments = []
        
        for match in matches:
            tournament = match.get('tournament', {})
            tournament_name = tournament.get('token_international') or tournament.get('token')
            if tournament_name:
                tournaments.append(tournament_name)
        
        counter = Counter(tournaments)
        return dict(counter.most_common(10))
    
    def _get_top_players(self, matches: List[Dict], top_n: int = 10) -> List[Dict]:
        """Identifica jogadores mais ativos"""
        player_matches = {}
        player_info = {}
        
        for match in matches:
            # Processar jogador 1
            p1 = match.get('participant1', {})
            p1_id = p1.get('id')
            if p1_id:
                player_matches[p1_id] = player_matches.get(p1_id, 0) + 1
                if p1_id not in player_info:
                    player_info[p1_id] = {
                        'nickname': p1.get('nickname', 'Unknown'),
                        'photo': p1.get('photo')
                    }
            
            # Processar jogador 2
            p2 = match.get('participant2', {})
            p2_id = p2.get('id')
            if p2_id:
                player_matches[p2_id] = player_matches.get(p2_id, 0) + 1
                if p2_id not in player_info:
                    player_info[p2_id] = {
                        'nickname': p2.get('nickname', 'Unknown'),
                        'photo': p2.get('photo')
                    }
        
        # Ordenar e retornar top N
        sorted_players = sorted(
            player_matches.items(),
            key=lambda x: x[1],
            reverse=True
        )[:top_n]
        
        return [
            {
                'player_id': player_id,
                'nickname': player_info[player_id]['nickname'],
                'photo': player_info[player_id]['photo'],
                'matches': count
            }
            for player_id, count in sorted_players
        ]
    
    def _get_top_teams(self, matches: List[Dict], top_n: int = 10) -> List[Dict]:
        """Identifica times mais usados"""
        team_usage = {}
        
        for match in matches:
            # Time do jogador 1
            p1_team = match.get('participant1', {}).get('team', {})
            team1_name = p1_team.get('token_international') or p1_team.get('token')
            if team1_name:
                if team1_name not in team_usage:
                    team_usage[team1_name] = {
                        'name': team1_name,
                        'logo': p1_team.get('logo'),
                        'count': 0
                    }
                team_usage[team1_name]['count'] += 1
            
            # Time do jogador 2
            p2_team = match.get('participant2', {}).get('team', {})
            team2_name = p2_team.get('token_international') or p2_team.get('token')
            if team2_name:
                if team2_name not in team_usage:
                    team_usage[team2_name] = {
                        'name': team2_name,
                        'logo': p2_team.get('logo'),
                        'count': 0
                    }
                team_usage[team2_name]['count'] += 1
        
        # Ordenar e retornar top N
        sorted_teams = sorted(
            team_usage.values(),
            key=lambda x: x['count'],
            reverse=True
        )[:top_n]
        
        return sorted_teams
    
    def _analyze_scores(self, matches: List[Dict]) -> Dict:
        """Analisa estatísticas de placares"""
        scores = []
        total_goals = 0
        
        for match in matches:
            score1 = match.get('score1')
            score2 = match.get('score2')
            
            if score1 is not None and score2 is not None:
                scores.append((score1, score2))
                total_goals += score1 + score2
        
        if not scores:
            return {
                'average_goals': 0,
                'highest_scoring': None,
                'most_common_score': None,
                'total_goals': 0
            }
        
        avg_goals = round(total_goals / len(scores), 2)
        highest = max(scores, key=lambda x: x[0] + x[1])
        most_common = Counter(scores).most_common(1)[0][0] if scores else None
        
        return {
            'average_goals': avg_goals,
            'highest_scoring': f"{highest[0]}-{highest[1]}",
            'most_common_score': f"{most_common[0]}-{most_common[1]}" if most_common else None,
            'total_goals': total_goals
        }
    
    def _analyze_time_distribution(self, matches: List[Dict]) -> Dict:
        """Analisa distribuição de partidas ao longo do dia"""
        hours = []
        
        for match in matches:
            date_str = match.get('date')
            if date_str:
                try:
                    date_obj = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                    hours.append(date_obj.hour)
                except:
                    continue
        
        if not hours:
            return {}
        
        counter = Counter(hours)
        
        return {
            f"{hour:02d}:00": count
            for hour, count in sorted(counter.items())
        }
    
    def analyze_player_performance(self, player_id: int, matches: List[Dict]) -> Dict:
        """
        Analisa desempenho de um jogador específico
        
        Args:
            player_id: ID do jogador
            matches: Lista de partidas
        
        Returns:
            Dicionário com estatísticas do jogador
        """
        try:
            player_matches = []
            wins = 0
            losses = 0
            draws = 0
            goals_scored = 0
            goals_conceded = 0
            
            for match in matches:
                p1 = match.get('participant1', {})
                p2 = match.get('participant2', {})
                
                is_player1 = p1.get('id') == player_id
                is_player2 = p2.get('id') == player_id
                
                if not (is_player1 or is_player2):
                    continue
                
                player_matches.append(match)
                
                score1 = match.get('score1')
                score2 = match.get('score2')
                
                if score1 is not None and score2 is not None:
                    if is_player1:
                        goals_scored += score1
                        goals_conceded += score2
                        if score1 > score2:
                            wins += 1
                        elif score1 < score2:
                            losses += 1
                        else:
                            draws += 1
                    else:
                        goals_scored += score2
                        goals_conceded += score1
                        if score2 > score1:
                            wins += 1
                        elif score2 < score1:
                            losses += 1
                        else:
                            draws += 1
            
            total_matches = len(player_matches)
            win_rate = round((wins / total_matches * 100), 2) if total_matches > 0 else 0
            
            return {
                'player_id': player_id,
                'total_matches': total_matches,
                'wins': wins,
                'losses': losses,
                'draws': draws,
                'win_rate': win_rate,
                'goals_scored': goals_scored,
                'goals_conceded': goals_conceded,
                'goal_difference': goals_scored - goals_conceded,
                'avg_goals_per_match': round(goals_scored / total_matches, 2) if total_matches > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"❌ Erro ao analisar desempenho do jogador {player_id}: {e}")
            return {}
    
    def generate_daily_report(self, date: datetime, matches: List[Dict]) -> Dict:
        """
        Gera relatório diário
        
        Args:
            date: Data do relatório
            matches: Partidas do dia
        
        Returns:
            Dicionário com o relatório
        """
        try:
            analysis = self.analyze_matches(matches)
            
            report = {
                'date': date.strftime('%Y-%m-%d'),
                'generated_at': datetime.now().isoformat(),
                'summary': {
                    'total_matches': analysis['total_matches'],
                    'by_status': analysis['by_status']
                },
                'locations': analysis['by_location'],
                'tournaments': analysis['by_tournament'],
                'top_players': analysis['top_players'][:5],
                'top_teams': analysis['top_teams'][:5],
                'scores': analysis['score_stats'],
                'time_distribution': analysis['time_distribution']
            }
            
            logger.info(f"✅ Relatório diário gerado: {date.strftime('%Y-%m-%d')}")
            return report
            
        except Exception as e:
            logger.error(f"❌ Erro ao gerar relatório diário: {e}")
            return {}
    
    def export_to_dict(self, analysis: Dict) -> str:
        """
        Exporta análise para JSON string
        
        Args:
            analysis: Dicionário de análise
        
        Returns:
            String JSON
        """
        try:
            return json.dumps(analysis, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"❌ Erro ao exportar para JSON: {e}")
            return "{}"


# Teste standalone
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    analyzer = DataAnalyzer()
    
    # Mock de dados para teste
    mock_matches = [
        {
            'id': 1,
            'status_id': 3,
            'date': '2026-01-30T10:00:00Z',
            'location': {'token_international': 'Wembley'},
            'tournament': {'token_international': 'Nations League'},
            'participant1': {
                'id': 101,
                'nickname': 'Player1',
                'team': {'token_international': 'Brazil'}
            },
            'participant2': {
                'id': 102,
                'nickname': 'Player2',
                'team': {'token_international': 'Argentina'}
            },
            'score1': 3,
            'score2': 2
        },
        {
            'id': 2,
            'status_id': 2,
            'date': '2026-01-30T14:00:00Z',
            'location': {'token_international': 'Wembley'},
            'tournament': {'token_international': 'Nations League'},
            'participant1': {
                'id': 101,
                'nickname': 'Player1',
                'team': {'token_international': 'Brazil'}
            },
            'participant2': {
                'id': 103,
                'nickname': 'Player3',
                'team': {'token_international': 'France'}
            },
            'score1': 1,
            'score2': 1
        }
    ]
    
    print("\n" + "="*80)
    print("🧪 TESTANDO DATA ANALYZER")
    print("="*80 + "\n")
    
    # Teste 1: Análise geral
    print("1️⃣ Análise geral de partidas...")
    analysis = analyzer.analyze_matches(mock_matches)
    print(f"✅ Total de partidas: {analysis['total_matches']}")
    print(f"✅ Por status: {analysis['by_status']}")
    print(f"✅ Top jogadores: {len(analysis['top_players'])}")
    
    # Teste 2: Desempenho de jogador
    print("\n2️⃣ Análise de desempenho do jogador 101...")
    performance = analyzer.analyze_player_performance(101, mock_matches)
    print(f"✅ Partidas: {performance.get('total_matches', 0)}")
    print(f"✅ Vitórias: {performance.get('wins', 0)}")
    print(f"✅ Win Rate: {performance.get('win_rate', 0)}%")
    
    # Teste 3: Relatório diário
    print("\n3️⃣ Gerando relatório diário...")
    report = analyzer.generate_daily_report(datetime.now(), mock_matches)
    print(f"✅ Relatório gerado para: {report.get('date', 'N/A')}")
    
    print("\n" + "="*80)
    print("✅ TESTES CONCLUÍDOS")
    print("="*80 + "\n")