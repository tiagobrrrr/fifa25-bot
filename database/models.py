"""
Modelos de dados para o FIFA 25 Bot
"""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Float, Text, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os
import logging

logger = logging.getLogger(__name__)

Base = declarative_base()


class Match(Base):
    """Modelo para armazenar dados de partidas"""
    
    __tablename__ = 'matches'
    
    # Campos principais
    id = Column(String(100), primary_key=True)
    
    # Jogadores
    home_player = Column(String(200), nullable=False, default='Desconhecido')
    away_player = Column(String(200), nullable=False, default='Desconhecido')
    
    # Times (clubes do FIFA)
    home_club = Column(String(200), nullable=True, default='N/A')
    away_club = Column(String(200), nullable=True, default='N/A')
    
    # Placar
    home_score = Column(Integer, default=0)
    away_score = Column(Integer, default=0)
    
    # Status da partida
    status = Column(String(50), default='unknown')  # live, finished, scheduled, etc
    minute = Column(Integer, default=0)
    is_live = Column(Boolean, default=False)
    
    # Informações adicionais
    tournament = Column(String(200), nullable=True)
    tournament_id = Column(String(100), nullable=True)
    
    # Timestamps
    start_time = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Dados brutos (JSON) para referência
    raw_data = Column(JSON, nullable=True)
    
    def __repr__(self):
        return (
            f"<Match {self.id}: {self.home_player} ({self.home_club}) "
            f"vs {self.away_player} ({self.away_club}) - "
            f"{self.home_score}:{self.away_score}>"
        )
    
    def to_dict(self):
        """Converte o modelo para dicionário"""
        return {
            'id': self.id,
            'home_player': self.home_player,
            'away_player': self.away_player,
            'home_club': self.home_club,
            'away_club': self.away_club,
            'home_score': self.home_score,
            'away_score': self.away_score,
            'status': self.status,
            'minute': self.minute,
            'is_live': self.is_live,
            'tournament': self.tournament,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class MatchStats(Base):
    """Modelo para estatísticas agregadas"""
    
    __tablename__ = 'match_stats'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(DateTime, default=datetime.utcnow)
    total_matches = Column(Integer, default=0)
    live_matches = Column(Integer, default=0)
    finished_matches = Column(Integer, default=0)
    
    def __repr__(self):
        return f"<MatchStats {self.date}: {self.total_matches} matches>"


# Configuração do banco de dados
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///fifa25_bot.db')

# Fix para Heroku/Render PostgreSQL URL
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Inicializa o banco de dados"""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Banco de dados inicializado com sucesso")
    except Exception as e:
        logger.error(f"❌ Erro ao inicializar banco de dados: {str(e)}")
        raise


def get_db():
    """Retorna uma sessão do banco de dados"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def save_matches(matches_data: list) -> tuple:
    """
    Salva ou atualiza partidas no banco de dados
    
    Args:
        matches_data: Lista de dicionários com dados das partidas
        
    Returns:
        Tupla (novas, atualizadas)
    """
    db = SessionLocal()
    new_count = 0
    updated_count = 0
    
    try:
        for match_data in matches_data:
            # Verifica se a partida já existe
            existing = db.query(Match).filter(Match.id == match_data['id']).first()
            
            if existing:
                # Atualiza partida existente
                existing.home_player = match_data.get('home_player', 'Desconhecido')
                existing.away_player = match_data.get('away_player', 'Desconhecido')
                existing.home_club = match_data.get('home_club', 'N/A')
                existing.away_club = match_data.get('away_club', 'N/A')
                existing.home_score = match_data.get('home_score', 0)
                existing.away_score = match_data.get('away_score', 0)
                existing.status = match_data.get('status', 'unknown')
                existing.minute = match_data.get('minute', 0)
                existing.is_live = match_data.get('is_live', False)
                existing.tournament = match_data.get('tournament')
                existing.raw_data = match_data.get('raw_data')
                existing.updated_at = datetime.utcnow()
                
                updated_count += 1
            else:
                # Cria nova partida
                new_match = Match(
                    id=match_data['id'],
                    home_player=match_data.get('home_player', 'Desconhecido'),
                    away_player=match_data.get('away_player', 'Desconhecido'),
                    home_club=match_data.get('home_club', 'N/A'),
                    away_club=match_data.get('away_club', 'N/A'),
                    home_score=match_data.get('home_score', 0),
                    away_score=match_data.get('away_score', 0),
                    status=match_data.get('status', 'unknown'),
                    minute=match_data.get('minute', 0),
                    is_live=match_data.get('is_live', False),
                    tournament=match_data.get('tournament'),
                    start_time=match_data.get('start_time'),
                    raw_data=match_data.get('raw_data')
                )
                db.add(new_match)
                new_count += 1
        
        db.commit()
        logger.info(f"✅ Salvo: {new_count} novas, {updated_count} atualizadas")
        
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Erro ao salvar partidas: {str(e)}")
        raise
    finally:
        db.close()
    
    return new_count, updated_count


def get_live_matches():
    """Retorna todas as partidas ao vivo"""
    db = SessionLocal()
    try:
        matches = db.query(Match).filter(Match.is_live == True).all()
        return [match.to_dict() for match in matches]
    finally:
        db.close()


def get_all_matches(limit=100):
    """Retorna todas as partidas (limitado)"""
    db = SessionLocal()
    try:
        matches = db.query(Match).order_by(Match.updated_at.desc()).limit(limit).all()
        return [match.to_dict() for match in matches]
    finally:
        db.close()


def get_match_by_id(match_id: str):
    """Retorna uma partida específica por ID"""
    db = SessionLocal()
    try:
        match = db.query(Match).filter(Match.id == match_id).first()
        return match.to_dict() if match else None
    finally:
        db.close()


def get_stats():
    """Retorna estatísticas gerais"""
    db = SessionLocal()
    try:
        total = db.query(Match).count()
        live = db.query(Match).filter(Match.is_live == True).count()
        finished = db.query(Match).filter(Match.status == 'finished').count()
        
        return {
            'total_matches': total,
            'live_matches': live,
            'finished_matches': finished,
            'last_update': datetime.utcnow().isoformat()
        }
    finally:
        db.close()


if __name__ == "__main__":
    # Testa a inicialização do banco
    logging.basicConfig(level=logging.INFO)
    logger.info("Inicializando banco de dados...")
    init_db()
    logger.info("✅ Banco de dados pronto!")
    
    # Mostra estatísticas
    stats = get_stats()
    logger.info(f"📊 Estatísticas: {stats}")