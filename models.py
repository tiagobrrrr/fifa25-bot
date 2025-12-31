"""
Modelos do Banco de Dados - FIFA25 Bot
"""

from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Match(db.Model):
    """Modelo para armazenar partidas"""
    __tablename__ = 'matches'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Times/Seleções
    team1 = db.Column(db.String(100), nullable=False)
    team2 = db.Column(db.String(100), nullable=False)
    
    # Jogadores
    player1 = db.Column(db.String(100))
    player2 = db.Column(db.String(100))
    
    # Placar
    score1 = db.Column(db.Integer, default=0)
    score2 = db.Column(db.Integer, default=0)
    
    # Informações adicionais
    tournament = db.Column(db.String(200))
    match_time = db.Column(db.String(50))
    location = db.Column(db.String(100))
    
    # Status: 'live', 'finished', 'scheduled'
    status = db.Column(db.String(20), default='live')
    
    # Metadados
    scraped_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<Match {self.team1} {self.score1}x{self.score2} {self.team2}>'
    
    def to_dict(self):
        """Converte para dicionário"""
        return {
            'id': self.id,
            'team1': self.team1,
            'team2': self.team2,
            'player1': self.player1,
            'player2': self.player2,
            'score1': self.score1,
            'score2': self.score2,
            'tournament': self.tournament,
            'match_time': self.match_time,
            'location': self.location,
            'status': self.status,
            'scraped_at': self.scraped_at.isoformat() if self.scraped_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class Player(db.Model):
    """Modelo para armazenar estatísticas de jogadores"""
    __tablename__ = 'players'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Informações básicas
    name = db.Column(db.String(100), unique=True, nullable=False)
    
    # Estatísticas
    matches_played = db.Column(db.Integer, default=0)
    wins = db.Column(db.Integer, default=0)
    draws = db.Column(db.Integer, default=0)
    losses = db.Column(db.Integer, default=0)
    
    goals_for = db.Column(db.Integer, default=0)
    goals_against = db.Column(db.Integer, default=0)
    
    # Metadados
    first_seen = db.Column(db.DateTime, default=datetime.utcnow)
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    @property
    def win_rate(self):
        """Calcula taxa de vitória"""
        if self.matches_played == 0:
            return 0.0
        return (self.wins / self.matches_played) * 100
    
    @property
    def goal_difference(self):
        """Calcula saldo de gols"""
        return self.goals_for - self.goals_against
    
    def __repr__(self):
        return f'<Player {self.name} - {self.matches_played} partidas>'
    
    def to_dict(self):
        """Converte para dicionário"""
        return {
            'id': self.id,
            'name': self.name,
            'matches_played': self.matches_played,
            'wins': self.wins,
            'draws': self.draws,
            'losses': self.losses,
            'goals_for': self.goals_for,
            'goals_against': self.goals_against,
            'win_rate': round(self.win_rate, 2),
            'goal_difference': self.goal_difference,
            'first_seen': self.first_seen.isoformat() if self.first_seen else None,
            'last_seen': self.last_seen.isoformat() if self.last_seen else None
        }

class Tournament(db.Model):
    """Modelo para armazenar torneios"""
    __tablename__ = 'tournaments'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Informações básicas
    name = db.Column(db.String(200), nullable=False)
    tournament_date = db.Column(db.Date)
    
    # Grupo/Console
    group = db.Column(db.String(50))
    location = db.Column(db.String(100))
    
    # Status: 'scheduled', 'in_progress', 'finished'
    status = db.Column(db.String(20), default='in_progress')
    
    # Metadados
    start_time = db.Column(db.DateTime)
    end_time = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<Tournament {self.name} - {self.status}>'
    
    def to_dict(self):
        """Converte para dicionário"""
        return {
            'id': self.id,
            'name': self.name,
            'tournament_date': self.tournament_date.isoformat() if self.tournament_date else None,
            'group': self.group,
            'location': self.location,
            'status': self.status,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None
        }

class DailyStats(db.Model):
    """Modelo para armazenar estatísticas diárias"""
    __tablename__ = 'daily_stats'
    
    id = db.Column(db.Integer, primary_key=True)
    
    date = db.Column(db.Date, unique=True, nullable=False)
    
    # Contadores
    total_matches = db.Column(db.Integer, default=0)
    total_goals = db.Column(db.Integer, default=0)
    unique_players = db.Column(db.Integer, default=0)
    
    # Média
    avg_goals_per_match = db.Column(db.Float, default=0.0)
    
    # Metadados
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<DailyStats {self.date} - {self.total_matches} partidas>'
    
    def to_dict(self):
        """Converte para dicionário"""
        return {
            'id': self.id,
            'date': self.date.isoformat() if self.date else None,
            'total_matches': self.total_matches,
            'total_goals': self.total_goals,
            'unique_players': self.unique_players,
            'avg_goals_per_match': round(self.avg_goals_per_match, 2)
        }