from flask import Flask, render_template, jsonify, request
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
import os
import logging
import requests
import pytz
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Timezone de São Paulo
SP_TZ = pytz.timezone('America/Sao_Paulo')

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SESSION_SECRET', 'dev-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///fifa25.db')

if app.config['SQLALCHEMY_DATABASE_URI'].startswith('postgres://'):
    app.config['SQLALCHEMY_DATABASE_URI'] = app.config['SQLALCHEMY_DATABASE_URI'].replace('postgres://', 'postgresql://')

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,
    'pool_recycle': 300,
}

from models import db, Match, Player
db.init_app(app)

# Filtro de template para converter UTC -> São Paulo
@app.template_filter('sp_time')
def sp_time_filter(dt):
    """Converte datetime UTC para horário de São Paulo"""
    if dt is None:
        return 'N/A'
    if dt.tzinfo is None:
        dt = pytz.utc.localize(dt)
    return dt.astimezone(SP_TZ).strftime('%d/%m/%Y %H:%M')

@app.template_filter('sp_time_short')
def sp_time_short_filter(dt):
    """Converte datetime UTC para horário de São Paulo (formato curto)"""
    if dt is None:
        return 'N/A'
    if dt.tzinfo is None:
        dt = pytz.utc.localize(dt)
    return dt.astimezone(SP_TZ).strftime('%d/%m %H:%M')

last_scan_time = None
scraper_status = "Aguardando primeira execução"
scheduler = None


# ============================================
# SCRAPER CORRIGIDO COM ENDPOINTS REAIS
# ============================================

