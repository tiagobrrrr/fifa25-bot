from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Match(db.Model):
    """Modelo para armazenar partidas"""
    __tablename__ = 'matches'
    
    id = db.Column(db.Integer, primary_key=True)
    match_id = db.Column(db.Integer, unique=True, nullable=False, index=True)
    tournament_id = db.Column(db.Integer, nullable=False, index=True)
    status_id = db.Column(db.Integer, nullable=False)  # 1=agendada, 2=ao vivo, 3=finalizada
    
    # Informações do jogo
    date = db.Column(db.DateTime, nullable=False, index=True)
    location = db.Column(db.String(100))
    console = db.Column(db.String(10))
    stream_url = db.Column(db.String(500))
    
    # Participante 1
    player1_nickname = db.Column(db.String(100), index=True)
    player1_team = db.Column(db.String(100))
    player1_score = db.Column(db.Integer, default=0)
    
    # Participante 2
    player2_nickname = db.Column(db.String(100), index=True)
    player2_team = db.Column(db.String(100))
    player2_score = db.Column(db.Integer, default=0)
    
    # Placar de períodos anteriores
    prev_periods_scores = db.Column(db.String(50))
    
    # Metadados
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<Match {self.match_id}: {self.player1_nickname} vs {self.player2_nickname}>'
    
    @staticmethod
    def from_api_data(match_data):
        """Cria uma Match a partir dos dados da API"""
        try:
            # Parse da data
            date_str = match_data.get('date', '')
            if date_str:
                # Formato: 2026-01-18T16:36:00Z
                match_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            else:
                match_date = datetime.utcnow()
            
            # Extrair dados dos participantes
            p1 = match_data.get('participant1', {})
            p2 = match_data.get('participant2', {})
            
            p1_team = p1.get('team', {})
            p2_team = p2.get('team', {})
            
            location_data = match_data.get('location', {})
            console_data = match_data.get('console', {})
            
            return Match(
                match_id=match_data.get('id'),
                tournament_id=match_data.get('tournament_id'),
                status_id=match_data.get('status_id', 1),
                date=match_date,
                location=location_data.get('token', 'Unknown'),
                console=console_data.get('token', ''),
                stream_url=console_data.get('streamUrl', ''),
                player1_nickname=p1.get('nickname', 'Unknown'),
                player1_team=p1_team.get('token_international', p1_team.get('token', 'Unknown')),
                player1_score=p1.get('score', 0),
                player2_nickname=p2.get('nickname', 'Unknown'),
                player2_team=p2_team.get('token_international', p2_team.get('token', 'Unknown')),
                player2_score=p2.get('score', 0),
                prev_periods_scores=match_data.get('prevPeriodsScores', '')
            )
        except Exception as e:
            print(f"Erro ao criar Match: {e}")
            raise
    
    def to_dict(self):
        """Converte para dicionário"""
        return {
            'id': self.match_id,
            'tournament_id': self.tournament_id,
            'status_id': self.status_id,
            'date': self.date.isoformat(),
            'location': self.location,
            'console': self.console,
            'stream_url': self.stream_url,
            'player1': {
                'nickname': self.player1_nickname,
                'team': self.player1_team,
                'score': self.player1_score
            },
            'player2': {
                'nickname': self.player2_nickname,
                'team': self.player2_team,
                'score': self.player2_score
            },
            'prev_periods_scores': self.prev_periods_scores
        }


class Tournament(db.Model):
    """Modelo para armazenar torneios"""
    __tablename__ = 'tournaments'
    
    id = db.Column(db.Integer, primary_key=True)
    tournament_id = db.Column(db.Integer, unique=True, nullable=False, index=True)
    status_id = db.Column(db.Integer)
    marker = db.Column(db.String(10))
    name = db.Column(db.String(200))
    name_international = db.Column(db.String(200))
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<Tournament {self.tournament_id}: {self.name_international}>'
    
    @staticmethod
    def from_api_data(tournament_data):
        """Cria um Tournament a partir dos dados da API"""
        return Tournament(
            tournament_id=tournament_data.get('id'),
            status_id=tournament_data.get('status_id'),
            marker=tournament_data.get('marker', ''),
            name=tournament_data.get('token', ''),
            name_international=tournament_data.get('token_international', '')
        )


class Player(db.Model):
    """Modelo para armazenar estatísticas de jogadores"""
    __tablename__ = 'players'
    
    id = db.Column(db.Integer, primary_key=True)
    nickname = db.Column(db.String(100), unique=True, nullable=False, index=True)
    
    # Estatísticas gerais
    total_matches = db.Column(db.Integer, default=0)
    wins = db.Column(db.Integer, default=0)
    draws = db.Column(db.Integer, default=0)
    losses = db.Column(db.Integer, default=0)
    goals_for = db.Column(db.Integer, default=0)
    goals_against = db.Column(db.Integer, default=0)
    
    # Metadados
    last_seen = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Player {self.nickname}: {self.wins}W {self.draws}D {self.losses}L>'
    
    @property
    def win_rate(self):
        """Calcula taxa de vitórias"""
        if self.total_matches == 0:
            return 0.0
        return (self.wins / self.total_matches) * 100
    
    @property
    def goal_difference(self):
        """Calcula saldo de gols"""
        return self.goals_for - self.goals_against
    
    @property
    def points(self):
        """Calcula pontos (vitória=3, empate=1)"""
        return (self.wins * 3) + self.draws
    
    def to_dict(self):
        """Converte para dicionário"""
        return {
            'nickname': self.nickname,
            'total_matches': self.total_matches,
            'wins': self.wins,
            'draws': self.draws,
            'losses': self.losses,
            'goals_for': self.goals_for,
            'goals_against': self.goals_against,
            'goal_difference': self.goal_difference,
            'win_rate': round(self.win_rate, 2),
            'points': self.points,
            'last_seen': self.last_seen.isoformat() if self.last_seen else None
        }


class ScraperLog(db.Model):
    """Modelo para armazenar logs do scraper"""
    __tablename__ = 'scraper_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    status = db.Column(db.String(20))  # success, error, warning
    message = db.Column(db.Text)
    matches_found = db.Column(db.Integer, default=0)
    matches_new = db.Column(db.Integer, default=0)
    matches_updated = db.Column(db.Integer, default=0)
    execution_time = db.Column(db.Float)  # em segundos
    
    def __repr__(self):
        return f'<ScraperLog {self.timestamp}: {self.status}>'
    
    def to_dict(self):
        """Converte para dicionário"""
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat(),
            'status': self.status,
            'message': self.message,
            'matches_found': self.matches_found,
            'matches_new': self.matches_new,
            'matches_updated': self.matches_updated,
            'execution_time': self.execution_time
        }