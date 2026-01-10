from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

# Inicializa SQLAlchemy UMA ÚNICA VEZ
db = SQLAlchemy()

class Match(db.Model):
    __tablename__ = 'matches'
    
    id = db.Column(db.Integer, primary_key=True)
    match_id = db.Column(db.String(100), unique=True, nullable=False, index=True)
    
    # Jogadores
    player1_name = db.Column(db.String(100))
    player2_name = db.Column(db.String(100))
    player1_team = db.Column(db.String(100))
    player2_team = db.Column(db.String(100))
    
    # Placar
    score1 = db.Column(db.Integer)
    score2 = db.Column(db.Integer)
    
    # Informações da partida
    date = db.Column(db.DateTime, index=True)
    status = db.Column(db.String(20), default='scheduled', index=True)
    location = db.Column(db.String(100))
    console = db.Column(db.String(50))
    tournament = db.Column(db.String(100))
    round_info = db.Column(db.String(50))
    
    # Metadados
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<Match {self.player1_name} vs {self.player2_name}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'match_id': self.match_id,
            'player1_name': self.player1_name,
            'player2_name': self.player2_name,
            'player1_team': self.player1_team,
            'player2_team': self.player2_team,
            'score1': self.score1,
            'score2': self.score2,
            'date': self.date.isoformat() if self.date else None,
            'status': self.status,
            'location': self.location,
            'console': self.console,
            'tournament': self.tournament,
            'round': self.round_info,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class Player(db.Model):
    __tablename__ = 'players'
    
    id = db.Column(db.Integer, primary_key=True)
    player_name = db.Column(db.String(100), unique=True, nullable=False, index=True)
    
    # Estatísticas
    total_matches = db.Column(db.Integer, default=0)
    wins = db.Column(db.Integer, default=0)
    losses = db.Column(db.Integer, default=0)
    draws = db.Column(db.Integer, default=0)
    
    # Metadados
    first_seen = db.Column(db.DateTime, default=datetime.utcnow)
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Player {self.player_name}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.player_name,
            'stats': {
                'matches': self.total_matches,
                'wins': self.wins,
                'losses': self.losses,
                'draws': self.draws,
                'win_rate': round(self.wins / self.total_matches * 100, 1) if self.total_matches > 0 else 0
            },
            'first_seen': self.first_seen.isoformat() if self.first_seen else None,
            'last_seen': self.last_seen.isoformat() if self.last_seen else None
        }
