"""
Modelos do Banco de Dados - FIFA 25 Bot
SQLAlchemy Models
"""

from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Match(db.Model):
    """Modelo de Partida"""
    __tablename__ = 'matches'
    
    id = db.Column(db.Integer, primary_key=True)
    match_id = db.Column(db.Integer, unique=True, nullable=False, index=True)
    
    # Status e data
    status_id = db.Column(db.Integer, default=1)  # 1=Planned, 2=Started, 3=Finished, 4=Canceled
    date = db.Column(db.DateTime, index=True)
    
    # Torneio
    tournament_id = db.Column(db.Integer, index=True)
    tournament_token = db.Column(db.String(200))
    
    # Location (arena/sala)
    location_code = db.Column(db.String(100))
    location_name = db.Column(db.String(200))
    location_color = db.Column(db.String(20))
    
    # Console
    console_id = db.Column(db.Integer)
    console_token = db.Column(db.String(100))
    
    # Jogador 1
    player1_id = db.Column(db.Integer, index=True)
    player1_nickname = db.Column(db.String(100))
    player1_photo = db.Column(db.String(500))
    player1_team_id = db.Column(db.Integer)
    player1_team_name = db.Column(db.String(200))
    player1_team_logo = db.Column(db.String(500))
    
    # Jogador 2
    player2_id = db.Column(db.Integer, index=True)
    player2_nickname = db.Column(db.String(100))
    player2_photo = db.Column(db.String(500))
    player2_team_id = db.Column(db.Integer)
    player2_team_name = db.Column(db.String(200))
    player2_team_logo = db.Column(db.String(500))
    
    # Placar
    score1 = db.Column(db.Integer)
    score2 = db.Column(db.Integer)
    
    # Metadados
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    
    def __repr__(self):
        return f'<Match {self.match_id}: {self.player1_nickname} vs {self.player2_nickname}>'
    
    def to_dict(self):
        """Converte para dicionário"""
        return {
            'id': self.id,
            'match_id': self.match_id,
            'status_id': self.status_id,
            'status': self.get_status_text(),
            'date': self.date.isoformat() if self.date else None,
            'tournament': {
                'id': self.tournament_id,
                'name': self.tournament_token
            },
            'location': {
                'code': self.location_code,
                'name': self.location_name,
                'color': self.location_color
            },
            'console': {
                'id': self.console_id,
                'token': self.console_token
            },
            'player1': {
                'id': self.player1_id,
                'nickname': self.player1_nickname,
                'photo': self.player1_photo,
                'team': {
                    'id': self.player1_team_id,
                    'name': self.player1_team_name,
                    'logo': self.player1_team_logo
                }
            },
            'player2': {
                'id': self.player2_id,
                'nickname': self.player2_nickname,
                'photo': self.player2_photo,
                'team': {
                    'id': self.player2_team_id,
                    'name': self.player2_team_name,
                    'logo': self.player2_team_logo
                }
            },
            'score': {
                'player1': self.score1,
                'player2': self.score2
            },
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def get_status_text(self):
        """Retorna texto do status"""
        statuses = {
            1: 'Planned',
            2: 'Live',
            3: 'Finished',
            4: 'Canceled'
        }
        return statuses.get(self.status_id, 'Unknown')
    
    def get_photo_url(self, photo_hash, size='120x120'):
        """Retorna URL completa da foto"""
        if not photo_hash:
            return None
        base_url = "https://football.esportsbattle.com/api/Image/efootball"
        return f"{base_url}/{size}/{photo_hash}"
    
    def get_logo_url(self, logo_hash, size='160x160'):
        """Retorna URL completa do logo do time"""
        if not logo_hash:
            return None
        base_url = "https://football.esportsbattle.com/api/Image/esports"
        return f"{base_url}/{size}/{logo_hash}"


class Player(db.Model):
    """Modelo de Jogador"""
    __tablename__ = 'players'
    
    id = db.Column(db.Integer, primary_key=True)
    player_id = db.Column(db.Integer, unique=True, nullable=False, index=True)
    nickname = db.Column(db.String(100), nullable=False)
    photo = db.Column(db.String(500))
    
    # Estatísticas
    total_matches = db.Column(db.Integer, default=0)
    wins = db.Column(db.Integer, default=0)
    losses = db.Column(db.Integer, default=0)
    draws = db.Column(db.Integer, default=0)
    goals_scored = db.Column(db.Integer, default=0)
    goals_conceded = db.Column(db.Integer, default=0)
    
    # Metadados
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    
    def __repr__(self):
        return f'<Player {self.player_id}: {self.nickname}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'player_id': self.player_id,
            'nickname': self.nickname,
            'photo': self.photo,
            'stats': {
                'total_matches': self.total_matches,
                'wins': self.wins,
                'losses': self.losses,
                'draws': self.draws,
                'goals_scored': self.goals_scored,
                'goals_conceded': self.goals_conceded,
                'win_rate': self.get_win_rate()
            }
        }
    
    def get_win_rate(self):
        """Calcula taxa de vitória"""
        if self.total_matches == 0:
            return 0.0
        return round((self.wins / self.total_matches) * 100, 2)


