from flask_sqlalchemy import SQLAlchemy
import datetime

db = SQLAlchemy()

# ===========================
#   Tabela de Jogadores
# ===========================
class Player(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    display_name = db.Column(db.String(120), nullable=True)

    def __repr__(self):
        return f"<Player {self.username}>"


# ===========================
#   Tabela de Times
# ===========================
class Team(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)

    def __repr__(self):
        return f"<Team {self.name}>"


# ===========================
#   Tabela de Partidas (em andamento, planejadas e finalizadas)
# ===========================
class Match(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    match_id = db.Column(db.String(50), nullable=False)      # ID do site
    player = db.Column(db.String(80), nullable=False)
    team = db.Column(db.String(120), nullable=False)
    opponent = db.Column(db.String(120), nullable=False)

    goals = db.Column(db.Integer, nullable=True)
    goals_against = db.Column(db.Integer, nullable=True)
    win = db.Column(db.Boolean, nullable=True)

    league = db.Column(db.String(120), nullable=True)
    stadium = db.Column(db.String(120), nullable=True)

    date = db.Column(db.Date, nullable=True)
    time = db.Column(db.Time, nullable=True)

    status = db.Column(db.String(40), nullable=False, default="planned")

    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    def __repr__(self):
        return f"<Match {self.match_id} - {self.player}>"


# ===========================
#   Arquivo histórico (backup)
# ===========================
class FinishedMatchArchive(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    match_id = db.Column(db.String(50), nullable=False)
    player = db.Column(db.String(80), nullable=False)
    team = db.Column(db.String(120), nullable=False)
    opponent = db.Column(db.String(120), nullable=False)

    goals = db.Column(db.Integer, nullable=True)
    goals_against = db.Column(db.Integer, nullable=True)
    win = db.Column(db.Boolean, nullable=True)

    league = db.Column(db.String(120), nullable=True)
    stadium = db.Column(db.String(120), nullable=True)

    date = db.Column(db.Date, nullable=True)
    time = db.Column(db.Time, nullable=True)

    archived_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    def __repr__(self):
        return f"<Archive {self.match_id} - {self.player}>"
