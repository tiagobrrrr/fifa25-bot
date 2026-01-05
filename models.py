from sqlalchemy import Column, Integer, String, DateTime, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os

Base = declarative_base()

class Match(Base):
    """Modelo para partidas FIFA 25"""
    __tablename__ = 'matches'
    
    id = Column(Integer, primary_key=True)
    team1 = Column(String(100))
    team2 = Column(String(100))
    player1 = Column(String(100))
    player2 = Column(String(100))
    score = Column(String(20))  # ✅ CORRIGIDO - formato "2-1"
    tournament = Column(String(200))
    match_time = Column(String(50))
    location = Column(String(100))
    status = Column(String(50))
    scraped_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<Match {self.team1} vs {self.team2} ({self.score})>"
    
    def to_dict(self):
        """Converte o objeto para dicionário"""
        return {
            'id': self.id,
            'team1': self.team1,
            'team2': self.team2,
            'player1': self.player1,
            'player2': self.player2,
            'score': self.score,
            'tournament': self.tournament,
            'match_time': self.match_time,
            'location': self.location,
            'status': self.status,
            'scraped_at': self.scraped_at.isoformat() if self.scraped_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Player(Base):
    """Modelo para estatísticas de jogadores"""
    __tablename__ = 'players'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True)
    total_matches = Column(Integer, default=0)
    wins = Column(Integer, default=0)
    losses = Column(Integer, default=0)
    draws = Column(Integer, default=0)
    goals_scored = Column(Integer, default=0)
    goals_conceded = Column(Integer, default=0)
    last_updated = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<Player {self.name} - {self.total_matches} partidas>"
    
    def to_dict(self):
        """Converte o objeto para dicionário"""
        win_rate = (self.wins / self.total_matches * 100) if self.total_matches > 0 else 0
        return {
            'id': self.id,
            'name': self.name,
            'total_matches': self.total_matches,
            'wins': self.wins,
            'losses': self.losses,
            'draws': self.draws,
            'goals_scored': self.goals_scored,
            'goals_conceded': self.goals_conceded,
            'goal_difference': self.goals_scored - self.goals_conceded,
            'win_rate': round(win_rate, 2),
            'last_updated': self.last_updated.isoformat() if self.last_updated else None
        }


# Configuração do banco de dados
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///fifa25_bot.db')

# Fix para Render/Heroku (postgres:// -> postgresql://)
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

# ✅ ADICIONAR: Configuração SSL para PostgreSQL no Render
connect_args = {}
if 'postgresql://' in DATABASE_URL and 'render.com' in DATABASE_URL:
    # Adiciona sslmode=require na URL
    if '?' in DATABASE_URL:
        DATABASE_URL += '&sslmode=require'
    else:
        DATABASE_URL += '?sslmode=require'
    
    # Configuração adicional de SSL
    connect_args = {
        'sslmode': 'require'
    }

# Criar engine com configurações SSL
engine = create_engine(
    DATABASE_URL, 
    echo=False,
    connect_args=connect_args,
    pool_pre_ping=True,  # Verifica conexões antes de usar
    pool_recycle=3600    # Recicla conexões a cada hora
)

Session = sessionmaker(bind=engine)

def init_db():
    """Inicializa o banco de dados criando todas as tabelas"""
    try:
        Base.metadata.create_all(engine)
        print("✅ Banco de dados inicializado com sucesso!")
        return True
    except Exception as e:
        print(f"⚠️  Aviso ao inicializar banco: {e}")
        print("ℹ️  O banco será inicializado quando a aplicação iniciar")
        return False

def get_session():
    """Retorna uma nova sessão do banco de dados"""
    return Session()