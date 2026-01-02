from flask import Flask, render_template, jsonify, request
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
import logging
import os
from sqlalchemy import func, and_, desc

# ✅ IMPORT CORRIGIDO
from web_scraper import FIFA25Scraper

from models import Match, Player, init_db, get_session
from data_analyzer import DataAnalyzer

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('app')

# Inicializar Flask
app = Flask(__name__)
app.secret_key = os.getenv('SESSION_SECRET', 'fifa25-secret-key-change-me')

# Variáveis globais
last_scrape_time = None
scrape_count = 0
scraper_enabled = os.getenv('RUN_SCRAPER', 'true').lower() == 'true'

# Inicializar banco de dados
init_db()

# Inicializar scraper
scraper = FIFA25Scraper()
analyzer = DataAnalyzer()


def scrape_job():
    """Job de coleta de dados executado periodicamente"""
    global last_scrape_time, scrape_count
    
    scrape_count += 1
    logger.info("=" * 70)
    logger.info(f"🔄 COLETA #{scrape_count}")
    logger.info(f"🕐 {datetime.now()}")
    logger.info("=" * 70)
    
    try:
        # Coletar partidas ao vivo
        live_matches = scraper.get_live_matches()
        recent_matches = scraper.get_recent_matches()
        
        all_matches = live_matches + recent_matches
        
        if not all_matches:
            logger.info("⚠️  Nenhuma partida encontrada")
            return
        
        # Salvar no banco de dados
        session = get_session()
        new_matches = 0
        
        for match_data in all_matches:
            try:
                # Verificar se a partida já existe
                existing = session.query(Match).filter(
                    and_(
                        Match.team1 == match_data.get('team1'),
                        Match.team2 == match_data.get('team2'),
                        Match.player1 == match_data.get('player1'),
                        Match.player2 == match_data.get('player2'),
                        Match.match_time == match_data.get('match_time')
                    )
                ).first()
                
                if not existing:
                    match = Match(
                        team1=match_data.get('team1'),
                        team2=match_data.get('team2'),
                        player1=match_data.get('player1'),
                        player2=match_data.get('player2'),
                        score=match_data.get('score', '0-0'),  # ✅ CORRIGIDO
                        tournament=match_data.get('tournament'),
                        match_time=match_data.get('match_time'),
                        location=match_data.get('location'),
                        status=match_data.get('status', 'unknown')
                    )
                    session.add(match)
                    new_matches += 1
                    
                    # Atualizar estatísticas dos jogadores
                    update_player_stats(session, match_data)
            
            except Exception as e:
                logger.error(f"❌ Erro ao salvar partida: {e}")
                continue
        
        session.commit()
        session.close()
        
        last_scrape_time = datetime.now()
        logger.info(f"✅ Coleta finalizada: {new_matches} novas partidas")
        
    except Exception as e:
        logger.error(f"❌ Erro na coleta: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()


def update_player_stats(session, match_data):
    """Atualiza estatísticas dos jogadores"""
    try:
        player1_name = match_data.get('player1')
        player2_name = match_data.get('player2')
        score = match_data.get('score', '0-0')
        
        if not player1_name or not player2_name or not score:
            return
        
        # Parsear placar
        try:
            score1, score2 = map(int, score.split('-'))
        except:
            return
        
        # Atualizar Player 1
        player1 = session.query(Player).filter_by(name=player1_name).first()
        if not player1:
            player1 = Player(name=player1_name)
            session.add(player1)
        
        player1.total_matches += 1
        player1.goals_scored += score1
        player1.goals_conceded += score2
        
        if score1 > score2:
            player1.wins += 1
        elif score1 < score2:
            player1.losses += 1
        else:
            player1.draws += 1
        
        player1.last_updated = datetime.utcnow()
        
        # Atualizar Player 2
        player2 = session.query(Player).filter_by(name=player2_name).first()
        if not player2:
            player2 = Player(name=player2_name)
            session.add(player2)
        
        player2.total_matches += 1
        player2.goals_scored += score2
        player2.goals_conceded += score1
        
        if score2 > score1:
            player2.wins += 1
        elif score2 < score1:
            player2.losses += 1
        else:
            player2.draws += 1
        
        player2.last_updated = datetime.utcnow()
        
    except Exception as e:
        logger.error(f"Erro ao atualizar estatísticas: {e}")


# Rotas da aplicação
@app.route('/')
def dashboard():
    """Dashboard principal"""
    try:
        session = get_session()
        
        # Estatísticas gerais
        total_matches = session.query(func.count(Match.id)).scalar() or 0
        total_players = session.query(func.count(Player.id)).scalar() or 0
        
        # Partidas recentes
        recent_matches = session.query(Match).order_by(
            desc(Match.created_at)
        ).limit(10).all()
        
        # Top jogadores
        top_players = session.query(Player).order_by(
            desc(Player.wins)
        ).limit(5).all()
        
        session.close()
        
        return render_template('dashboard.html',
                             total_matches=total_matches,
                             total_players=total_players,
                             recent_matches=recent_matches,
                             top_players=top_players,
                             last_scrape=last_scrape_time,
                             scrape_count=scrape_count,
                             scraper_enabled=scraper_enabled)
    
    except Exception as e:
        logger.error(f"Erro no dashboard: {e}")
        return f"Erro ao carregar dashboard: {e}", 500


@app.route('/api/matches')
def api_matches():
    """API para listar partidas"""
    try:
        session = get_session()
        limit = request.args.get('limit', 50, type=int)
        
        matches = session.query(Match).order_by(
            desc(Match.created_at)
        ).limit(limit).all()
        
        result = [m.to_dict() for m in matches]
        session.close()
        
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"Erro na API de partidas: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/players')
def api_players():
    """API para listar jogadores"""
    try:
        session = get_session()
        
        players = session.query(Player).order_by(
            desc(Player.total_matches)
        ).all()
        
        result = [p.to_dict() for p in players]
        session.close()
        
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"Erro na API de jogadores: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/stats')
def api_stats():
    """API para estatísticas gerais"""
    try:
        session = get_session()
        
        stats = {
            'total_matches': session.query(func.count(Match.id)).scalar() or 0,
            'total_players': session.query(func.count(Player.id)).scalar() or 0,
            'last_scrape': last_scrape_time.isoformat() if last_scrape_time else None,
            'scrape_count': scrape_count,
            'scraper_enabled': scraper_enabled
        }
        
        session.close()
        return jsonify(stats)
    
    except Exception as e:
        logger.error(f"Erro na API de stats: {e}")
        return jsonify({'error': str(e)}), 500


# Inicializar scheduler
if scraper_enabled:
    scheduler = BackgroundScheduler()
    interval = int(os.getenv('SCAN_INTERVAL', 30))
    scheduler.add_job(
        func=scrape_job,
        trigger="interval",
        seconds=interval,
        id='scrape_job',
        name='Coletar partidas FIFA25',
        replace_existing=True
    )
    scheduler.start()
    logger.info(f"✅ Scheduler iniciado - Intervalo: {interval}s")
else:
    logger.info("⚠️  Scraper desabilitado via variável RUN_SCRAPER")


if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)