class FIFA25Scraper:
    """Scraper FIFA25 com endpoints corretos"""
    
    def __init__(self):
        self.base_url = "https://football.esportsbattle.com"
        self.headers = {
            'accept': '*/*',
            'accept-language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
            'content-type': 'application/json',
            'referer': 'https://football.esportsbattle.com/en/',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36'
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        
        # IDs de torneios e locations conhecidos
        self.tournament_ids = [233188, 233189, 233190]  # Adicione mais IDs conforme descobrir
        self.location_ids = [1, 2, 3]  # Adicione mais IDs
    
    def get_live_matches(self):
        """Coleta partidas ao vivo via streaming endpoint"""
        all_matches = []
        
        try:
            logger.info("🔴 Coletando partidas AO VIVO...")
            
            # Endpoint 1: Streaming geral (NOVO!)
            try:
                url = f"{self.base_url}/api/locations/streaming"
                response = self.session.get(url, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    matches = self._parse_streaming_data(data, 'all')
                    all_matches.extend(matches)
                    logger.info(f"   ✓ Streaming geral: {len(matches)} partidas")
            except Exception as e:
                logger.debug(f"   × Streaming geral: {e}")
            
            # Endpoint 2: Locations específicas
            for location_id in self.location_ids:
                try:
                    url = f"{self.base_url}/api/locations/{location_id}/streaming"
                    response = self.session.get(url, timeout=10)
                    
                    if response.status_code == 200:
                        data = response.json()
                        matches = self._parse_streaming_data(data, location_id)
                        all_matches.extend(matches)
                        logger.info(f"   ✓ Location {location_id}: {len(matches)} partidas")
                except Exception as e:
                    logger.debug(f"   × Location {location_id}: {e}")
                    continue
            
            logger.info(f"✅ Total ao vivo: {len(all_matches)}")
            return all_matches
            
        except Exception as e:
            logger.error(f"❌ Erro live: {e}")
            return []
    
    def get_recent_matches(self):
        """Coleta partidas recentes via múltiplos endpoints"""
        all_matches = []
        
        try:
            logger.info("📋 Coletando partidas recentes...")
            
            # Endpoint 1: nearest-matches (NOVO!)
            try:
                url = f"{self.base_url}/api/tournaments/nearest-matches"
                response = self.session.get(url, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    matches = self._parse_nearest_matches(data)
                    all_matches.extend(matches)
                    logger.info(f"   ✓ Nearest-matches: {len(matches)} partidas")
            except Exception as e:
                logger.debug(f"   × Nearest-matches: {e}")
            
            # Endpoint 2: Torneios específicos
            for tournament_id in self.tournament_ids:
                try:
                    url = f"{self.base_url}/api/tournaments/{tournament_id}/results"
                    response = self.session.get(url, timeout=10)
                    
                    if response.status_code == 200:
                        data = response.json()
                        matches = self._parse_tournament_results(data, tournament_id)
                        all_matches.extend(matches)
                        logger.info(f"   ✓ Torneio {tournament_id}: {len(matches)} partidas")
                except Exception as e:
                    logger.debug(f"   × Torneio {tournament_id}: {e}")
                    continue
            
            logger.info(f"✅ Total recentes: {len(all_matches)}")
            return all_matches
            
        except Exception as e:
            logger.error(f"❌ Erro recent: {e}")
            return []
    
    def _parse_streaming_data(self, data, location_id):
        """Parse dos dados de streaming"""
        matches = []
        
        try:
            # Estrutura pode variar, adapte conforme necessário
            items = data if isinstance(data, list) else data.get('matches', [])
            
            for item in items:
                match = self._extract_match_data(item, is_live=True)
                if match:
                    match['location_id'] = location_id
                    matches.append(match)
        except Exception as e:
            logger.debug(f"Parse streaming error: {e}")
        
        return matches
    
    def _parse_nearest_matches(self, data):
        """Parse do endpoint nearest-matches (NOVO!)"""
        matches = []
        
        try:
            items = data if isinstance(data, list) else data.get('matches', [])
            
            for item in items:
                match = self._extract_match_data(item, is_live=False)
                if match:
                    matches.append(match)
        except Exception as e:
            logger.debug(f"Parse nearest-matches error: {e}")
        
        return matches
    
    def _parse_tournament_results(self, data, tournament_id):
        """Parse dos resultados de torneio"""
        matches = []
        
        try:
            items = data if isinstance(data, list) else data.get('results', [])
            
            for item in items:
                match = self._extract_match_data(item, is_live=False)
                if match:
                    match['tournament_id'] = str(tournament_id)
                    matches.append(match)
        except Exception as e:
            logger.debug(f"Parse tournament error: {e}")
        
        return matches
    
    def _extract_match_data(self, item, is_live=False):
        """Extrai dados de uma partida"""
        try:
            match_id = str(item.get('id', ''))
            if not match_id:
                return None
            
            # Participantes
            p1 = item.get('participant1', {})
            p2 = item.get('participant2', {})
            
            # Data
            date_str = item.get('date') or item.get('scheduled_at')
            date = None
            if date_str:
                try:
                    date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                except:
                    date = datetime.utcnow()
            else:
                date = datetime.utcnow()
            
            # Status
            status_id = item.get('status_id', 0)
            if is_live:
                status = 'live'
            elif status_id == 3 or item.get('status') == 'finished':
                status = 'finished'
            else:
                status = 'scheduled'
            
            return {
                'match_id': match_id,
                'player1_name': p1.get('nickname', 'Unknown'),
                'player2_name': p2.get('nickname', 'Unknown'),
                'player1_team': p1.get('team', {}).get('name') if p1.get('team') else None,
                'player2_team': p2.get('team', {}).get('name') if p2.get('team') else None,
                'score1': item.get('score1'),
                'score2': item.get('score2'),
                'date': date,
                'status': status,
                'location': item.get('location', {}).get('token') if item.get('location') else None,
                'console': item.get('console', {}).get('token') if item.get('console') else None,
                'tournament': item.get('tournament', {}).get('name') if item.get('tournament') else None,
                'tournament_id': item.get('tournament_id'),
                'round': item.get('round', {}).get('name') if item.get('round') else None
            }
        except Exception as e:
            logger.debug(f"Extract error: {e}")
            return None


# ============================================
# FUNÇÕES DE COLETA
# ============================================

def collect_and_save_matches():
    global last_scan_time, scraper_status
    
    try:
        logger.info("=" * 80)
        logger.info("🚀 INICIANDO COLETA")
        logger.info("=" * 80)
        
        scraper_status = "Coletando..."
        scraper = FIFA25Scraper()
        
        with app.app_context():
            before_count = Match.query.count()
            logger.info(f"📊 Antes: {before_count}")
            
            live_matches = scraper.get_live_matches()
            recent_matches = scraper.get_recent_matches()
            
            new_count = 0
            updated_count = 0
            duplicate_count = 0
            
            for match_data in live_matches:
                result = process_match(match_data, is_live=True)
                if result == 'new':
                    new_count += 1
                elif result == 'updated':
                    updated_count += 1
                elif result == 'duplicate':
                    duplicate_count += 1
            
            for match_data in recent_matches:
                result = process_match(match_data, is_live=False)
                if result == 'new':
                    new_count += 1
                elif result == 'updated':
                    updated_count += 1
                elif result == 'duplicate':
                    duplicate_count += 1
            
            db.session.commit()
            
            after_count = Match.query.count()
            last_scan_time = datetime.utcnow()
            scraper_status = "Ativo"
            
            logger.info("=" * 80)
            logger.info(f"✅ FINALIZADO")
            logger.info(f"📊 Antes: {before_count} | Depois: {after_count}")
            logger.info(f"✨ Novas: {new_count} | 🔄 Atualizadas: {updated_count} | ⏭️ Duplicadas: {duplicate_count}")
            logger.info("=" * 80)
            
            return {
                'new': new_count,
                'updated': updated_count,
                'duplicates': duplicate_count
            }
        
    except Exception as e:
        scraper_status = f"Erro: {str(e)}"
        logger.error(f"❌ ERRO: {e}", exc_info=True)
        try:
            db.session.rollback()
        except:
            pass
        return None


def process_match(match_data, is_live=False):
    try:
        match_id = match_data.get('match_id')
        if not match_id:
            return 'error'
        
        existing = Match.query.filter_by(match_id=match_id).first()
        
        if existing:
            should_update = False
            
            new_status = 'live' if is_live else match_data.get('status', 'scheduled')
            if existing.status != new_status:
                existing.status = new_status
                should_update = True
            
            if match_data.get('score1') is not None and existing.score1 != match_data.get('score1'):
                existing.score1 = match_data.get('score1')
                should_update = True
            
            if match_data.get('score2') is not None and existing.score2 != match_data.get('score2'):
                existing.score2 = match_data.get('score2')
                should_update = True
            
            if should_update:
                existing.updated_at = datetime.utcnow()
                logger.info(f"🔄 {existing.player1_name} vs {existing.player2_name}")
                return 'updated'
            else:
                return 'duplicate'
        
        else:
            new_match = Match(
                match_id=match_id,
                player1_name=match_data.get('player1_name'),
                player2_name=match_data.get('player2_name'),
                player1_team=match_data.get('player1_team'),
                player2_team=match_data.get('player2_team'),
                score1=match_data.get('score1'),
                score2=match_data.get('score2'),
                date=match_data.get('date'),
                status='live' if is_live else match_data.get('status', 'scheduled'),
                location=match_data.get('location'),
                console=match_data.get('console'),
                tournament=match_data.get('tournament'),
                tournament_id=match_data.get('tournament_id'),
                round_info=match_data.get('round'),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            db.session.add(new_match)
            logger.info(f"✨ {new_match.player1_name} vs {new_match.player2_name}")
            return 'new'
            
    except Exception as e:
        logger.error(f"❌ Process error: {e}")
        return 'error'


def start_scheduler():
    global scheduler
    
    run_scraper = os.getenv('RUN_SCRAPER', 'true').lower() == 'true'
    
    if not run_scraper:
        logger.info("⏸️  Scraper desabilitado")
        return
    
    if scheduler is None:
        scheduler = BackgroundScheduler()
        interval = int(os.getenv('SCAN_INTERVAL', 30))
        
        scheduler.add_job(
            func=collect_and_save_matches,
            trigger="interval",
            seconds=interval,
            id='fifa25_scraper',
            name='Coletar partidas FIFA25',
            replace_existing=True
        )
        
        scheduler.start()
        logger.info(f"✅ Scheduler: {interval}s")
        collect_and_save_matches()


# ============================================
# ROTAS
# ============================================

@app.route('/')
def dashboard():
    try:
        total_matches = Match.query.count()
        today = datetime.utcnow().date()
        today_matches = Match.query.filter(db.func.date(Match.date) == today).count()
        live_matches = Match.query.filter_by(status='live').all()
        recent_matches = Match.query.order_by(Match.date.desc()).limit(10).all()
        
        # Log para debug
        logger.info(f"Dashboard: {total_matches} total, {len(live_matches)} live, {len(recent_matches)} recent")
        
        # Se não tem partidas live mas tem total, mostra as recentes como se fossem live
        if len(live_matches) == 0 and total_matches > 0:
            logger.info(f"⚠️ Sem partidas 'live', mas existem {total_matches} no banco. Mostrando as mais recentes.")
            live_matches = Match.query.order_by(Match.updated_at.desc()).limit(5).all()
        
        return render_template('dashboard.html',
            total_matches=total_matches,
            today_matches=today_matches,
            live_matches=live_matches,
            recent_matches=recent_matches,
            last_scan=last_scan_time,
            scraper_status=scraper_status
        )
    except Exception as e:
        logger.error(f"Dashboard error: {e}", exc_info=True)
        return render_template('dashboard.html',
            total_matches=0,
            today_matches=0,
            live_matches=[],
            recent_matches=[],
            last_scan=None,
            scraper_status="Erro"
        )


@app.route('/matches')
def matches():
    try:
        page = request.args.get('page', 1, type=int)
        per_page = 50
        
        matches_query = Match.query.order_by(Match.date.desc())
        pagination = matches_query.paginate(page=page, per_page=per_page, error_out=False)
        
        return render_template('matches.html',
            matches=pagination.items,
            pagination=pagination,
            last_scan=last_scan_time
        )
    except Exception as e:
        logger.error(f"Matches error: {e}")
        return render_template('matches.html', matches=[], pagination=None, last_scan=last_scan_time)


@app.route('/api/stats')
def api_stats():
    try:
        total = Match.query.count()
        live = Match.query.filter_by(status='live').count()
        today = datetime.utcnow().date()
        today_matches = Match.query.filter(db.func.date(Match.date) == today).count()
        
        return jsonify({
            'total_matches': total,
            'live_matches': live,
            'today_matches': today_matches,
            'last_scan': last_scan_time.isoformat() if last_scan_time else None,
            'status': scraper_status
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/debug/database-info')
def debug_database_info():
    try:
        total_matches = Match.query.count()
        recent = Match.query.order_by(Match.date.desc()).limit(10).all()
        live_count = Match.query.filter_by(status='live').count()
        scheduled_count = Match.query.filter_by(status='scheduled').count()
        finished_count = Match.query.filter_by(status='finished').count()
        today = datetime.utcnow().date()
        today_count = Match.query.filter(db.func.date(Match.date) == today).count()
        
        return jsonify({
            'status': 'success',
            'database': {
                'total_matches': total_matches,
                'by_status': {
                    'live': live_count,
                    'scheduled': scheduled_count,
                    'finished': finished_count
                },
                'today_matches': today_count
            },
            'scraper': {
                'last_scan': last_scan_time.isoformat() if last_scan_time else None,
                'status': scraper_status
            },
            'recent_matches': [
                {
                    'id': m.match_id,
                    'player1': m.player1_name,
                    'player2': m.player2_name,
                    'score': f"{m.score1 or '-'} x {m.score2 or '-'}",
                    'status': m.status,
                    'date': m.date.isoformat() if m.date else None
                }
                for m in recent
            ]
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/debug/test-scraper')
def debug_test_scraper():
    try:
        scraper = FIFA25Scraper()
        live = scraper.get_live_matches()
        recent = scraper.get_recent_matches()
        
        duplicates = 0
        new = 0
        
        for match_data in recent:
            existing = Match.query.filter_by(match_id=match_data.get('match_id')).first()
            if existing:
                duplicates += 1
            else:
                new += 1
        
        return jsonify({
            'status': 'success',
            'found': {
                'live': len(live),
                'recent': len(recent),
                'total': len(live) + len(recent)
            },
            'analysis': {
                'new_matches': new,
                'duplicates': duplicates
            },
            'sample_matches': [
                {
                    'player1': m.get('player1_name'),
                    'player2': m.get('player2_name'),
                    'status': m.get('status')
                }
                for m in recent[:5]
            ]
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/debug/force-collect')
def debug_force_collect():
    try:
        result = collect_and_save_matches()
        
        if result:
            return jsonify({
                'status': 'success',
                'message': 'Coleta executada!',
                'results': result,
                'total_matches_now': Match.query.count()
            })
        else:
            return jsonify({
                'status': 'error',
                'message': 'Erro na coleta'
            }), 500
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/debug/reset-database')
def debug_reset():
    try:
        deleted = Match.query.delete()
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'Banco resetado!',
            'deleted_matches': deleted
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/debug/list-all-matches')
def debug_list_all():
    """Lista TODAS as partidas com detalhes"""
    try:
        all_matches = Match.query.all()
        
        return jsonify({
            'status': 'success',
            'total': len(all_matches),
            'matches': [
                {
                    'id': m.match_id,
                    'player1': m.player1_name,
                    'player2': m.player2_name,
                    'score': f"{m.score1 or '-'} x {m.score2 or '-'}",
                    'status': m.status,
                    'date': m.date.isoformat() if m.date else None,
                    'created_at': m.created_at.isoformat() if m.created_at else None,
                    'updated_at': m.updated_at.isoformat() if m.updated_at else None
                }
                for m in all_matches
            ]
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ============================================
# INICIALIZAÇÃO
# ============================================

with app.app_context():
    db.create_all()
    logger.info("✅ Tabelas criadas")
    start_scheduler()


if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)