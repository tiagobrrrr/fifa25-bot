from flask import Flask, render_template, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from datetime import datetime, timedelta
import os
import logging
import pytz

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Inicialização do Flask
app = Flask(__name__)
CORS(app)

# Configurações
app.config['SECRET_KEY'] = os.environ.get('SESSION_SECRET', 'dev-secret-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///fifa25.db')

# Timezone de Brasília
BRAZIL_TZ = pytz.timezone('America/Sao_Paulo')

# Fix para Heroku/Render (postgres:// -> postgresql://)
if app.config['SQLALCHEMY_DATABASE_URI'].startswith('postgres://'):
    app.config['SQLALCHEMY_DATABASE_URI'] = app.config['SQLALCHEMY_DATABASE_URI'].replace('postgres://', 'postgresql://', 1)

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,
    'pool_recycle': 300,
}

# Inicialização do banco de dados
db = SQLAlchemy(app)

# Import e criação dos models DEPOIS do db ser criado
from models import create_models
Match, Tournament, Player, ScraperLog = create_models(db)

# ==================== ROTAS WEB ====================

@app.route('/')
def index():
    """Página principal - Dashboard"""
    try:
        # Estatísticas gerais
        total_matches = Match.query.count()
        total_players = Player.query.count()
        live_matches = Match.query.filter_by(status_id=2).count()
        
        # Última execução do scraper (converter para horário de Brasília)
        last_scan = ScraperLog.query.order_by(ScraperLog.timestamp.desc()).first()
        if last_scan and last_scan.timestamp:
            # Converter UTC para Brasília
            utc_time = last_scan.timestamp.replace(tzinfo=pytz.UTC)
            last_scan.timestamp = utc_time.astimezone(BRAZIL_TZ)
        
        # Top 10 jogadores
        top_players = Player.query.filter(
            Player.total_matches >= 3
        ).order_by(
            Player.wins.desc()
        ).limit(10).all()
        
        return render_template('dashboard.html',
            total_matches=total_matches,
            total_players=total_players,
            live_matches=live_matches,
            last_scan=last_scan,
            top_players=top_players
        )
    except Exception as e:
        logger.error(f"Erro na página inicial: {e}", exc_info=True)
        return render_template('error.html', error=str(e)), 500


@app.route('/matches')
def matches():
    """Página de partidas"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = 50
        
        # Filtros
        status = request.args.get('status', 'all')
        location = request.args.get('location', 'all')
        
        query = Match.query
        
        if status != 'all':
            query = query.filter_by(status_id=int(status))
        
        if location != 'all':
            query = query.filter_by(location=location)
        
        matches_pagination = query.order_by(
            Match.date.desc()
        ).paginate(page=page, per_page=per_page, error_out=False)
        
        # Locations disponíveis
        locations = db.session.query(Match.location).distinct().all()
        locations = [loc[0] for loc in locations]
        
        return render_template('matches.html',
            matches=matches_pagination.items,
            pagination=matches_pagination,
            locations=locations,
            current_status=status,
            current_location=location
        )
    except Exception as e:
        logger.error(f"Erro na página de partidas: {e}", exc_info=True)
        return render_template('error.html', error=str(e)), 500


@app.route('/players')
def players():
    """Página de jogadores"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = 30
        
        players_pagination = Player.query.filter(
            Player.total_matches > 0
        ).order_by(
            Player.wins.desc()
        ).paginate(page=page, per_page=per_page, error_out=False)
        
        return render_template('players.html',
            players=players_pagination.items,
            pagination=players_pagination
        )
    except Exception as e:
        logger.error(f"Erro na página de jogadores: {e}", exc_info=True)
        return render_template('error.html', error=str(e)), 500


@app.route('/reports')
def reports():
    """Página de relatórios"""
    try:
        # Logs do scraper
        logs = ScraperLog.query.order_by(
            ScraperLog.timestamp.desc()
        ).limit(100).all()
        
        return render_template('reports.html', logs=logs)
    except Exception as e:
        logger.error(f"Erro na página de relatórios: {e}", exc_info=True)
        return render_template('error.html', error=str(e)), 500


