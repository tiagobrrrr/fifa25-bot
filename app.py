"""
FIFA25 Bot - Aplicação Flask
Apenas interface web (worker roda separadamente)
"""

from flask import Flask, render_template, jsonify
from flask_sqlalchemy import SQLAlchemy
import os
import logging
from datetime import datetime

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Inicializar Flask
app = Flask(__name__)

# Configurações
app.config['SECRET_KEY'] = os.getenv('SESSION_SECRET', 'dev-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
    'DATABASE_URL', 
    'sqlite:///fifa25.db'
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Corrigir URL PostgreSQL
if app.config['SQLALCHEMY_DATABASE_URI'].startswith('postgres://'):
    app.config['SQLALCHEMY_DATABASE_URI'] = app.config[
        'SQLALCHEMY_DATABASE_URI'
    ].replace('postgres://', 'postgresql://', 1)

# Inicializar banco
db = SQLAlchemy(app)

# ==================== MODELOS ====================

class Match(db.Model):
    """Modelo para partidas"""
    __tablename__ = 'matches'
    
    id = db.Column(db.Integer, primary_key=True)
    team1 = db.Column(db.String(100), nullable=False)
    team2 = db.Column(db.String(100), nullable=False)
    player1 = db.Column(db.String(100))
    player2 = db.Column(db.String(100))
    score1 = db.Column(db.Integer, default=0)
    score2 = db.Column(db.Integer, default=0)
    tournament = db.Column(db.String(200))
    match_time = db.Column(db.String(50))
    location = db.Column(db.String(100))
    status = db.Column(db.String(20), default='live')
    scraped_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'team1': self.team1,
            'team2': self.team2,
            'player1': self.player1,
            'player2': self.player2,
            'score1': self.score1,
            'score2': self.score2,
            'tournament': self.tournament,
            'status': self.status,
            'match_time': self.match_time
        }

class Player(db.Model):
    """Modelo para jogadores"""
    __tablename__ = 'players'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    matches_played = db.Column(db.Integer, default=0)
    wins = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Tournament(db.Model):
    """Modelo para torneios"""
    __tablename__ = 'tournaments'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    status = db.Column(db.String(20), default='in_progress')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# ==================== ROTAS ====================

@app.route('/')
def index():
    """Página inicial"""
    try:
        # Estatísticas
        total = Match.query.count()
        live = Match.query.filter_by(status='live').count()
        today = datetime.now().date()
        today_matches = Match.query.filter(
            db.func.date(Match.scraped_at) == today
        ).count()
        
        # Última atualização
        last_match = Match.query.order_by(
            Match.scraped_at.desc()
        ).first()
        
        stats = {
            'total_matches': total,
            'live_matches': live,
            'today_matches': today_matches,
            'last_update': last_match.scraped_at.strftime(
                '%Y-%m-%d %H:%M:%S'
            ) if last_match else 'Nunca',
            'scraper_status': 'Ativo' if total > 0 else 'Aguardando'
        }
        
        # Últimas 10 partidas
        recent = Match.query.order_by(
            Match.scraped_at.desc()
        ).limit(10).all()
        
        return render_template(
            'dashboard.html', 
            stats=stats,
            recent_matches=recent
        )
        
    except Exception as e:
        logger.error(f"Erro no dashboard: {e}")
        return render_template('dashboard.html', stats={}, recent_matches=[])

@app.route('/matches')
def matches():
    """Página de partidas"""
    try:
        page = int(request.args.get('page', 1))
        per_page = 50
        
        pagination = Match.query.order_by(
            Match.scraped_at.desc()
        ).paginate(
            page=page, 
            per_page=per_page, 
            error_out=False
        )
        
        return render_template(
            'matches.html', 
            matches=pagination.items,
            pagination=pagination
        )
    except Exception as e:
        logger.error(f"Erro ao buscar partidas: {e}")
        return render_template('matches.html', matches=[])

@app.route('/players')
def players():
    """Página de jogadores"""
    try:
        all_players = Player.query.all()
        return render_template('players.html', players=all_players)
    except Exception as e:
        logger.error(f"Erro ao buscar jogadores: {e}")
        return render_template('players.html', players=[])

@app.route('/api/status')
def api_status():
    """Status do bot"""
    try:
        total = Match.query.count()
        live = Match.query.filter_by(status='live').count()
        
        last_match = Match.query.order_by(
            Match.scraped_at.desc()
        ).first()
        
        return jsonify({
            'status': 'online',
            'total_matches': total,
            'live_matches': live,
            'last_scrape': last_match.scraped_at.isoformat() if last_match else None,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/live')
def api_live():
    """Partidas ao vivo"""
    try:
        live_matches = Match.query.filter_by(status='live').all()
        return jsonify([m.to_dict() for m in live_matches])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/recent')
def api_recent():
    """Partidas recentes"""
    try:
        limit = int(request.args.get('limit', 20))
        recent = Match.query.order_by(
            Match.scraped_at.desc()
        ).limit(limit).all()
        return jsonify([m.to_dict() for m in recent])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/health')
def health():
    """Health check"""
    try:
        db.session.execute(db.text('SELECT 1'))
        return jsonify({
            'status': 'healthy',
            'database': 'connected',
            'timestamp': datetime.now().isoformat()
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 500

# ==================== INICIALIZAÇÃO ====================

with app.app_context():
    try:
        db.create_all()
        logger.info("✅ Banco de dados inicializado")
    except Exception as e:
        logger.error(f"❌ Erro ao inicializar banco: {e}")

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)