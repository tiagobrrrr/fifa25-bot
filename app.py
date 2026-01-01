"""
FIFA25 Bot - Aplicação Completa
Com APScheduler + Endpoints Admin + Dashboard
"""

from flask import Flask, render_template, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import os
import logging
from datetime import datetime
import atexit

# ==================== CONFIGURAÇÃO ====================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Inicializar Flask
app = Flask(__name__)

# Configurações
app.config['SECRET_KEY'] = os.getenv('SESSION_SECRET', 'dev-secret-key-change-me')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///fifa25.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Corrigir URL PostgreSQL (Render usa postgres:// mas SQLAlchemy precisa postgresql://)
if app.config['SQLALCHEMY_DATABASE_URI'].startswith('postgres://'):
    app.config['SQLALCHEMY_DATABASE_URI'] = app.config['SQLALCHEMY_DATABASE_URI'].replace(
        'postgres://', 
        'postgresql://', 
        1
    )

# Inicializar banco
db = SQLAlchemy(app)

# Variáveis globais
scrape_count = 0
last_scrape_time = None
scraper_active = False

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
            'match_time': self.match_time,
            'status': self.status,
            'scraped_at': self.scraped_at.strftime('%Y-%m-%d %H:%M:%S') if self.scraped_at else None
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

# ==================== SCRAPER JOB ====================

