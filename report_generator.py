"""
Gerador de Relatórios - FIFA 25 Bot
Gera planilhas Excel com estatísticas das partidas
"""

import logging
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import os

logger = logging.getLogger(__name__)


class ReportGenerator:
    """Classe para geração de relatórios em Excel"""
    
    def __init__(self):
        self.reports_dir = '/tmp/reports'
        os.makedirs(self.reports_dir, exist_ok=True)
        logger.info("✅ ReportGenerator inicializado")
    
    def generate_weekly_report(self, matches_data: List[Dict]) -> Optional[str]:
        """
        Gera relatório semanal em Excel
        
        Args:
            matches_data: Lista de dicionários com dados das partidas
        
        Returns:
            Caminho do arquivo Excel gerado ou None se erro
        """
        try:
            if not matches_data:
                logger.warning("⚠️ Nenhum dado para gerar relatório")
                return None
            
            # Nome do arquivo
            filename = f"FIFA25_Relatorio_Semanal_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            filepath = os.path.join(self.reports_dir, filename)
            
            # Criar Excel com múltiplas abas
            with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
                
                # Aba 1: Resumo Geral
                self._create_summary_sheet(matches_data, writer)
                
                # Aba 2: Todas as Partidas
                self._create_matches_sheet(matches_data, writer)
                
                # Aba 3: Estatísticas por Jogador
                self._create_players_stats_sheet(matches_data, writer)
                
                # Aba 4: Times Mais Usados
                self._create_teams_stats_sheet(matches_data, writer)
                
                # Aba 5: Estatísticas por Location
                self._create_locations_stats_sheet(matches_data, writer)
            
            logger.info(f"✅ Relatório gerado: {filename}")
            return filepath
            
        except Exception as e:
            logger.error(f"❌ Erro ao gerar relatório: {e}")
            return None
    
    def _create_summary_sheet(self, matches_data: List[Dict], writer):
        """Cria aba de resumo"""
        try:
            # Estatísticas gerais
            total_matches = len(matches_data)
            
            status_count = {}
            for match in matches_data:
                status = match.get('status_id', 1)
                status_name = {1: 'Planejadas', 2: 'Ao Vivo', 3: 'Finalizadas', 4: 'Canceladas'}.get(status, 'Outros')
                status_count[status_name] = status_count.get(status_name, 0) + 1
            
            # Jogadores únicos
            players = set()
            for match in matches_data:
                if match.get('player1_nickname'):
                    players.add(match['player1_nickname'])
                if match.get('player2_nickname'):
                    players.add(match['player2_nickname'])
            
            # Gols totais
            total_goals = 0
            for match in matches_data:
                score1 = match.get('score1', 0) or 0
                score2 = match.get('score2', 0) or 0
                total_goals += score1 + score2
            
            avg_goals = round(total_goals / total_matches, 2) if total_matches > 0 else 0
            
            # Criar DataFrame
            summary_data = {
                'Métrica': [
                    'Total de Partidas',
                    'Partidas Finalizadas',
                    'Partidas Ao Vivo',
                    'Partidas Planejadas',
                    'Jogadores Únicos',
                    'Total de Gols',
                    'Média de Gols/Partida'
                ],
                'Valor': [
                    total_matches,
                    status_count.get('Finalizadas', 0),
                    status_count.get('Ao Vivo', 0),
                    status_count.get('Planejadas', 0),
                    len(players),
                    total_goals,
                    avg_goals
                ]
            }
            
            df_summary = pd.DataFrame(summary_data)
            df_summary.to_excel(writer, sheet_name='Resumo', index=False)
            
            # Ajustar largura das colunas
            worksheet = writer.sheets['Resumo']
            worksheet.column_dimensions['A'].width = 25
            worksheet.column_dimensions['B'].width = 15
            
        except Exception as e:
            logger.error(f"❌ Erro ao criar aba de resumo: {e}")
    
    def _create_matches_sheet(self, matches_data: List[Dict], writer):
        """Cria aba com todas as partidas"""
        try:
            matches_list = []
            
            for match in matches_data:
                matches_list.append({
                    'ID': match.get('match_id', 'N/A'),
                    'Data/Hora': self._format_datetime(match.get('date')),
                    'Status': self._get_status_name(match.get('status_id', 1)),
                    'Jogador 1': match.get('player1_nickname', 'N/A'),
                    'Time 1': match.get('player1_team_name', 'N/A'),
                    'Placar 1': match.get('score1', '-'),
                    'Placar 2': match.get('score2', '-'),
                    'Jogador 2': match.get('player2_nickname', 'N/A'),
                    'Time 2': match.get('player2_team_name', 'N/A'),
                    'Location': match.get('location_name', 'N/A'),
                    'Torneio': match.get('tournament_token', 'N/A')
                })
            
            df_matches = pd.DataFrame(matches_list)
            df_matches.to_excel(writer, sheet_name='Partidas', index=False)
            
            # Ajustar largura das colunas
            worksheet = writer.sheets['Partidas']
            for col in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K']:
                worksheet.column_dimensions[col].width = 15
            
        except Exception as e:
            logger.error(f"❌ Erro ao criar aba de partidas: {e}")
    
    def _create_players_stats_sheet(self, matches_data: List[Dict], writer):
        """Cria aba com estatísticas por jogador"""
        try:
            player_stats = {}
            
            for match in matches_data:
                status = match.get('status_id', 1)
                if status != 3:  # Apenas partidas finalizadas
                    continue
                
                score1 = match.get('score1', 0) or 0
                score2 = match.get('score2', 0) or 0
                
                # Jogador 1
                p1_nick = match.get('player1_nickname')
                if p1_nick:
                    if p1_nick not in player_stats:
                        player_stats[p1_nick] = {
                            'partidas': 0,
                            'vitorias': 0,
                            'derrotas': 0,
                            'empates': 0,
                            'gols_marcados': 0,
                            'gols_sofridos': 0
                        }
                    
                    player_stats[p1_nick]['partidas'] += 1
                    player_stats[p1_nick]['gols_marcados'] += score1
                    player_stats[p1_nick]['gols_sofridos'] += score2
                    
                    if score1 > score2:
                        player_stats[p1_nick]['vitorias'] += 1
                    elif score1 < score2:
                        player_stats[p1_nick]['derrotas'] += 1
                    else:
                        player_stats[p1_nick]['empates'] += 1
                
                # Jogador 2
                p2_nick = match.get('player2_nickname')
                if p2_nick:
                    if p2_nick not in player_stats:
                        player_stats[p2_nick] = {
                            'partidas': 0,
                            'vitorias': 0,
                            'derrotas': 0,
                            'empates': 0,
                            'gols_marcados': 0,
                            'gols_sofridos': 0
                        }
                    
                    player_stats[p2_nick]['partidas'] += 1
                    player_stats[p2_nick]['gols_marcados'] += score2
                    player_stats[p2_nick]['gols_sofridos'] += score1
                    
                    if score2 > score1:
                        player_stats[p2_nick]['vitorias'] += 1
                    elif score2 < score1:
                        player_stats[p2_nick]['derrotas'] += 1
                    else:
                        player_stats[p2_nick]['empates'] += 1
            
            # Criar lista para DataFrame
            players_list = []
            for nickname, stats in player_stats.items():
                win_rate = round((stats['vitorias'] / stats['partidas'] * 100), 2) if stats['partidas'] > 0 else 0
                
                players_list.append({
                    'Jogador': nickname,
                    'Partidas': stats['partidas'],
                    'Vitórias': stats['vitorias'],
                    'Derrotas': stats['derrotas'],
                    'Empates': stats['empates'],
                    'Taxa de Vitória (%)': win_rate,
                    'Gols Marcados': stats['gols_marcados'],
                    'Gols Sofridos': stats['gols_sofridos'],
                    'Saldo de Gols': stats['gols_marcados'] - stats['gols_sofridos']
                })
            
            # Ordenar por taxa de vitória
            players_list.sort(key=lambda x: x['Taxa de Vitória (%)'], reverse=True)
            
            df_players = pd.DataFrame(players_list)
            df_players.to_excel(writer, sheet_name='Estatísticas Jogadores', index=False)
            
            # Ajustar largura das colunas
            worksheet = writer.sheets['Estatísticas Jogadores']
            for col in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I']:
                worksheet.column_dimensions[col].width = 18
            
        except Exception as e:
            logger.error(f"❌ Erro ao criar aba de estatísticas de jogadores: {e}")
    
    def _create_teams_stats_sheet(self, matches_data: List[Dict], writer):
        """Cria aba com times mais usados"""
        try:
            team_usage = {}
            
            for match in matches_data:
                team1 = match.get('player1_team_name')
                team2 = match.get('player2_team_name')
                
                if team1:
                    team_usage[team1] = team_usage.get(team1, 0) + 1
                if team2:
                    team_usage[team2] = team_usage.get(team2, 0) + 1
            
            # Criar DataFrame
            teams_list = [
                {'Time': team, 'Vezes Usado': count}
                for team, count in sorted(team_usage.items(), key=lambda x: x[1], reverse=True)
            ]
            
            df_teams = pd.DataFrame(teams_list)
            df_teams.to_excel(writer, sheet_name='Times Mais Usados', index=False)
            
            # Ajustar largura das colunas
            worksheet = writer.sheets['Times Mais Usados']
            worksheet.column_dimensions['A'].width = 25
            worksheet.column_dimensions['B'].width = 15
            
        except Exception as e:
            logger.error(f"❌ Erro ao criar aba de times: {e}")
    
    def _create_locations_stats_sheet(self, matches_data: List[Dict], writer):
        """Cria aba com estatísticas por location"""
        try:
            location_stats = {}
            
            for match in matches_data:
                location = match.get('location_name', 'Desconhecido')
                
                if location not in location_stats:
                    location_stats[location] = 0
                
                location_stats[location] += 1
            
            # Criar DataFrame
            locations_list = [
                {'Location': loc, 'Partidas': count}
                for loc, count in sorted(location_stats.items(), key=lambda x: x[1], reverse=True)
            ]
            
            df_locations = pd.DataFrame(locations_list)
            df_locations.to_excel(writer, sheet_name='Locations', index=False)
            
            # Ajustar largura das colunas
            worksheet = writer.sheets['Locations']
            worksheet.column_dimensions['A'].width = 25
            worksheet.column_dimensions['B'].width = 15
            
        except Exception as e:
            logger.error(f"❌ Erro ao criar aba de locations: {e}")
    
    def _format_datetime(self, date_str: str) -> str:
        """Formata data/hora"""
        if not date_str:
            return 'N/A'
        
        try:
            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            return dt.strftime('%d/%m/%Y %H:%M')
        except:
            return date_str
    
    def _get_status_name(self, status_id: int) -> str:
        """Retorna nome do status"""
        statuses = {
            1: 'Planejada',
            2: 'Ao Vivo',
            3: 'Finalizada',
            4: 'Cancelada'
        }
        return statuses.get(status_id, 'Desconhecido')
    
    def cleanup_old_reports(self, days: int = 7):
        """Remove relatórios antigos"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            for filename in os.listdir(self.reports_dir):
                filepath = os.path.join(self.reports_dir, filename)
                
                if os.path.isfile(filepath):
                    file_time = datetime.fromtimestamp(os.path.getmtime(filepath))
                    
                    if file_time < cutoff_date:
                        os.remove(filepath)
                        logger.info(f"🗑️ Relatório antigo removido: {filename}")
            
        except Exception as e:
            logger.error(f"❌ Erro ao limpar relatórios antigos: {e}")


# Teste standalone
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Mock de dados para teste
    mock_data = [
        {
            'match_id': 1,
            'date': '2026-01-30T10:00:00Z',
            'status_id': 3,
            'player1_nickname': 'Player1',
            'player1_team_name': 'Brazil',
            'player2_nickname': 'Player2',
            'player2_team_name': 'Argentina',
            'score1': 3,
            'score2': 2,
            'location_name': 'Wembley',
            'tournament_token': 'Nations League'
        }
    ]
    
    generator = ReportGenerator()
    filepath = generator.generate_weekly_report(mock_data)
    
    if filepath:
        print(f"✅ Relatório gerado: {filepath}")
    else:
        print("❌ Erro ao gerar relatório")
