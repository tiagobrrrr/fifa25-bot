# app.py - ARQUIVO COMPLETO CORRIGIDO
"""
Bot FIFA25 - Aplicação Flask Principal
Inclui prevenção de duplicatas e detecção automática de resultados
"""

from flask import Flask, render_template, jsonify, request, send_file
from flask_sqlalchemy import SQLAlchemy
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
import os
import logging

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

# Corrige URL do PostgreSQL se necessário
if app.config['SQLALCHEMY_DATABASE_URI'].startswith('postgres://'):
    app.config['SQLALCHEMY_DATABASE_URI'] = app.config['SQLALCHEMY_DATABASE_URI'].replace('postgres://', 'postgresql://', 1)

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,
    'pool_recycle': 300,
}

# Inicialização do banco de dados
from models import db, Match, get_or_create_match, get_match_statistics
db.init_app(app)

# Importações dos módulos
from web_scraper import FIFA25Scraper
from excel_exporter import ExcelExporter
from statistics_calculator import StatisticsCalculator

# Inicializar componentes
scraper = FIFA25Scraper()
excel_exporter = ExcelExporter()
stats_calculator = StatisticsCalculator()

# Configurações
SCAN_INTERVAL = int(os.environ.get('SCAN_INTERVAL', 30))  # segundos
RUN_SCRAPER = os.environ.get('RUN_SCRAPER', 'true').lower() == 'true'


# ============================================================
# FUNÇÕES DE SCRAPING COM PREVENÇÃO DE DUPLICATAS
# ============================================================

def scrape_matches():
    """
    Função principal de scraping com verificação de duplicatas
    """
    try:
        logger.info("🔄 Iniciando varredura...")
        
        # Coleta partidas próximas
        upcoming_matches = scraper.get_upcoming_matches()
        logger.info(f"📊 Encontradas {len(upcoming_matches)} partidas próximas")
        
        # Processa partidas próximas (evitando duplicatas)
        new_upcoming = process_matches(upcoming_matches, 'scheduled')
        
        # Coleta partidas ao vivo
        live_matches = scraper.get_live_matches()
        logger.info(f"📺 Encontradas {len(live_matches)} partidas em streaming")
        
        # Processa partidas ao vivo (evitando duplicatas)
        new_live = process_matches(live_matches, 'live')
        
        total_new = new_upcoming + new_live
        logger.info(f"✅ Varredura completa: {total_new} partidas NOVAS salvas")
        
    except Exception as e:
        logger.error(f"❌ Erro na varredura: {e}")


def process_matches(matches, default_status='scheduled'):
    """
    Processa lista de partidas evitando duplicatas
    
    Args:
        matches: lista de dicts com dados das partidas
        default_status: status padrão se não especificado
        
    Returns:
        int: número de partidas novas adicionadas
    """
    new_count = 0
    updated_count = 0
    
    for match_data in matches:
        try:
            match_id = match_data.get('match_id')
            
            if not match_id:
                logger.warning("⚠️ Partida sem match_id, ignorando")
                continue
            
            # Verifica se partida já existe no banco
            existing_match = Match.query.filter_by(match_id=match_id).first()
            
            if existing_match:
                # Partida já existe - apenas atualiza se necessário
                updated = update_existing_match(existing_match, match_data)
                if updated:
                    updated_count += 1
            else:
                # Partida nova - cria no banco
                create_new_match(match_data, default_status)
                new_count += 1
                logger.info(f"✨ Nova partida adicionada: {match_id}")
        
        except Exception as e:
            logger.error(f"Erro ao processar partida: {e}")
            continue
    
    if updated_count > 0:
        logger.info(f"🔄 {updated_count} partidas existentes atualizadas")
    
    return new_count


