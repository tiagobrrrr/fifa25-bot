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

# Definir modelos inline para evitar import circular
class Match(db.Model):
    """Modelo de Partida"""
    __tablename__ = 'matches'
    
    id = db.Column(db.Integer, primary_key=True)
    match_id = db.Column(db.Integer, unique=True, nullable=False, index=True)
    status_id = db.Column(db.Integer, default=1)
    date = db.Column(db.DateTime, index=True)
    tournament_id = db.Column(db.Integer, index=True)
    tournament_token = db.Column(db.String(200))
    location_code = db.Column(db.String(100))
    location_name = db.Column(db.String(200))
    location_color = db.Column(db.String(20))
    console_id = db.Column(db.Integer)
    console_token = db.Column(db.String(100))
    player1_id = db.Column(db.Integer, index=True)
    player1_nickname = db.Column(db.String(100))
    player1_photo = db.Column(db.String(500))
    player1_team_id = db.Column(db.Integer)
    player1_team_name = db.Column(db.String(200))
    player1_team_logo = db.Column(db.String(500))
    player2_id = db.Column(db.Integer, index=True)
    player2_nickname = db.Column(db.String(100))
    player2_photo = db.Column(db.String(500))
    player2_team_id = db.Column(db.Integer)
    player2_team_name = db.Column(db.String(200))
    player2_team_logo = db.Column(db.String(500))
    score1 = db.Column(db.Integer)
    score2 = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    
    def to_dict(self):
        return {
            'id': self.id,
            'match_id': self.match_id,
            'status_id': self.status_id,
            'date': self.date.isoformat() if self.date else None,
            'player1_nickname': self.player1_nickname,
            'player2_nickname': self.player2_nickname,
            'score1': self.score1,
            'score2': self.score2
        }

class Player(db.Model):
    """Modelo de Jogador"""
    __tablename__ = 'players'
    
    id = db.Column(db.Integer, primary_key=True)
    player_id = db.Column(db.Integer, unique=True, nullable=False, index=True)
    nickname = db.Column(db.String(100), nullable=False)
    photo = db.Column(db.String(500))
    total_matches = db.Column(db.Integer, default=0)
    wins = db.Column(db.Integer, default=0)
    losses = db.Column(db.Integer, default=0)
    draws = db.Column(db.Integer, default=0)
    goals_scored = db.Column(db.Integer, default=0)
    goals_conceded = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

class Tournament(db.Model):
    """Modelo de Torneio"""
    __tablename__ = 'tournaments'
    
    id = db.Column(db.Integer, primary_key=True)
    tournament_id = db.Column(db.Integer, unique=True, nullable=False, index=True)
    status_id = db.Column(db.Integer, default=1)
    token = db.Column(db.String(200))
    token_international = db.Column(db.String(200))
    marker = db.Column(db.String(10))
    total_matches = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

class Analysis(db.Model):
    """Modelo de Análise Diária"""
    __tablename__ = 'analyses'
    
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, index=True)
    total_matches = db.Column(db.Integer, default=0)
    live_matches = db.Column(db.Integer, default=0)
    finished_matches = db.Column(db.Integer, default=0)
    canceled_matches = db.Column(db.Integer, default=0)
    unique_players = db.Column(db.Integer, default=0)
    top_teams = db.Column(db.Text)
    top_locations = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

# Importar serviços
from web_scraper import FIFA25Scraper
from data_analyzer import DataAnalyzer

try:
    from email_service import EmailService
    email_enabled = True
except:
    email_enabled = False
    logger.warning("⚠️ Email service não disponível")

try:
    from report_generator import ReportGenerator
    report_enabled = True
except:
    report_enabled = False
    logger.warning("⚠️ Report generator não disponível")

try:
    from telegram_service import TelegramService
    telegram_enabled = True
except:
    telegram_enabled = False
    logger.warning("⚠️ Telegram service não disponível")

# Variáveis globais
scraper = FIFA25Scraper()
analyzer = DataAnalyzer()
email_service = EmailService() if email_enabled else None
report_generator = ReportGenerator() if report_enabled else None
telegram = TelegramService() if telegram_enabled else None

# Configurações do scheduler
SCAN_INTERVAL = int(os.environ.get('SCAN_INTERVAL', 30))
RUN_SCRAPER = os.environ.get('RUN_SCRAPER', 'true').lower() == 'true'

