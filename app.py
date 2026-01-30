"""
FIFA 25 Bot - Aplicação Flask Principal
Monitoramento de partidas do ESportsBattle
"""

import os
import logging
from datetime import datetime, timedelta
from flask import Flask, render_template, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import atexit

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Inicialização do Flask
app = Flask(__name__)

# Configurações
app.config['SECRET_KEY'] = os.environ.get('SESSION_SECRET', 'dev-secret-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///fifa25.db')
if app.config['SQLALCHEMY_DATABASE_URI'].startswith('postgres://'):
    app.config['SQLALCHEMY_DATABASE_URI'] = app.config['SQLALCHEMY_DATABASE_URI'].replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,
    'pool_recycle': 300,
}

# Inicialização do banco de dados
db = SQLAlchemy(app)

# Importar modelos após inicializar db
from models import Match, Player, Analysis, Tournament

# Importar serviços
from web_scraper import FIFA25Scraper
from data_analyzer import DataAnalyzer
try:
    from telegram_service import TelegramService
    telegram_enabled = True
except:
    telegram_enabled = False
    logger.warning("⚠️ Telegram service não disponível")

try:
    from email_service import EmailService
    email_enabled = True
except:
    email_enabled = False
    logger.warning("⚠️ Email service não disponível")

# Variáveis globais
scraper = FIFA25Scraper()
analyzer = DataAnalyzer()
telegram = TelegramService() if telegram_enabled else None
email_service = EmailService() if email_enabled else None

# Configurações do scheduler
SCAN_INTERVAL = int(os.environ.get('SCAN_INTERVAL', 30))
RUN_SCRAPER = os.environ.get('RUN_SCRAPER', 'true').lower() == 'true'

# Estatísticas globais
stats = {
    'last_scan': None,
    'total_scans': 0,
    'total_matches': 0,
    'errors': 0,
    'status': 'Iniciando...'
}


def init_db():
    """Inicializa o banco de dados"""
    with app.app_context():
        try:
            db.create_all()
            logger.info("✅ Banco de dados inicializado")
        except Exception as e:
            logger.error(f"❌ Erro ao inicializar banco: {e}")


def run_scraper():
    """Executa o scraper de forma assíncrona"""
    if not RUN_SCRAPER:
        logger.info("⏸️ Scraper desabilitado (RUN_SCRAPER=false)")
        return
    
    with app.app_context():
        try:
            stats['status'] = 'Executando scraper...'
            logger.info("🔄 Iniciando varredura...")
            
            # 1. Buscar partidas próximas (endpoint principal)
            nearest_matches = scraper.get_nearest_matches()
            logger.info(f"📊 Encontradas {len(nearest_matches)} partidas próximas")
            
            # 2. Buscar partidas em streaming
            streaming_matches = scraper.get_streaming_matches()
            logger.info(f"📺 Encontradas {len(streaming_matches)} partidas em streaming")
            
            # 3. Processar e salvar no banco
            total_saved = 0
            
            # Processar nearest matches
            for match_data in nearest_matches:
                try:
                    match = save_match(match_data)
                    if match:
                        total_saved += 1
                except Exception as e:
                    logger.error(f"Erro ao salvar partida {match_data.get('id')}: {e}")
            
            # Processar streaming matches
            for match_data in streaming_matches:
                try:
                    match = save_match(match_data)
                    if match:
                        total_saved += 1
                except Exception as e:
                    logger.error(f"Erro ao salvar partida streaming {match_data.get('id')}: {e}")
            
            # Atualizar estatísticas
            stats['last_scan'] = datetime.now()
            stats['total_scans'] += 1
            stats['total_matches'] = Match.query.count()
            stats['status'] = 'Online'
            
            logger.info(f"✅ Varredura completa: {total_saved} partidas salvas")
            
            # Enviar notificações se habilitado
            if telegram and total_saved > 0:
                try:
                    telegram.send_notification(f"🎮 {total_saved} novas partidas detectadas!")
                except:
                    pass
            
        except Exception as e:
            stats['errors'] += 1
            stats['status'] = f'Erro: {str(e)[:50]}'
            logger.error(f"❌ Erro no scraper: {e}")
            
            if telegram:
                try:
                    telegram.send_error(f"Erro no scraper: {e}")
                except:
                    pass


def save_match(match_data):
    """Salva ou atualiza uma partida no banco de dados"""
    try:
        match_id = match_data.get('id')
        if not match_id:
            return None
        
        # Verificar se já existe
        match = Match.query.filter_by(match_id=match_id).first()
        
        if not match:
            match = Match()
            match.match_id = match_id
        
        # Atualizar dados
        match.status_id = match_data.get('status_id', 1)
        match.date = datetime.fromisoformat(match_data.get('date', '').replace('Z', '+00:00')) if match_data.get('date') else None
        match.tournament_id = match_data.get('tournament_id')
        
        # Location
        location = match_data.get('location', {})
        match.location_code = location.get('code')
        match.location_name = location.get('token_international', location.get('token'))
        match.location_color = location.get('color')
        
        # Console
        console = match_data.get('console', {})
        match.console_id = console.get('id')
        match.console_token = console.get('token_international', console.get('token'))
        
        # Participant 1
        p1 = match_data.get('participant1', {})
        match.player1_id = p1.get('id')
        match.player1_nickname = p1.get('nickname')
        match.player1_photo = p1.get('photo')
        
        team1 = p1.get('team', {})
        match.player1_team_id = team1.get('id')
        match.player1_team_name = team1.get('token_international', team1.get('token'))
        match.player1_team_logo = team1.get('logo')
        
        # Participant 2
        p2 = match_data.get('participant2', {})
        match.player2_id = p2.get('id')
        match.player2_nickname = p2.get('nickname')
        match.player2_photo = p2.get('photo')
        
        team2 = p2.get('team', {})
        match.player2_team_id = team2.get('id')
        match.player2_team_name = team2.get('token_international', team2.get('token'))
        match.player2_team_logo = team2.get('logo')
        
        # Score
        match.score1 = match_data.get('score1')
        match.score2 = match_data.get('score2')
        
        # Tournament info
        tournament = match_data.get('tournament', {})
        match.tournament_token = tournament.get('token_international', tournament.get('token'))
        
        match.updated_at = datetime.now()
        
        db.session.merge(match)
        db.session.commit()
        
        return match
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao salvar partida: {e}")
        return None