class Tournament(db.Model):
    """Modelo de Torneio"""
    __tablename__ = 'tournaments'
    
    id = db.Column(db.Integer, primary_key=True)
    tournament_id = db.Column(db.Integer, unique=True, nullable=False, index=True)
    
    status_id = db.Column(db.Integer, default=1)
    token = db.Column(db.String(200))
    token_international = db.Column(db.String(200))
    marker = db.Column(db.String(10))
    
    # Estatísticas
    total_matches = db.Column(db.Integer, default=0)
    
    # Metadados
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    
    def __repr__(self):
        return f'<Tournament {self.tournament_id}: {self.token_international}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'tournament_id': self.tournament_id,
            'status_id': self.status_id,
            'name': self.token_international or self.token,
            'marker': self.marker,
            'total_matches': self.total_matches
        }


class Analysis(db.Model):
    """Modelo de Análise Diária"""
    __tablename__ = 'analyses'
    
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, index=True)
    
    # Estatísticas do dia
    total_matches = db.Column(db.Integer, default=0)
    live_matches = db.Column(db.Integer, default=0)
    finished_matches = db.Column(db.Integer, default=0)
    canceled_matches = db.Column(db.Integer, default=0)
    
    # Jogadores únicos
    unique_players = db.Column(db.Integer, default=0)
    
    # Times mais usados
    top_teams = db.Column(db.Text)  # JSON string
    
    # Locations mais ativas
    top_locations = db.Column(db.Text)  # JSON string
    
    # Metadados
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    
    def __repr__(self):
        return f'<Analysis {self.date}>'
    
    def to_dict(self):
        import json
        
        return {
            'id': self.id,
            'date': self.date.isoformat(),
            'stats': {
                'total_matches': self.total_matches,
                'live_matches': self.live_matches,
                'finished_matches': self.finished_matches,
                'canceled_matches': self.canceled_matches,
                'unique_players': self.unique_players
            },
            'top_teams': json.loads(self.top_teams) if self.top_teams else [],
            'top_locations': json.loads(self.top_locations) if self.top_locations else []
        }


class ScanLog(db.Model):
    """Log de varreduras do scraper"""
    __tablename__ = 'scan_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Resultado da varredura
    success = db.Column(db.Boolean, default=True)
    matches_found = db.Column(db.Integer, default=0)
    matches_saved = db.Column(db.Integer, default=0)
    duration_seconds = db.Column(db.Float)
    
    # Erro (se houver)
    error_message = db.Column(db.Text)
    
    # Metadados
    created_at = db.Column(db.DateTime, default=datetime.now, index=True)
    
    def __repr__(self):
        status = "✅" if self.success else "❌"
        return f'<ScanLog {status} {self.created_at}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'success': self.success,
            'matches_found': self.matches_found,
            'matches_saved': self.matches_saved,
            'duration_seconds': self.duration_seconds,
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat()
        }