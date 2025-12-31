"""
FIFA25 Bot - Aplicação Flask Principal
Com worker em background funcionando
"""

from flask import Flask, render_template, jsonify, request
from flask_sqlalchemy import SQLAlchemy
import os
import logging
from datetime import datetime, timedelta
import threading
import time

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Inicializar Flask
app = Flask(__name__)

# Configurações
app.config['SECRET_KEY'] = os.getenv('SESSION_SECRET', 'dev-secret-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///fifa25.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Corrigir URL do PostgreSQL (Render usa postgres:// mas SQLAlchemy precisa postgresql://)
if app.config['SQLALCHEMY_DATABASE_URI'].startswith('postgres://'):
    app.config['SQLALCHEMY_DATABASE_URI'] = app.config['SQLALCHEMY_DATABASE_URI'].replace('postgres://', 'postgresql://', 1)

# Inicializar banco de dados
db = SQLAlchemy(app)

# Importar modelos
from models import Match, Player, Tournament

# Variáveis globais para controle do scraper
scraper_running = False
last_scrape_time = None
scrape_count = 0

def init_db():
    """Inicializa o banco de dados"""
    with app.app_context():
        try:
            db.create_all()
            logger.info("✅ Banco de dados inicializado")
        except Exception as e:
            logger.error(f"❌ Erro ao inicializar banco: {e}")

def scraper_worker():
    """Worker que roda em background coletando dados"""
    global scraper_running, last_scrape_time, scrape_count
    
    # Configurações
    SCAN_INTERVAL = int(os.getenv('SCAN_INTERVAL', 30))
    RUN_SCRAPER = os.getenv('RUN_SCRAPER', 'true').lower() == 'true'
    
    logger.info("="*60)
    logger.info("🤖 WORKER INICIADO")
    logger.info(f"📊 RUN_SCRAPER: {RUN_SCRAPER}")
    logger.info(f"⏱️ SCAN_INTERVAL: {SCAN_INTERVAL} segundos")
    logger.info("="*60)
    
    if not RUN_SCRAPER:
        logger.warning("⚠️ Scraper DESATIVADO (RUN_SCRAPER=false)")
        return
    
    # Importar scraper
    try:
        from web_scraper import FIFA25Scraper
        scraper = FIFA25Scraper()
        logger.info("✅ Scraper importado com sucesso")
    except Exception as e:
        logger.error(f"❌ Erro ao importar scraper: {e}")
        return
    
    scraper_running = True
    
    while scraper_running:
        try:
            logger.info("\n" + "="*60)
            logger.info(f"🔄 INICIANDO COLETA #{scrape_count + 1}")
            logger.info(f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info("="*60)
            
            # Coletar partidas ao vivo
            live_matches = scraper.get_live_matches()
            logger.info(f"📺 Partidas ao vivo coletadas: {len(live_matches)}")
            
            # Coletar próximas partidas
            recent_matches = scraper.get_recent_matches()
            logger.info(f"📅 Próximas partidas coletadas: {len(recent_matches)}")
            
            # Salvar no banco de dados
            saved_count = 0
            with app.app_context():
                try:
                    # Salvar partidas ao vivo
                    for match_data in live_matches:
                        # Verificar se já existe
                        existing = Match.query.filter_by(
                            team1=match_data['team1'],
                            team2=match_data['team2'],
                            match_time=match_data['match_time']
                        ).first()
                        
                        if existing:
                            # Atualizar placar se mudou
                            if (existing.score1 != match_data['score1'] or 
                                existing.score2 != match_data['score2']):
                                existing.score1 = match_data['score1']
                                existing.score2 = match_data['score2']
                                existing.status = match_data['status']
                                logger.info(f"🔄 Atualizado: {match_data['team1']} {match_data['score1']}x{match_data['score2']} {match_data['team2']}")
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
                                status=match_data['status'],
                                scraped_at=match_data['scraped_at']
                            )
                            db.session.add(new_match)
                            saved_count += 1
                            logger.info(f"💾 Nova partida: {match_data['team1']} vs {match_data['team2']}")
                    
                    db.session.commit()
                    logger.info(f"✅ {saved_count} novas partidas salvas no banco")
                    
                except Exception as e:
                    logger.error(f"❌ Erro ao salvar no banco: {e}")
                    db.session.rollback()
            
            # Atualizar status
            last_scrape_time = datetime.now()
            scrape_count += 1
            
            logger.info(f"✅ Coleta #{scrape_count} concluída")
            logger.info(f"⏳ Próxima coleta em {SCAN_INTERVAL} segundos...")
            
            # Aguardar intervalo
            time.sleep(SCAN_INTERVAL)
            
        except KeyboardInterrupt:
            logger.info("⚠️ Worker interrompido pelo usuário")
            break
        except Exception as e:
            logger.error(f"❌ Erro no worker: {type(e).__name__}: {e}")
            logger.info("⏳ Aguardando 60s antes de tentar novamente...")
            time.sleep(60)
    
    scraper_running = False
    logger.info("🛑 Worker finalizado")

# ==================== ROTAS ====================

@app.route('/')
def index():
    """Página inicial - Dashboard"""
    return render_template('dashboard.html')

@app.route('/dashboard')
def dashboard():
    """Dashboard principal"""
    try:
        # Estatísticas básicas
        total_matches = Match.query.count()
        live_matches = Match.query.filter_by(status='live').count()
        today = datetime.now().date()
        today_matches = Match.query.filter(
            db.func.date(Match.scraped_at) == today
        ).count()
        
        stats = {
            'total_matches': total_matches,
            'live_matches': live_matches,
            'today_matches': today_matches,
            'last_scrape': last_scrape_time.strftime('%Y-%m-%d %H:%M:%S') if last_scrape_time else 'Nunca',
            'scrape_count': scrape_count,
            'scraper_status': 'Ativo' if scraper_running else 'Inativo'
        }
        
        return render_template('dashboard.html', stats=stats)
        
    except Exception as e:
        logger.error(f"Erro no dashboard: {e}")
        return render_template('dashboard.html', stats={})

@app.route('/matches')
def matches():
    """Página de partidas"""
    try:
        # Últimas 50 partidas
        all_matches = Match.query.order_by(Match.scraped_at.desc()).limit(50).all()
        return render_template('matches.html', matches=all_matches)
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
    """Status do bot em JSON"""
    return jsonify({
        'scraper_running': scraper_running,
        'last_scrape': last_scrape_time.isoformat() if last_scrape_time else None,
        'scrape_count': scrape_count,
        'total_matches': Match.query.count(),
        'live_matches': Match.query.filter_by(status='live').count()
    })

@app.route('/api/live')
def api_live():
    """Partidas ao vivo em JSON"""
    try:
        live = Match.query.filter_by(status='live').all()
        return jsonify([{
            'id': m.id,
            'team1': m.team1,
            'team2': m.team2,
            'score1': m.score1,
            'score2': m.score2,
            'player1': m.player1,
            'player2': m.player2,
            'tournament': m.tournament,
            'match_time': m.match_time
        } for m in live])
    except Exception as e:
        logger.error(f"Erro na API: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/health')
def health():
    """Health check para o Render"""
    try:
        # Testar conexão com banco
        db.session.execute(db.text('SELECT 1'))
        return jsonify({
            'status': 'healthy',
            'database': 'connected',
            'scraper': 'running' if scraper_running else 'stopped',
            'timestamp': datetime.now().isoformat()
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 500

# ==================== INICIALIZAÇÃO ====================

if __name__ == '__main__':
    # Inicializar banco de dados
    init_db()
    
    # Iniciar worker em thread separada
    worker_thread = threading.Thread(target=scraper_worker, daemon=True)
    worker_thread.start()
    logger.info("🚀 Worker thread iniciada")
    
    # Iniciar Flask
    port = int(os.getenv('PORT', 5000))
    logger.info(f"🌐 Iniciando Flask na porta {port}")
    app.run(host='0.0.0.0', port=port, debug=False)