# ==================== ROTAS ====================

@app.route('/')
def index():
    """Página inicial - Dashboard"""
    return render_template('dashboard.html', stats=stats)


@app.route('/matches')
def matches():
    """Página de partidas"""
    status_filter = request.args.get('status', 'all')
    
    query = Match.query
    
    if status_filter == 'live':
        query = query.filter_by(status_id=2)
    elif status_filter == 'upcoming':
        query = query.filter_by(status_id=1)
    elif status_filter == 'finished':
        query = query.filter_by(status_id=3)
    
    matches = query.order_by(Match.date.desc()).limit(100).all()
    
    return render_template('matches.html', matches=matches, status=status_filter)


@app.route('/players')
def players():
    """Página de jogadores"""
    # Buscar jogadores únicos
    players_data = db.session.query(
        Match.player1_id,
        Match.player1_nickname,
        Match.player1_photo,
        db.func.count(Match.id).label('matches_count')
    ).filter(
        Match.player1_id.isnot(None)
    ).group_by(
        Match.player1_id,
        Match.player1_nickname,
        Match.player1_photo
    ).all()
    
    return render_template('players.html', players=players_data)


@app.route('/reports')
def reports():
    """Página de relatórios"""
    today = datetime.now().date()
    
    # Estatísticas do dia
    today_matches = Match.query.filter(
        db.func.date(Match.date) == today
    ).count()
    
    live_matches = Match.query.filter_by(status_id=2).count()
    finished_today = Match.query.filter(
        db.func.date(Match.date) == today,
        Match.status_id == 3
    ).count()
    
    report_data = {
        'today_matches': today_matches,
        'live_matches': live_matches,
        'finished_today': finished_today,
        'total_matches': Match.query.count()
    }
    
    return render_template('reports.html', report=report_data)


# ==================== API ENDPOINTS ====================

@app.route('/api/stats')
def api_stats():
    """Retorna estatísticas do bot"""
    return jsonify({
        'last_scan': stats['last_scan'].isoformat() if stats['last_scan'] else None,
        'total_scans': stats['total_scans'],
        'total_matches': stats['total_matches'],
        'errors': stats['errors'],
        'status': stats['status'],
        'scraper_enabled': RUN_SCRAPER,
        'scan_interval': SCAN_INTERVAL
    })


@app.route('/api/matches/live')
def api_live_matches():
    """Retorna partidas ao vivo"""
    matches = Match.query.filter_by(status_id=2).order_by(Match.date.desc()).limit(20).all()
    return jsonify([m.to_dict() for m in matches])


@app.route('/api/matches/upcoming')
def api_upcoming_matches():
    """Retorna próximas partidas"""
    matches = Match.query.filter_by(status_id=1).order_by(Match.date.asc()).limit(20).all()
    return jsonify([m.to_dict() for m in matches])


@app.route('/api/matches/recent')
def api_recent_matches():
    """Retorna partidas recentes"""
    matches = Match.query.order_by(Match.updated_at.desc()).limit(50).all()
    return jsonify([m.to_dict() for m in matches])


@app.route('/api/force-scan')
def api_force_scan():
    """Força uma varredura imediata"""
    try:
        run_scraper()
        return jsonify({'success': True, 'message': 'Varredura iniciada'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== SCHEDULER ====================

def setup_scheduler():
    """Configura o scheduler para executar o scraper periodicamente"""
    scheduler = BackgroundScheduler()
    
    scheduler.add_job(
        func=run_scraper,
        trigger=IntervalTrigger(seconds=SCAN_INTERVAL),
        id='scraper_job',
        name='Scraper FIFA25 ESportsBattle',
        replace_existing=True
    )
    
    scheduler.start()
    logger.info(f"✅ Scheduler configurado: intervalo de {SCAN_INTERVAL}s")
    
    # Desligar o scheduler quando a aplicação fechar
    atexit.register(lambda: scheduler.shutdown())
    
    return scheduler


# ==================== INICIALIZAÇÃO ====================

# Inicializar banco de dados
init_db()

# Configurar scheduler
if RUN_SCRAPER:
    scheduler = setup_scheduler()
    logger.info("✅ Scheduler iniciado com sucesso")
else:
    logger.warning("⚠️ Scraper desabilitado")

# Executar primeira varredura ao iniciar
with app.app_context():
    run_scraper()


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    app.run(host='0.0.0.0', port=port, debug=debug)