def update_existing_match(match, new_data):
    """
    Atualiza partida existente apenas se houver mudanças relevantes
    
    Args:
        match: objeto Match do banco
        new_data: dict com novos dados
        
    Returns:
        bool: True se houve atualização
    """
    updated = False
    
    try:
        # Atualiza status se mudou
        new_status = new_data.get('status')
        if new_status and new_status != match.status:
            # Não regredir de finished para live/scheduled
            if match.status != 'finished':
                match.status = new_status
                updated = True
                logger.info(f"📝 Status atualizado: {match.match_id} → {new_status}")
        
        # Atualiza placar durante partida ao vivo
        if match.status == 'live':
            home_score = new_data.get('current_score_home')
            away_score = new_data.get('current_score_away')
            
            if home_score is not None and away_score is not None:
                if (match.current_score_home != home_score or 
                    match.current_score_away != away_score):
                    match.current_score_home = home_score
                    match.current_score_away = away_score
                    updated = True
        
        # Atualiza stream_url se mudou
        new_stream = new_data.get('stream_url')
        if new_stream and new_stream != match.stream_url:
            match.stream_url = new_stream
            updated = True
        
        # Atualiza campos vazios
        if not match.home_player and new_data.get('home_player'):
            match.home_player = new_data['home_player']
            updated = True
        
        if not match.away_player and new_data.get('away_player'):
            match.away_player = new_data['away_player']
            updated = True
        
        if not match.location and new_data.get('location'):
            match.location = new_data['location']
            updated = True
        
        if not match.tournament and new_data.get('tournament'):
            match.tournament = new_data['tournament']
            updated = True
        
        if updated:
            match.updated_at = datetime.utcnow()
            db.session.commit()
    
    except Exception as e:
        logger.error(f"Erro ao atualizar partida {match.match_id}: {e}")
        db.session.rollback()
    
    return updated


def create_new_match(match_data, default_status='scheduled'):
    """
    Cria nova partida no banco de dados
    
    Args:
        match_data: dict com dados da partida
        default_status: status padrão
    """
    try:
        match = Match(
            match_id=match_data.get('match_id'),
            home_player=match_data.get('home_player'),
            away_player=match_data.get('away_player'),
            home_team=match_data.get('home_team'),
            away_team=match_data.get('away_team'),
            tournament=match_data.get('tournament'),
            location=match_data.get('location'),
            match_date=match_data.get('match_date'),
            status=match_data.get('status', default_status),
            stream_url=match_data.get('stream_url'),
            url=match_data.get('url'),
            current_score_home=match_data.get('current_score_home', 0),
            current_score_away=match_data.get('current_score_away', 0)
        )
        
        db.session.add(match)
        db.session.commit()
        
    except Exception as e:
        logger.error(f"Erro ao criar partida: {e}")
        db.session.rollback()
        raise


# ============================================================
# VERIFICAÇÃO DE PARTIDAS FINALIZADAS
# ============================================================

def check_finished_matches():
    """
    Verifica partidas ao vivo que finalizaram
    """
    try:
        # Busca partidas com status 'live'
        live_matches = Match.query.filter_by(status='live').all()
        
        if not live_matches:
            logger.info("ℹ️ Nenhuma partida ao vivo para verificar")
            return
        
        logger.info(f"🔍 Verificando {len(live_matches)} partidas ao vivo...")
        
        finished_count = 0
        
        for match in live_matches:
            try:
                # Verifica status atual da partida
                result = scraper.check_match_status_and_score(match.url)
                
                if not result:
                    continue
                
                # Se partida finalizou
                if result['status'] == 'finished':
                    logger.info(f"🏁 Partida {match.match_id} FINALIZADA: "
                              f"{result['home_score']} x {result['away_score']}")
                    
                    # Atualiza dados no banco
                    match.status = 'finished'
                    match.final_score_home = result['home_score']
                    match.final_score_away = result['away_score']
                    match.winner = result['winner']
                    match.finished_at = result['finished_at']
                    
                    db.session.commit()
                    
                    # Processa resultado
                    process_finished_match(match)
                    
                    finished_count += 1
                
                # Se ainda está ao vivo, atualiza placar atual
                elif result['status'] == 'live':
                    if (match.current_score_home != result['home_score'] or
                        match.current_score_away != result['away_score']):
                        match.current_score_home = result['home_score']
                        match.current_score_away = result['away_score']
                        db.session.commit()
            
            except Exception as e:
                logger.error(f"Erro ao verificar match {match.match_id}: {e}")
                continue
        
        if finished_count > 0:
            logger.info(f"✅ {finished_count} partidas finalizadas nesta verificação")
    
    except Exception as e:
        logger.error(f"Erro no check_finished_matches: {e}")


