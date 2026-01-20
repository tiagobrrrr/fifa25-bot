import pandas as pd
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class DataAnalyzer:
    """Analisador de dados de partidas FIFA 25"""
    
    def __init__(self):
        pass
    
    def analyze_matches(self, matches):
        """Analisa lista de partidas"""
        try:
            if not matches:
                return {}
            
            df = pd.DataFrame(matches)
            
            analysis = {
                'total_matches': len(df),
                'live_matches': len(df[df['status'] == 'live']) if 'status' in df.columns else 0,
                'finished_matches': len(df[df['status'] == 'finished']) if 'status' in df.columns else 0,
                'avg_goals': df[['score1', 'score2']].sum().sum() / len(df) if 'score1' in df.columns else 0,
            }
            
            return analysis
            
        except Exception as e:
            logger.error(f"Erro ao analisar partidas: {e}")
            return {}
    
    def get_top_teams(self, matches, limit=10):
        """Retorna times com mais partidas"""
        try:
            df = pd.DataFrame(matches)
            
            teams = []
            if 'team1' in df.columns:
                teams.extend(df['team1'].tolist())
            if 'team2' in df.columns:
                teams.extend(df['team2'].tolist())
            
            team_counts = pd.Series(teams).value_counts().head(limit)
            
            return team_counts.to_dict()
            
        except Exception as e:
            logger.error(f"Erro ao obter top times: {e}")
            return {}
    
    def get_daily_stats(self, matches):
        """Estatísticas diárias"""
        try:
            df = pd.DataFrame(matches)
            
            if 'match_date' not in df.columns:
                return {}
            
            df['match_date'] = pd.to_datetime(df['match_date'])
            df['date'] = df['match_date'].dt.date
            
            daily = df.groupby('date').agg({
                'match_id': 'count',
                'score1': 'sum',
                'score2': 'sum'
            }).reset_index()
            
            daily.columns = ['date', 'matches', 'total_goals_team1', 'total_goals_team2']
            daily['total_goals'] = daily['total_goals_team1'] + daily['total_goals_team2']
            
            return daily.to_dict('records')
            
        except Exception as e:
            logger.error(f"Erro ao calcular estatísticas diárias: {e}")
            return []
    
    def generate_report(self, matches, filename='report.xlsx'):
        """Gera relatório em Excel"""
        try:
            df = pd.DataFrame(matches)
            
            with pd.ExcelWriter(filename, engine='openpyxl') as writer:
                # Aba de partidas
                df.to_excel(writer, sheet_name='Partidas', index=False)
                
                # Aba de estatísticas
                stats_df = pd.DataFrame([self.analyze_matches(matches)])
                stats_df.to_excel(writer, sheet_name='Estatísticas', index=False)
                
                # Aba de top times
                top_teams = self.get_top_teams(matches)
                top_teams_df = pd.DataFrame(list(top_teams.items()), columns=['Time', 'Partidas'])
                top_teams_df.to_excel(writer, sheet_name='Top Times', index=False)
            
            logger.info(f"Relatório gerado: {filename}")
            return filename
            
        except Exception as e:
            logger.error(f"Erro ao gerar relatório: {e}")
            return None


if __name__ == '__main__':
    # Teste do analisador
    analyzer = DataAnalyzer()
    
    sample_matches = [
        {
            'match_id': '1',
            'team1': 'Time A',
            'team2': 'Time B',
            'score1': 2,
            'score2': 1,
            'status': 'finished',
            'match_date': datetime.now()
        },
        {
            'match_id': '2',
            'team1': 'Time C',
            'team2': 'Time A',
            'score1': 0,
            'score2': 3,
            'status': 'live',
            'match_date': datetime.now()
        }
    ]
    
    analysis = analyzer.analyze_matches(sample_matches)
    print("Análise:", analysis)
    
    top_teams = analyzer.get_top_teams(sample_matches)
    print("Top Times:", top_teams)