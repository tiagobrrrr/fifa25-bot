# models.py - ARQUIVO COMPLETO ATUALIZADO
"""
Modelos do banco de dados para o Bot FIFA25
Inclui campos para armazenar resultados das partidas
"""

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class Match(db.Model):
    """Modelo para armazenar dados das partidas"""
    __tablename__ = 'matches'
    
    id = db.Column(db.Integer, primary_key=True)
    match_id = db.Column(db.String(50), unique=True, nullable=False, index=True)
    
    # Jogadores
    home_player = db.Column(db.String(100))
    away_player = db.Column(db.String(100))
    
    # Times
    home_team = db.Column(db.String(100))
    away_team = db.Column(db.String(100))
    
    # Informações da partida
    tournament = db.Column(db.String(200))
    location = db.Column(db.String(100), index=True)  # Estádio
    match_date = db.Column(db.DateTime)
    
    # Status da partida
    status = db.Column(db.String(20), default='scheduled', index=True)  # scheduled, live, finished
    
    # Placar durante a partida (opcional)
    current_score_home = db.Column(db.Integer, default=0)
    current_score_away = db.Column(db.Integer, default=0)
    current_minute = db.Column(db.Integer, default=0)
    
    # NOVOS CAMPOS: Resultado final
    final_score_home = db.Column(db.Integer, default=0)
    final_score_away = db.Column(db.Integer, default=0)
    winner = db.Column(db.String(100))  # Nome do jogador vencedor ou 'Empate'
    finished_at = db.Column(db.DateTime)  # Quando a partida terminou
    
    # Metadados
    stream_url = db.Column(db.String(500))
    url = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<Match {self.match_id}: {self.home_player} vs {self.away_player}>'
    
    def to_dict(self):
        """Converte o objeto para dicionário"""
        return {
            'id': self.id,
            'match_id': self.match_id,
            'home_player': self.home_player,
            'away_player': self.away_player,
            'home_team': self.home_team,
            'away_team': self.away_team,
            'tournament': self.tournament,
            'location': self.location,
            'match_date': self.match_date.isoformat() if self.match_date else None,
            'status': self.status,
            'current_score_home': self.current_score_home,
            'current_score_away': self.current_score_away,
            'current_minute': self.current_minute,
            'final_score_home': self.final_score_home,
            'final_score_away': self.final_score_away,
            'winner': self.winner,
            'finished_at': self.finished_at.isoformat() if self.finished_at else None,
            'stream_url': self.stream_url,
            'url': self.url,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    @property
    def is_finished(self):
        """Verifica se a partida está finalizada"""
        return self.status == 'finished'
    
    @property
    def is_live(self):
        """Verifica se a partida está ao vivo"""
        return self.status == 'live'
    
    @property
    def has_result(self):
        """Verifica se a partida tem resultado definido"""
        return self.final_score_home is not None and self.final_score_away is not None


class Player(db.Model):
    """Modelo para armazenar dados dos jogadores (opcional, para cache)"""
    __tablename__ = 'players'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False, index=True)
    
    # Estatísticas (podem ser calculadas dinamicamente, mas cache ajuda performance)
    total_matches = db.Column(db.Integer, default=0)
    wins = db.Column(db.Integer, default=0)
    losses = db.Column(db.Integer, default=0)
    draws = db.Column(db.Integer, default=0)
    goals_scored = db.Column(db.Integer, default=0)
    goals_conceded = db.Column(db.Integer, default=0)
    
    # Estádio principal (onde mais joga)
    main_stadium = db.Column(db.String(100))
    
    # Metadados
    first_match_date = db.Column(db.DateTime)
    last_match_date = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<Player {self.name}>'
    
    @property
    def win_rate(self):
        """Calcula taxa de vitória"""
        if self.total_matches == 0:
            return 0.0
        return (self.wins / self.total_matches) * 100
    
    @property
    def goal_difference(self):
        """Calcula saldo de gols"""
        return self.goals_scored - self.goals_conceded
    
    def to_dict(self):
        """Converte o objeto para dicionário"""
        return {
            'id': self.id,
            'name': self.name,
            'total_matches': self.total_matches,
            'wins': self.wins,
            'losses': self.losses,
            'draws': self.draws,
            'goals_scored': self.goals_scored,
            'goals_conceded': self.goals_conceded,
            'goal_difference': self.goal_difference,
            'win_rate': round(self.win_rate, 2),
            'main_stadium': self.main_stadium,
            'first_match_date': self.first_match_date.isoformat() if self.first_match_date else None,
            'last_match_date': self.last_match_date.isoformat() if self.last_match_date else None
        }


