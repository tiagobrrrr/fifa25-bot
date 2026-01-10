from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Match(db.Model):
    __tablename__ = 'matches'
    
    id = db.Column(db.Integer, primary_key=True)
    match_id = db.Column(db.String(100), unique=True, nullable=False, index=True)
    
    player1_name = db.Column(db.String(100))
    player2_name = db.Column(db.String(100))
    player1_team = db.Column(db.String(100))
    player2_team = db.Column(db.String(100))
    
    score1 = db.Column(db.Integer)
    score2 = db.Column(db.Integer)
    
    date = db.Column(db.DateTime, index=True)
    status = db.Column(db.String(20), default='scheduled', index=True)
    location = db.Column(db.String(100))
    console = db.Column(db.String(50))
    tournament = db.Column(db.String(100))
    tournament_id = db.Column(db.String(50))
    round_info = db.Column(db.String(50))
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<Match {self.player1_name} vs {self.player2_name}>'


class Player(db.Model):
    __tablename__ = 'players'
    
    id = db.Column(db.Integer, primary_key=True)
    player_name = db.Column(db.String(100), unique=True, nullable=False, index=True)
    
    total_matches = db.Column(db.Integer, default=0)
    wins = db.Column(db.Integer, default=0)
    losses = db.Column(db.Integer, default=0)
    draws = db.Column(db.Integer, default=0)
    
    first_seen = db.Column(db.DateTime, default=datetime.utcnow)
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Player {self.player_name}>'