def process_finished_match(match):
    """
    Processa uma partida que acabou de finalizar
    """
    try:
        logger.info(f"📊 Processando partida finalizada {match.match_id}...")
        
        # Exporta para Excel
        success = excel_exporter.export_match(match)
        if success:
            logger.info(f"✅ Partida exportada para Excel")
        
        # Atualiza cache de estatísticas
        stats_calculator.refresh_cache()
        logger.info(f"✅ Estatísticas atualizadas")
        
        # Envia notificação (se configurado)
        try:
            notify_match_finished(match)
        except Exception as e:
            logger.warning(f"⚠️ Erro ao enviar notificação: {e}")
        
        logger.info(f"✅ Processamento da partida {match.match_id} concluído")
        
    except Exception as e:
        logger.error(f"Erro ao processar partida {match.match_id}: {e}")


def notify_match_finished(match):
    """
    Envia notificação quando partida finaliza
    """
    try:
        from telegram_service import send_message
        
        message = f"""
🏁 **PARTIDA FINALIZADA**

🎮 **Match #{match.match_id}**

⚽ **{match.home_player}** {match.final_score_home} x {match.final_score_away} **{match.away_player}**

🏆 **Vencedor:** {match.winner}

📍 **Local:** {match.location}
🎯 **Torneio:** {match.tournament}
"""
        
        send_message(message)
        logger.info("📱 Notificação Telegram enviada")
        
    except ImportError:
        # Telegram não configurado
        pass
    except Exception as e:
        logger.error(f"Erro ao enviar notificação: {e}")


# ============================================================
# LIMPEZA DE PARTIDAS ANTIGAS
# ============================================================

def cleanup_old_matches():
    """
    Remove partidas muito antigas do banco (opcional)
    Mantém apenas partidas dos últimos 30 dias
    """
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=30)
        
        old_matches = Match.query.filter(
            Match.status == 'scheduled',
            Match.created_at < cutoff_date
        ).all()
        
        if old_matches:
            for match in old_matches:
                db.session.delete(match)
            
            db.session.commit()
            logger.info(f"🗑️ {len(old_matches)} partidas antigas removidas")
    
    except Exception as e:
        logger.error(f"Erro ao limpar partidas antigas: {e}")
        db.session.rollback()


# ============================================================
# SCHEDULER
# ============================================================

scheduler = BackgroundScheduler()

if RUN_SCRAPER:
    # Job 1: Scraper principal (a cada 30 segundos)
    scheduler.add_job(
        func=scrape_matches,
        trigger="interval",
        seconds=SCAN_INTERVAL,
        id="scraper_fifa25",
        name="Scraper FIFA25 ESportsBattle",
        replace_existing=True
    )
    
    # Job 2: Verificar partidas finalizadas (a cada 2 minutos)
    scheduler.add_job(
        func=check_finished_matches,
        trigger="interval",
        minutes=2,
        id="check_finished_matches",
        name="Verificar Partidas Finalizadas",
        replace_existing=True
    )
    
    # Job 3: Exportar para Excel (a cada 5 minutos)
    scheduler.add_job(
        func=lambda: excel_exporter.export_all_finished_matches(),
        trigger="interval",
        minutes=5,
        id="export_to_excel",
        name="Exportar Partidas para Excel",
        replace_existing=True
    )
    
    # Job 4: Atualizar estatísticas (a cada 5 minutos)
    scheduler.add_job(
        func=lambda: stats_calculator.refresh_cache(),
        trigger="interval",
        minutes=5,
        id="update_statistics",
        name="Atualizar Cache de Estatísticas",
        replace_existing=True
    )
    
    # Job 5: Limpeza de partidas antigas (1x por dia às 3h)
    scheduler.add_job(
        func=cleanup_old_matches,
        trigger="cron",
        hour=3,
        minute=0,
        id="cleanup_old_matches",
        name="Limpar Partidas Antigas",
        replace_existing=True
    )