class Tournament(db.Model):
    """Modelo para armazenar dados dos torneios (opcional)"""
    __tablename__ = 'tournaments'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), unique=True, nullable=False)
    
    # Estatísticas do torneio
    total_matches = db.Column(db.Integer, default=0)
    total_goals = db.Column(db.Integer, default=0)
    
    # Metadados
    start_date = db.Column(db.DateTime)
    end_date = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Tournament {self.name}>'
    
    @property
    def avg_goals_per_match(self):
        """Média de gols por partida"""
        if self.total_matches == 0:
            return 0.0
        return round(self.total_goals / self.total_matches, 2)


# Funções auxiliares para trabalhar com o banco

def get_or_create_match(session, match_id, **kwargs):
    """
    Busca ou cria uma partida no banco
    
    Args:
        session: sessão do SQLAlchemy
        match_id: ID da partida
        **kwargs: dados da partida
        
    Returns:
        tuple: (match, created) onde created é True se foi criada
    """
    match = session.query(Match).filter_by(match_id=match_id).first()
    
    if match:
        # Atualiza dados existentes
        for key, value in kwargs.items():
            if hasattr(match, key):
                setattr(match, key, value)
        match.updated_at = datetime.utcnow()
        return match, False
    else:
        # Cria nova partida
        match = Match(match_id=match_id, **kwargs)
        session.add(match)
        return match, True


def update_player_stats(session, player_name):
    """
    Atualiza estatísticas de um jogador baseado em suas partidas
    
    Args:
        session: sessão do SQLAlchemy
        player_name: nome do jogador
    """
    from sqlalchemy import or_
    
    # Busca ou cria jogador
    player = session.query(Player).filter_by(name=player_name).first()
    if not player:
        player = Player(name=player_name)
        session.add(player)
    
    # Busca todas as partidas finalizadas do jogador
    matches = session.query(Match).filter(
        Match.status == 'finished',
        or_(Match.home_player == player_name, Match.away_player == player_name)
    ).all()
    
    # Reseta estatísticas
    player.total_matches = len(matches)
    player.wins = 0
    player.losses = 0
    player.draws = 0
    player.goals_scored = 0
    player.goals_conceded = 0
    
    stadiums = {}
    
    for match in matches:
        # Identifica se é home ou away
        is_home = match.home_player == player_name
        
        # Contabiliza gols
        if is_home:
            player.goals_scored += match.final_score_home or 0
            player.goals_conceded += match.final_score_away or 0
        else:
            player.goals_scored += match.final_score_away or 0
            player.goals_conceded += match.final_score_home or 0
        
        # Contabiliza resultado
        if match.winner == player_name:
            player.wins += 1
        elif match.winner == 'Empate':
            player.draws += 1
        else:
            player.losses += 1
        
        # Conta estádios
        if match.location:
            stadiums[match.location] = stadiums.get(match.location, 0) + 1
        
        # Atualiza datas
        if not player.first_match_date or (match.match_date and match.match_date < player.first_match_date):
            player.first_match_date = match.match_date
        
        if not player.last_match_date or (match.match_date and match.match_date > player.last_match_date):
            player.last_match_date = match.match_date
    
    # Define estádio principal
    if stadiums:
        player.main_stadium = max(stadiums.items(), key=lambda x: x[1])[0]
    
    player.updated_at = datetime.utcnow()
    session.commit()
    
    return player


def get_match_statistics():
    """
    Retorna estatísticas gerais das partidas
    
    Returns:
        dict com estatísticas
    """
    from sqlalchemy import func
    
    total = Match.query.count()
    finished = Match.query.filter_by(status='finished').count()
    live = Match.query.filter_by(status='live').count()
    scheduled = Match.query.filter_by(status='scheduled').count()
    
    # Total de gols
    total_goals = db.session.query(
        func.sum(Match.final_score_home + Match.final_score_away)
    ).filter(Match.status == 'finished').scalar() or 0
    
    return {
        'total_matches': total,
        'finished': finished,
        'live': live,
        'scheduled': scheduled,
        'total_goals': total_goals,
        'avg_goals_per_match': round(total_goals / finished, 2) if finished > 0 else 0
    }


if __name__ == '__main__':
    # Testes básicos
    print("Modelos definidos com sucesso!")
    print("\nModelos disponíveis:")
    print("- Match")
    print("- Player")
    print("- Tournament")