# Estatísticas globais
stats = {
    'last_scan': None,
    'total_scans': 0,
    'total_matches': 0,
    'errors': 0,
    'status': 'Iniciando...',
    'success_rate': 100.0,
    'uptime': 0,
    'matches_per_hour': 0,
    'live_matches': 0,
    'upcoming_matches': 0,
    'finished_matches': 0,
    'unique_players': 0,
    'active_tournaments': 0,
    'avg_goals_per_match': 0,
    'most_active_player': 'N/A',
    'most_used_team': 'N/A',
    'busiest_location': 'N/A'
}

# Tempo de início do bot
bot_start_time = datetime.now()


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
            
            # Calcular taxa de sucesso
            total_attempts = stats['total_scans']
            failures = stats['errors']
            if total_attempts > 0:
                stats['success_rate'] = round(((total_attempts - failures) / total_attempts) * 100, 1)
            else:
                stats['success_rate'] = 100.0
            
            # Calcular uptime (em horas)
            uptime_delta = datetime.now() - bot_start_time
            stats['uptime'] = round(uptime_delta.total_seconds() / 3600, 1)
            
            # Partidas por hora
            if stats['uptime'] > 0:
                stats['matches_per_hour'] = round(stats['total_matches'] / stats['uptime'], 1)
            
            # Estatísticas adicionais
            stats['live_matches'] = Match.query.filter_by(status_id=2).count()
            stats['upcoming_matches'] = Match.query.filter_by(status_id=1).count()
            stats['finished_matches'] = Match.query.filter_by(status_id=3).count()
            
            # Jogadores únicos
            unique_p1 = db.session.query(Match.player1_id).distinct().count()
            unique_p2 = db.session.query(Match.player2_id).distinct().count()
            stats['unique_players'] = unique_p1 + unique_p2
            
            # Torneios ativos
            stats['active_tournaments'] = db.session.query(Match.tournament_id).distinct().count()
            
            # Média de gols
            finished = Match.query.filter_by(status_id=3).filter(
                Match.score1.isnot(None),
                Match.score2.isnot(None)
            ).all()
            
            if finished:
                total_goals = sum([(m.score1 or 0) + (m.score2 or 0) for m in finished])
                stats['avg_goals_per_match'] = round(total_goals / len(finished), 2)
            
            # Jogador mais ativo
            top_player = db.session.query(
                Match.player1_nickname,
                db.func.count(Match.id).label('count')
            ).filter(
                Match.player1_nickname.isnot(None)
            ).group_by(
                Match.player1_nickname
            ).order_by(
                db.desc('count')
            ).first()
            
            if top_player:
                stats['most_active_player'] = top_player[0]
            
            # Time mais usado
            top_team = db.session.query(
                Match.player1_team_name,
                db.func.count(Match.id).label('count')
            ).filter(
                Match.player1_team_name.isnot(None)
            ).group_by(
                Match.player1_team_name
            ).order_by(
                db.desc('count')
            ).first()
            
            if top_team:
                stats['most_used_team'] = top_team[0]
            
            # Location mais ativa
            top_location = db.session.query(
                Match.location_name,
                db.func.count(Match.id).label('count')
            ).filter(
                Match.location_name.isnot(None)
            ).group_by(
                Match.location_name
            ).order_by(
                db.desc('count')
            ).first()
            
            if top_location:
                stats['busiest_location'] = top_location[0]
            
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