scheduler.start()


# ============================================================
# ROTAS - PÁGINAS
# ============================================================

@app.route('/')
def index():
    """Dashboard principal"""
    try:
        stats = get_match_statistics()
        
        # Partidas ao vivo (limitado a 5 para o dashboard)
        live_matches = Match.query.filter_by(status='live')\
                                  .order_by(Match.created_at.desc())\
                                  .limit(5).all()
        
        # Próximas partidas (limitado a 5)
        upcoming_matches = Match.query.filter_by(status='scheduled')\
                                      .order_by(Match.match_date)\
                                      .limit(5).all()
        
        return render_template(
            'dashboard.html',
            stats=stats,
            live_matches=live_matches,
            upcoming_matches=upcoming_matches
        )
    
    except Exception as e:
        logger.error(f"Erro na página inicial: {e}")
        return render_template('dashboard.html', stats={}, live_matches=[], upcoming_matches=[])


@app.route('/matches')
def matches():
    """Página de partidas ao vivo"""
    try:
        status_filter = request.args.get('status', 'live')
        
        query = Match.query.filter_by(status=status_filter)\
                          .order_by(Match.created_at.desc())
        
        matches_list = query.all()
        
        return render_template(
            'matches.html',
            matches=matches_list,
            status=status_filter
        )
    
    except Exception as e:
        logger.error(f"Erro na página de partidas: {e}")
        return render_template('matches.html', matches=[], status='live')


@app.route('/upcoming')
def upcoming():
    """Página de partidas agendadas"""
    try:
        upcoming_matches = Match.query.filter_by(status='scheduled')\
                                      .order_by(Match.match_date)\
                                      .all()
        
        return render_template('upcoming.html', matches=upcoming_matches)
    
    except Exception as e:
        logger.error(f"Erro na página de próximas: {e}")
        return render_template('upcoming.html', matches=[])


@app.route('/statistics')
def statistics():
    """Página de estatísticas dos jogadores"""
    try:
        # Obtém estatísticas por estádio (do cache)
        stats_by_stadium = stats_calculator.get_statistics_by_stadium()
        
        # Conta partidas finalizadas
        finished_count = Match.query.filter_by(status='finished').count()
        
        # Top scorers e winners
        top_scorers = stats_calculator.get_top_scorers(limit=5)
        top_winners = stats_calculator.get_top_winners(limit=5)
        
        return render_template(
            'statistics.html',
            stats_by_stadium=stats_by_stadium,
            finished_count=finished_count,
            top_scorers=top_scorers,
            top_winners=top_winners,
            last_update=stats_calculator.cache_timestamp
        )
    
    except Exception as e:
        logger.error(f"Erro na página de estatísticas: {e}")
        return render_template('statistics.html', stats_by_stadium={}, error=str(e))


@app.route('/players')
def players():
    """Página com todos os jogadores de todos os estádios"""
    try:
        from sqlalchemy import or_
        
        # Busca TODOS os jogadores únicos
        home_players = Match.query.with_entities(Match.home_player, Match.location)\
                                   .filter(Match.home_player.isnot(None))\
                                   .distinct().all()
        
        away_players = Match.query.with_entities(Match.away_player, Match.location)\
                                   .filter(Match.away_player.isnot(None))\
                                   .distinct().all()
        
        # Organiza por estádio
        players_by_stadium = {}
        
        for player, stadium in home_players + away_players:
            if stadium not in players_by_stadium:
                players_by_stadium[stadium] = set()
            players_by_stadium[stadium].add(player)
        
        # Converte para listas ordenadas
        for stadium in players_by_stadium:
            players_by_stadium[stadium] = sorted(list(players_by_stadium[stadium]))
        
        # Obtém estatísticas
        all_stats = stats_calculator.get_cached_statistics()
        player_stats = all_stats.get('all_players', {})
        
        return render_template(
            'players.html',
            players_by_stadium=players_by_stadium,
            player_stats=player_stats,
            total_players=sum(len(p) for p in players_by_stadium.values())
        )
    
    except Exception as e:
        logger.error(f"Erro na página de jogadores: {e}")
        return render_template('players.html', players_by_stadium={}, error=str(e))