# ==================== API ENDPOINTS ====================

@app.route('/api/matches/live')
def api_live_matches():
    """API: Retorna partidas ao vivo"""
    try:
        matches = Match.query.filter_by(status_id=2).order_by(Match.date.desc()).all()
        
        return jsonify([{
            'id': m.match_id,
            'location': m.location,
            'player1': m.player1_nickname,
            'player2': m.player2_nickname,
            'score': f"{m.player1_score} - {m.player2_score}",
            'team1': m.player1_team,
            'team2': m.player2_team,
            'stream_url': m.stream_url,
            'date': m.date.isoformat()
        } for m in matches])
    except Exception as e:
        logger.error(f"Erro API live matches: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/matches/today')
def api_today_matches():
    """API: Retorna partidas do dia"""
    try:
        today = datetime.utcnow().date()
        matches = Match.query.filter(
            db.func.date(Match.date) == today
        ).order_by(Match.date.desc()).all()
        
        return jsonify([{
            'id': m.match_id,
            'date': m.date.isoformat(),
            'location': m.location,
            'player1': m.player1_nickname,
            'player2': m.player2_nickname,
            'score': f"{m.player1_score} - {m.player2_score}",
            'status': 'live' if m.status_id == 2 else 'finished' if m.status_id == 3 else 'scheduled'
        } for m in matches])
    except Exception as e:
        logger.error(f"Erro API today matches: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/matches/recent')
def api_recent_matches():
    """API: Retorna partidas recentes"""
    try:
        limit = request.args.get('limit', 20, type=int)
        matches = Match.query.order_by(Match.date.desc()).limit(limit).all()
        
        return jsonify([{
            'id': m.match_id,
            'date': m.date.isoformat(),
            'location': m.location,
            'player1': m.player1_nickname,
            'player2': m.player2_nickname,
            'score': f"{m.player1_score} - {m.player2_score}",
            'team1': m.player1_team,
            'team2': m.player2_team,
            'status': m.status_id
        } for m in matches])
    except Exception as e:
        logger.error(f"Erro API recent matches: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/players/ranking')
def api_player_ranking():
    """API: Retorna ranking de jogadores"""
    try:
        min_matches = request.args.get('min_matches', 5, type=int)
        limit = request.args.get('limit', 50, type=int)
        
        players = Player.query.filter(
            Player.total_matches >= min_matches
        ).order_by(
            Player.wins.desc()
        ).limit(limit).all()
        
        return jsonify([{
            'rank': idx + 1,
            'nickname': p.nickname,
            'matches': p.total_matches,
            'wins': p.wins,
            'draws': p.draws,
            'losses': p.losses,
            'goals_for': p.goals_for,
            'goals_against': p.goals_against,
            'goal_diff': p.goal_difference,
            'win_rate': round(p.win_rate, 2)
        } for idx, p in enumerate(players)])
    except Exception as e:
        logger.error(f"Erro API player ranking: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/stats')
def api_stats():
    """API: Estatísticas gerais"""
    try:
        total_matches = Match.query.count()
        total_players = Player.query.count()
        live_matches = Match.query.filter_by(status_id=2).count()
        today_matches = Match.query.filter(
            db.func.date(Match.date) == datetime.utcnow().date()
        ).count()
        
        last_scan = ScraperLog.query.order_by(ScraperLog.timestamp.desc()).first()
        
        return jsonify({
            'total_matches': total_matches,
            'total_players': total_players,
            'live_matches': live_matches,
            'today_matches': today_matches,
            'last_scan': last_scan.timestamp.isoformat() if last_scan else None,
            'last_scan_status': last_scan.status if last_scan else None
        })
    except Exception as e:
        logger.error(f"Erro API stats: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/scraper/status')
def api_scraper_status():
    """API: Status do scraper"""
    try:
        last_log = ScraperLog.query.order_by(ScraperLog.timestamp.desc()).first()
        
        if not last_log:
            return jsonify({
                'status': 'unknown',
                'message': 'Nenhuma execução registrada'
            })
        
        # Verificar se está rodando recentemente (últimos 2 minutos)
        time_diff = datetime.utcnow() - last_log.timestamp
        is_active = time_diff.total_seconds() < 120
        
        return jsonify({
            'status': 'active' if is_active else 'idle',
            'last_run': last_log.timestamp.isoformat(),
            'last_status': last_log.status,
            'matches_found': last_log.matches_found,
            'message': last_log.message
        })
    except Exception as e:
        logger.error(f"Erro API scraper status: {e}")
        return jsonify({'error': str(e)}), 500


# ==================== FUNÇÕES AUXILIARES ====================

def cleanup_old_data():
    """Limpa dados antigos do banco"""
    with app.app_context():
        try:
            # Remover partidas com mais de 30 dias
            cutoff_date = datetime.utcnow() - timedelta(days=30)
            deleted = Match.query.filter(Match.date < cutoff_date).delete()
            
            # Remover logs com mais de 7 dias
            log_cutoff = datetime.utcnow() - timedelta(days=7)
            deleted_logs = ScraperLog.query.filter(ScraperLog.timestamp < log_cutoff).delete()
            
            db.session.commit()
            logger.info(f"🗑️  Limpeza: {deleted} partidas e {deleted_logs} logs removidos")
        except Exception as e:
            logger.error(f"Erro na limpeza: {e}")
            db.session.rollback()


def run_scraper_job():
    """Executa o scraper (chamado pelo scheduler)"""
    with app.app_context():
        try:
            from web_scraper.scraper_service import ScraperService
            # Passar os models como tupla
            models = (Match, Tournament, Player, ScraperLog)
            scraper = ScraperService(db, models)
            scraper.run()
        except Exception as e:
            logger.error(f"Erro ao executar scraper: {e}", exc_info=True)


# ==================== INICIALIZAÇÃO DO SCHEDULER ====================

def init_scheduler():
    """Inicializa o scheduler do APScheduler"""
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.interval import IntervalTrigger
    import atexit
    
    scheduler = BackgroundScheduler()
    
    # Intervalo de scraping (padrão: 60 segundos - aumentado para acomodar scan)
    scan_interval = int(os.environ.get('SCAN_INTERVAL', 60))
    run_scraper = os.environ.get('RUN_SCRAPER', 'true').lower() == 'true'
    
    if run_scraper:
        scheduler.add_job(
            func=run_scraper_job,  # Função wrapper com contexto
            trigger=IntervalTrigger(seconds=scan_interval),
            id='run_scraper',
            name='Scraper de partidas FIFA25',
            replace_existing=True
        )
        logger.info(f"✅ Scheduler configurado: scraping a cada {scan_interval}s")
    else:
        logger.info("⚠️  Scraper desabilitado (RUN_SCRAPER=false)")
    
    # Job de limpeza semanal (domingo às 3h UTC)
    scheduler.add_job(
        func=cleanup_old_data,
        trigger='cron',
        day_of_week='sun',
        hour=3,
        id='weekly_cleanup',
        name='Limpeza semanal',
        replace_existing=True
    )
    
    scheduler.start()
    logger.info("✅ Scheduler iniciado")
    
    # Shutdown ao fechar
    atexit.register(lambda: scheduler.shutdown())
    
    return scheduler


# ==================== INICIALIZAÇÃO DO APP ====================

# Criar tabelas e iniciar scheduler
with app.app_context():
    try:
        # Criar tabelas
        db.create_all()
        logger.info("✅ Banco de dados inicializado")
        
    except Exception as e:
        logger.error(f"❌ Erro na inicialização do banco: {e}", exc_info=True)

# Iniciar scheduler (fora do contexto)
try:
    scheduler = init_scheduler()
except Exception as e:
    logger.error(f"❌ Erro ao iniciar scheduler: {e}", exc_info=True)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)