def send_weekly_report():
    """Envia relatório semanal por email"""
    if not email_enabled or not report_enabled:
        logger.warning("⚠️ Email ou Report Generator desabilitado")
        return
    
    with app.app_context():
        try:
            logger.info("📧 Gerando relatório semanal...")
            
            # Buscar partidas dos últimos 7 dias
            seven_days_ago = datetime.now() - timedelta(days=7)
            matches = Match.query.filter(
                Match.date >= seven_days_ago
            ).all()
            
            if not matches:
                logger.warning("⚠️ Nenhuma partida nos últimos 7 dias")
                return
            
            # Converter para lista de dicionários
            matches_data = [match.to_dict() for match in matches]
            
            # Gerar planilha Excel
            excel_path = report_generator.generate_weekly_report(matches_data)
            
            if not excel_path:
                logger.error("❌ Erro ao gerar planilha")
                return
            
            # Preparar dados do email
            total_matches = len(matches)
            finished = len([m for m in matches if m.status_id == 3])
            
            # Jogadores únicos
            players = set()
            for match in matches:
                if match.player1_nickname:
                    players.add(match.player1_nickname)
                if match.player2_nickname:
                    players.add(match.player2_nickname)
            
            report_data = {
                'total_matches': total_matches,
                'finished_matches': finished,
                'unique_players': len(players)
            }
            
            # Enviar email
            recipient_email = os.environ.get('RECIPIENT_EMAIL', os.environ.get('EMAIL_USER'))
            
            success = email_service.send_daily_report(
                to_address=recipient_email,
                report_data=report_data,
                attachment_path=excel_path
            )
            
            if success:
                logger.info(f"✅ Relatório semanal enviado para {recipient_email}")
            else:
                logger.error("❌ Falha ao enviar relatório semanal")
            
            # Limpar relatórios antigos
            report_generator.cleanup_old_reports(days=14)
            
        except Exception as e:
            logger.error(f"❌ Erro ao enviar relatório semanal: {e}")
            
            if email_service:
                try:
                    recipient_email = os.environ.get('RECIPIENT_EMAIL', os.environ.get('EMAIL_USER'))
                    email_service.send_error_notification(
                        to_address=recipient_email,
                        error_message=f"Erro ao gerar relatório semanal: {e}"
                    )
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
    try:
        # Buscar estatísticas gerais
        total_matches = Match.query.count()
        live_matches = Match.query.filter_by(status_id=2).count()
        upcoming_matches = Match.query.filter_by(status_id=1).count()
        finished_matches = Match.query.filter_by(status_id=3).count()
        
        # Buscar partidas recentes
        recent_matches = Match.query.order_by(Match.updated_at.desc()).limit(10).all()
        
        # Buscar partidas ao vivo
        live_matches_list = Match.query.filter_by(status_id=2).order_by(Match.date.desc()).limit(10).all()
        
        # Buscar próximas partidas
        upcoming_matches_list = Match.query.filter_by(status_id=1).order_by(Match.date.asc()).limit(10).all()
        
        # Preparar dados do summary
        summary = {
            'total_matches': total_matches,
            'live_matches_count': live_matches,
            'upcoming_matches_count': upcoming_matches,
            'finished_matches_count': finished_matches,
            'nearest_matches_count': upcoming_matches,
            'recent_matches': [m.to_dict() for m in recent_matches],
            'live_matches': [m.to_dict() for m in live_matches_list],
            'upcoming_matches': [m.to_dict() for m in upcoming_matches_list]
        }
        
        return render_template('dashboard.html', stats=stats, summary=summary)
    except Exception as e:
        logger.error(f"Erro ao carregar dashboard: {e}")
        # Retornar página com dados vazios em caso de erro
        summary = {
            'total_matches': 0,
            'live_matches_count': 0,
            'upcoming_matches_count': 0,
            'finished_matches_count': 0,
            'nearest_matches_count': 0,
            'recent_matches': [],
            'live_matches': [],
            'upcoming_matches': []
        }
        return render_template('dashboard.html', stats=stats, summary=summary)


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


@app.route('/api/send-report')
def api_send_report():
    """Força envio de relatório semanal (para testes)"""
    try:
        send_weekly_report()
        return jsonify({'success': True, 'message': 'Relatório enviado'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== SCHEDULER ====================

def setup_scheduler():
    """Configura o scheduler para executar o scraper periodicamente"""
    scheduler = BackgroundScheduler()
    
    # Job 1: Scraper (a cada X segundos)
    scheduler.add_job(
        func=run_scraper,
        trigger=IntervalTrigger(seconds=SCAN_INTERVAL),
        id='scraper_job',
        name='Scraper FIFA25 ESportsBattle',
        replace_existing=True
    )
    logger.info(f"✅ Scheduler configurado: scraper a cada {SCAN_INTERVAL}s")
    
    # Job 2: Relatório Semanal (toda segunda-feira às 09:00)
    if email_enabled and report_enabled:
        from apscheduler.triggers.cron import CronTrigger
        
        scheduler.add_job(
            func=send_weekly_report,
            trigger=CronTrigger(day_of_week='mon', hour=9, minute=0),
            id='weekly_report_job',
            name='Relatório Semanal FIFA25',
            replace_existing=True
        )
        logger.info("✅ Scheduler configurado: relatório semanal toda segunda às 09:00")
    else:
        logger.warning("⚠️ Relatório semanal desabilitado (email ou report generator não disponível)")
    
    scheduler.start()
    
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