@app.route('/reports')
def reports():
    """Página de relatórios"""
    return render_template('reports.html')


# ============================================================
# ROTAS - API
# ============================================================

@app.route('/api/stats')
def api_stats():
    """API: Estatísticas gerais"""
    stats = get_match_statistics()
    return jsonify(stats)


@app.route('/api/matches/count')
def api_matches_count():
    """API: Contagem de partidas por data"""
    date_str = request.args.get('date')
    
    if date_str:
        try:
            date = datetime.strptime(date_str, '%Y-%m-%d').date()
            count = Match.query.filter(
                db.func.date(Match.match_date) == date
            ).count()
        except:
            count = 0
    else:
        count = Match.query.count()
    
    return jsonify({'count': count, 'date': date_str})


@app.route('/api/statistics/all')
def api_all_statistics():
    """API: Todas as estatísticas"""
    try:
        stats = stats_calculator.get_cached_statistics()
        return jsonify({
            'success': True,
            'data': stats,
            'timestamp': stats_calculator.cache_timestamp.isoformat() if stats_calculator.cache_timestamp else None
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/statistics/player/<player_name>')
def api_player_statistics(player_name):
    """API: Estatísticas de um jogador"""
    try:
        stats = stats_calculator.calculate_player_statistics(player_name=player_name)
        return jsonify({
            'success': True,
            'player': player_name,
            'stats': stats.get(player_name, {})
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/statistics/top-scorers')
def api_top_scorers():
    """API: Top artilheiros"""
    limit = request.args.get('limit', 10, type=int)
    stadium = request.args.get('stadium')
    
    try:
        scorers = stats_calculator.get_top_scorers(limit=limit, stadium=stadium)
        return jsonify({'success': True, 'scorers': scorers})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/statistics/top-winners')
def api_top_winners():
    """API: Top vencedores"""
    limit = request.args.get('limit', 10, type=int)
    stadium = request.args.get('stadium')
    
    try:
        winners = stats_calculator.get_top_winners(limit=limit, stadium=stadium)
        return jsonify({'success': True, 'winners': winners})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/download/excel')
def download_excel():
    """Download da planilha Excel"""
    try:
        excel_path = excel_exporter.excel_path
        
        if os.path.exists(excel_path):
            return send_file(
                excel_path,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                as_attachment=True,
                download_name=f'FIFA25_Partidas_{datetime.now().strftime("%Y%m%d_%H%M")}.xlsx'
            )
        else:
            return jsonify({'error': 'Arquivo não encontrado'}), 404
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/admin/force-update')
def force_update():
    """Força atualização completa (debug)"""
    try:
        # Verifica partidas finalizadas
        check_finished_matches()
        
        # Exporta pendentes
        excel_exporter.export_all_finished_matches()
        
        # Atualiza estatísticas
        stats_calculator.refresh_cache()
        
        return jsonify({
            'success': True,
            'message': 'Atualização forçada concluída',
            'timestamp': datetime.now().isoformat()
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================
# INICIALIZAÇÃO
# ============================================================

# Cria tabelas se não existirem
with app.app_context():
    db.create_all()
    logger.info("✅ Banco de dados inicializado")

# Carrega cache inicial de estatísticas
try:
    with app.app_context():
        stats_calculator.refresh_cache()
        logger.info("✅ Cache inicial de estatísticas carregado")
except Exception as e:
    logger.error(f"⚠️ Erro ao carregar cache inicial: {e}")

# Log de jobs agendados
logger.info("\n" + "="*60)
logger.info("📅 JOBS AGENDADOS:")
logger.info(f"   - Scraper FIFA25: a cada {SCAN_INTERVAL}s")
logger.info("   - Verificar Finalizadas: a cada 2 min")
logger.info("   - Exportar Excel: a cada 5 min")
logger.info("   - Atualizar Estatísticas: a cada 5 min")
logger.info("   - Limpar Antigas: 1x/dia às 3h")
logger.info("="*60 + "\n")


# ============================================================
# EXECUÇÃO
# ============================================================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