def scrape_job():
    """Job executado periodicamente pelo scheduler"""
    global scrape_count, last_scrape_time, scraper_active
    
    if not scraper_active:
        return
    
    scrape_count += 1
    
    logger.info("=" * 70)
    logger.info(f"🔄 COLETA #{scrape_count}")
    logger.info(f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 70)
    
    try:
        from web_scraper import FIFA25Scraper
        
        scraper = FIFA25Scraper()
        
        # Coletar partidas ao vivo
        live_matches = scraper.get_live_matches()
        logger.info(f"📺 Coletadas {len(live_matches)} partidas ao vivo")
        
        # Salvar no banco
        saved = 0
        updated = 0
        
        with app.app_context():
            for match_data in live_matches:
                # Verificar se já existe
                existing = Match.query.filter_by(
                    team1=match_data['team1'],
                    team2=match_data['team2'],
                    match_time=match_data['match_time']
                ).first()
                
                if existing:
                    # Atualizar se mudou
                    if (existing.score1 != match_data['score1'] or 
                        existing.score2 != match_data['score2']):
                        existing.score1 = match_data['score1']
                        existing.score2 = match_data['score2']
                        existing.status = match_data['status']
                        existing.scraped_at = datetime.now()
                        updated += 1
                        logger.info(
                            f"🔄 Atualizado: {match_data['team1']} "
                            f"{match_data['score1']}x{match_data['score2']} "
                            f"{match_data['team2']}"
                        )
                else:
                    # Criar nova partida
                    new_match = Match(
                        team1=match_data['team1'],
                        team2=match_data['team2'],
                        player1=match_data.get('player1'),
                        player2=match_data.get('player2'),
                        score1=match_data['score1'],
                        score2=match_data['score2'],
                        tournament=match_data.get('tournament'),
                        match_time=match_data['match_time'],
                        location=match_data.get('location'),
                        status=match_data['status'],
                        scraped_at=datetime.now()
                    )
                    db.session.add(new_match)
                    saved += 1
                    logger.info(
                        f"💾 Nova: {match_data['team1']} vs {match_data['team2']}"
                    )
            
            db.session.commit()
            
            if saved > 0 or updated > 0:
                logger.info(f"💾 Salvas: {saved} | Atualizadas: {updated}")
            else:
                logger.info("⚠️  Nenhuma partida nova ou atualizada")
        
        last_scrape_time = datetime.now()
        logger.info(f"✅ Coleta #{scrape_count} concluída")
        logger.info("=" * 70)
        
    except Exception as e:
        logger.error(f"❌ Erro na coleta: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

# ==================== ROTAS PRINCIPAIS ====================

@app.route('/')
def index():
    """Dashboard principal"""
    try:
        # Estatísticas
        total = Match.query.count()
        live = Match.query.filter_by(status='live').count()
        today = datetime.now().date()
        today_matches = Match.query.filter(
            db.func.date(Match.scraped_at) == today
        ).count()
        
        stats = {
            'total_matches': total,
            'live_matches': live,
            'today_matches': today_matches,
            'scrape_count': scrape_count,
            'last_scrape': last_scrape_time.strftime('%Y-%m-%d %H:%M:%S') if last_scrape_time else 'Nunca',
            'scraper_status': 'Ativo ✅' if scraper_active else 'Inativo ❌'
        }
        
        # Últimas 10 partidas
        recent = Match.query.order_by(Match.scraped_at.desc()).limit(10).all()
        
        return render_template('dashboard.html', stats=stats, recent_matches=recent)
        
    except Exception as e:
        logger.error(f"Erro no dashboard: {e}")
        return render_template('dashboard.html', stats={}, recent_matches=[])

@app.route('/matches')
def matches():
    """Página de todas as partidas"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = 50
        
        pagination = Match.query.order_by(
            Match.scraped_at.desc()
        ).paginate(page=page, per_page=per_page, error_out=False)
        
        return render_template(
            'matches.html', 
            matches=pagination.items,
            pagination=pagination
        )
    except Exception as e:
        logger.error(f"Erro em /matches: {e}")
        all_matches = Match.query.order_by(Match.scraped_at.desc()).limit(100).all()
        return render_template('matches.html', matches=all_matches)

@app.route('/players')
def players():
    """Página de jogadores"""
    try:
        all_players = Player.query.all()
        return render_template('players.html', players=all_players)
    except Exception as e:
        logger.error(f"Erro em /players: {e}")
        return render_template('players.html', players=[])

# ==================== API ENDPOINTS ====================

@app.route('/api/status')
def api_status():
    """Status do bot em JSON"""
    try:
        total = Match.query.count()
        live = Match.query.filter_by(status='live').count()
        
        return jsonify({
            'status': 'online',
            'scraper_active': scraper_active,
            'scrape_count': scrape_count,
            'last_scrape': last_scrape_time.isoformat() if last_scrape_time else None,
            'total_matches': total,
            'live_matches': live,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/live')
def api_live():
    """Partidas ao vivo em JSON"""
    try:
        live_matches = Match.query.filter_by(status='live').all()
        return jsonify([m.to_dict() for m in live_matches])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/recent')
def api_recent():
    """Partidas recentes em JSON"""
    try:
        limit = request.args.get('limit', 20, type=int)
        recent = Match.query.order_by(Match.scraped_at.desc()).limit(limit).all()
        return jsonify([m.to_dict() for m in recent])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/health')
def health():
    """Health check para monitoramento"""
    try:
        # Testar conexão com banco
        db.session.execute(text('SELECT 1'))
        
        return jsonify({
            'status': 'healthy',
            'database': 'connected',
            'scraper': 'active' if scraper_active else 'inactive',
            'timestamp': datetime.now().isoformat()
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 500

# ==================== ADMIN ENDPOINTS ====================

@app.route('/admin/reset')
def admin_reset():
    """⚠️ Reseta banco completamente (apaga tudo!)"""
    
    # Proteção: requer confirmação
    if request.args.get('confirm') != 'yes':
        return jsonify({
            'status': 'warning',
            'message': '⚠️ Para confirmar, adicione ?confirm=yes na URL',
            'warning': 'Isso vai APAGAR TODOS os dados!',
            'example': request.url + '?confirm=yes'
        })
    
    try:
        logger.warning("⚠️  RESETANDO BANCO DE DADOS!")
        
        with db.engine.connect() as conn:
            # Dropar tabelas antigas
            logger.info("🗑️  Removendo tabelas antigas...")
            conn.execute(text("DROP TABLE IF EXISTS matches CASCADE"))
            conn.execute(text("DROP TABLE IF EXISTS players CASCADE"))
            conn.execute(text("DROP TABLE IF EXISTS tournaments CASCADE"))
            
            # Criar nova estrutura
            logger.info("🔧 Criando nova estrutura...")
            
            conn.execute(text("""
                CREATE TABLE matches (
                    id SERIAL PRIMARY KEY,
                    team1 VARCHAR(100) NOT NULL,
                    team2 VARCHAR(100) NOT NULL,
                    player1 VARCHAR(100),
                    player2 VARCHAR(100),
                    score1 INTEGER DEFAULT 0,
                    score2 INTEGER DEFAULT 0,
                    tournament VARCHAR(200),
                    match_time VARCHAR(50),
                    location VARCHAR(100),
                    status VARCHAR(20) DEFAULT 'live',
                    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            
            conn.execute(text("""
                CREATE TABLE players (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100) UNIQUE NOT NULL,
                    matches_played INTEGER DEFAULT 0,
                    wins INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            
            conn.execute(text("""
                CREATE TABLE tournaments (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(200) NOT NULL,
                    status VARCHAR(20) DEFAULT 'in_progress',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            
            conn.commit()
            
        logger.info("✅ Banco resetado com sucesso!")
        
        return jsonify({
            'status': 'success',
            'message': '✅ Banco resetado com sucesso!',
            'action': 'reset',
            'next_step': 'Reinicie o serviço no Render Dashboard',
            'note': 'O scraper começará a coletar novos dados automaticamente'
        })
        
    except Exception as e:
        logger.error(f"❌ Erro ao resetar: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/admin/migrate')
def admin_migrate():
    """Migra banco para nova estrutura (sem apagar dados)"""
    try:
        logger.info("🔄 Iniciando migração...")
        
        with db.engine.connect() as conn:
            # Verificar se score1 já existe
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='matches' AND column_name='score1'
            """))
            
            if result.fetchone():
                return jsonify({
                    'status': 'info',
                    'message': '✅ Banco já está atualizado!',
                    'action': 'none'
                })
            
            # Adicionar colunas novas
            logger.info("➕ Adicionando score1 e score2...")
            conn.execute(text("ALTER TABLE matches ADD COLUMN IF NOT EXISTS score1 INTEGER DEFAULT 0"))
            conn.execute(text("ALTER TABLE matches ADD COLUMN IF NOT EXISTS score2 INTEGER DEFAULT 0"))
            
            # Remover coluna antiga
            logger.info("🗑️  Removendo coluna 'score' antiga...")
            conn.execute(text("ALTER TABLE matches DROP COLUMN IF EXISTS score"))
            
            conn.commit()
            
        logger.info("✅ Migração concluída!")
        
        return jsonify({
            'status': 'success',
            'message': '✅ Banco migrado com sucesso!',
            'action': 'migrated',
            'next_step': 'Reinicie o serviço no Render'
        })
        
    except Exception as e:
        logger.error(f"❌ Erro na migração: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e),
            'hint': 'Tente usar /admin/reset?confirm=yes para resetar completamente'
        }), 500

@app.route('/admin/check')
def admin_check():
    """Verifica estrutura do banco"""
    try:
        with db.engine.connect() as conn:
            # Listar colunas
            result = conn.execute(text("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name='matches'
                ORDER BY ordinal_position
            """))
            
            columns = [{'name': row[0], 'type': row[1]} for row in result]
            
            # Contar registros
            count_result = conn.execute(text("SELECT COUNT(*) FROM matches"))
            total = count_result.fetchone()[0]
            
            has_score1 = any(c['name'] == 'score1' for c in columns)
            has_score2 = any(c['name'] == 'score2' for c in columns)
            
            return jsonify({
                'status': 'success',
                'table': 'matches',
                'columns': columns,
                'total_records': total,
                'has_score1': has_score1,
                'has_score2': has_score2,
                'structure_ok': has_score1 and has_score2,
                'recommendation': 'Estrutura OK!' if (has_score1 and has_score2) else 'Use /admin/reset?confirm=yes para corrigir'
            })
            
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

# ==================== INICIALIZAÇÃO ====================

# Criar tabelas
with app.app_context():
    try:
        db.create_all()
        logger.info("✅ Banco de dados inicializado")
    except Exception as e:
        logger.error(f"❌ Erro ao inicializar banco: {e}")

# Configurar e iniciar scheduler
RUN_SCRAPER = os.getenv('RUN_SCRAPER', 'true').lower() == 'true'
SCAN_INTERVAL = int(os.getenv('SCAN_INTERVAL', 30))

if RUN_SCRAPER:
    logger.info("=" * 70)
    logger.info("🤖 INICIANDO SCHEDULER")
    logger.info(f"⏱️  Intervalo: {SCAN_INTERVAL} segundos")
    logger.info("=" * 70)
    
    try:
        scheduler = BackgroundScheduler()
        scheduler.add_job(
            func=scrape_job,
            trigger=IntervalTrigger(seconds=SCAN_INTERVAL),
            id='scrape_job',
            name='Coletar partidas FIFA25',
            replace_existing=True
        )
        scheduler.start()
        scraper_active = True
        
        logger.info("✅ Scheduler iniciado com sucesso!")
        
        # Executar primeira coleta imediatamente
        logger.info("🚀 Executando primeira coleta...")
        with app.app_context():
            scrape_job()
        
        # Parar scheduler ao fechar app
        atexit.register(lambda: scheduler.shutdown())
        
    except Exception as e:
        logger.error(f"❌ Erro ao iniciar scheduler: {e}")
        import traceback
        traceback.print_exc()
else:
    logger.warning("=" * 70)
    logger.warning("⚠️  SCRAPER DESATIVADO!")
    logger.warning("⚠️  Configure RUN_SCRAPER=true no Render")
    logger.warning("=" * 70)

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    logger.info(f"🌐 Iniciando Flask na porta {port}")
    app.run(host='0.0.0.0', port=port, debug=False)