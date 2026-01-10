from flask import Flask, render_template, jsonify, request
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
import os
import logging
from dotenv import load_dotenv

# Carrega variáveis de ambiente
load_dotenv()

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Inicializa Flask
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SESSION_SECRET', 'dev-secret-key-change-this')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///fifa25.db')

# Correção para PostgreSQL do Render
if app.config['SQLALCHEMY_DATABASE_URI'].startswith('postgres://'):
    app.config['SQLALCHEMY_DATABASE_URI'] = app.config['SQLALCHEMY_DATABASE_URI'].replace('postgres://', 'postgresql://')

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,
    'pool_recycle': 300,
}

# IMPORTANTE: Importa db e models DEPOIS de configurar o app
from models import db, Match, Player

# Inicializa o banco com o app
db.init_app(app)

# Variáveis globais
last_scan_time = None
scraper_status = "Aguardando primeira execução"
scheduler = None

# ============================================
# FUNÇÕES DE COLETA - MELHORADAS
# ============================================

def collect_and_save_matches():
    """Coleta e salva partidas com sistema de atualização inteligente"""
    global last_scan_time, scraper_status
    
    try:
        logger.info("=" * 80)
        logger.info("🚀 INICIANDO COLETA DE PARTIDAS FIFA25")
        logger.info("=" * 80)
        
        scraper_status = "Coletando..."
        
        # Importa scraper aqui para evitar circular imports
        from web_scraper.fifa25_scraper import FIFA25Scraper
        scraper = FIFA25Scraper()
        
        # Estatísticas
        with app.app_context():
            before_count = Match.query.count()
            logger.info(f"📊 Partidas no banco ANTES da coleta: {before_count}")
            
            # Coleta partidas
            live_matches = scraper.get_live_matches()
            recent_matches = scraper.get_recent_matches()
            
            logger.info(f"🔍 Partidas encontradas pelo scraper:")
            logger.info(f"   └─ Ao vivo: {len(live_matches)}")
            logger.info(f"   └─ Recentes: {len(recent_matches)}")
            
            # Contadores
            new_count = 0
            updated_count = 0
            duplicate_count = 0
            error_count = 0
            
            # Processa partidas ao vivo
            logger.info("🔴 Processando partidas AO VIVO...")
            for match_data in live_matches:
                result = process_match(match_data, is_live=True)
                if result == 'new':
                    new_count += 1
                elif result == 'updated':
                    updated_count += 1
                elif result == 'duplicate':
                    duplicate_count += 1
                else:
                    error_count += 1
            
            # Processa partidas recentes
            logger.info("📋 Processando partidas RECENTES...")
            for match_data in recent_matches:
                result = process_match(match_data, is_live=False)
                if result == 'new':
                    new_count += 1
                elif result == 'updated':
                    updated_count += 1
                elif result == 'duplicate':
                    duplicate_count += 1
                else:
                    error_count += 1
            
            # Commit de todas as mudanças
            db.session.commit()
            
            # Estatísticas finais
            after_count = Match.query.count()
            last_scan_time = datetime.utcnow()
            scraper_status = "Ativo"
            
            logger.info("=" * 80)
            logger.info("✅ COLETA FINALIZADA COM SUCESSO!")
            logger.info(f"📊 ESTATÍSTICAS:")
            logger.info(f"   ├─ Partidas no banco ANTES: {before_count}")
            logger.info(f"   ├─ Partidas no banco DEPOIS: {after_count}")
            logger.info(f"   ├─ Novas partidas salvas: {new_count}")
            logger.info(f"   ├─ Partidas atualizadas: {updated_count}")
            logger.info(f"   ├─ Duplicatas ignoradas: {duplicate_count}")
            logger.info(f"   └─ Erros encontrados: {error_count}")
            logger.info("=" * 80)
            
            return {
                'new': new_count,
                'updated': updated_count,
                'duplicates': duplicate_count,
                'errors': error_count
            }
        
    except Exception as e:
        scraper_status = f"Erro: {str(e)}"
        logger.error(f"❌ ERRO CRÍTICO na coleta: {e}", exc_info=True)
        try:
            db.session.rollback()
        except:
            pass
        return None


def process_match(match_data, is_live=False):
    """
    Processa uma partida individualmente com lógica inteligente
    Returns: 'new', 'updated', 'duplicate', ou 'error'
    """
    try:
        match_id = match_data.get('match_id')
        
        if not match_id:
            logger.warning("⚠️  Match sem ID, ignorando...")
            return 'error'
        
        # Busca partida existente
        existing = Match.query.filter_by(match_id=match_id).first()
        
        if existing:
            # Verifica se precisa atualizar
            should_update = False
            updates = []
            
            # Atualiza status se mudou
            new_status = 'live' if is_live else match_data.get('status', 'scheduled')
            if existing.status != new_status:
                existing.status = new_status
                should_update = True
                updates.append(f"status: {new_status}")
            
            # Atualiza placar se disponível
            if match_data.get('score1') is not None and existing.score1 != match_data.get('score1'):
                existing.score1 = match_data.get('score1')
                should_update = True
                updates.append(f"score1: {match_data.get('score1')}")
            
            if match_data.get('score2') is not None and existing.score2 != match_data.get('score2'):
                existing.score2 = match_data.get('score2')
                should_update = True
                updates.append(f"score2: {match_data.get('score2')}")
            
            # Atualiza timestamp
            if should_update:
                existing.updated_at = datetime.utcnow()
                logger.info(f"🔄 Atualizada: {existing.player1_name} vs {existing.player2_name} ({', '.join(updates)})")
                return 'updated'
            else:
                logger.debug(f"⏭️  Duplicata: {existing.player1_name} vs {existing.player2_name}")
                return 'duplicate'
        
        else:
            # Cria nova partida
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
                round_info=match_data.get('round'),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            db.session.add(new_match)
            logger.info(f"✨ Nova partida: {new_match.player1_name} vs {new_match.player2_name} [{new_match.status}]")
            return 'new'
            
    except Exception as e:
        logger.error(f"❌ Erro ao processar partida: {e}")
        return 'error'


def start_scheduler():
    """Inicia o scheduler de coletas automáticas"""
    global scheduler
    
    run_scraper = os.getenv('RUN_SCRAPER', 'true').lower() == 'true'
    
    if not run_scraper:
        logger.info("⏸️  Scraper desabilitado (RUN_SCRAPER=false)")
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
        logger.info(f"✅ Scheduler iniciado! Coletando a cada {interval} segundos")
        
        # Primeira coleta imediata
        collect_and_save_matches()


# ============================================
# ROTAS PRINCIPAIS
# ============================================

@app.route('/')
def dashboard():
    """Dashboard principal"""
    try:
        total_matches = Match.query.count()
        today = datetime.utcnow().date()
        today_matches = Match.query.filter(
            db.func.date(Match.date) == today
        ).count()
        
        live_matches = Match.query.filter_by(status='live').all()
        
        recent_matches = Match.query.order_by(
            Match.date.desc()
        ).limit(10).all()
        
        return render_template('dashboard.html',
            total_matches=total_matches,
            today_matches=today_matches,
            live_matches=live_matches,
            recent_matches=recent_matches,
            last_scan=last_scan_time,
            scraper_status=scraper_status
        )
    except Exception as e:
        logger.error(f"Erro no dashboard: {e}")
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
    """Lista todas as partidas"""
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
        logger.error(f"Erro ao listar partidas: {e}")
        return render_template('matches.html', matches=[], pagination=None, last_scan=last_scan_time)


@app.route('/api/stats')
def api_stats():
    """API com estatísticas gerais"""
    try:
        total = Match.query.count()
        live = Match.query.filter_by(status='live').count()
        
        today = datetime.utcnow().date()
        today_matches = Match.query.filter(
            db.func.date(Match.date) == today
        ).count()
        
        return jsonify({
            'total_matches': total,
            'live_matches': live,
            'today_matches': today_matches,
            'last_scan': last_scan_time.isoformat() if last_scan_time else None,
            'status': scraper_status
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================
# ROTAS DE DEBUG
# ============================================

@app.route('/debug/database-info')
def debug_database_info():
    """Mostra informações completas do banco"""
    try:
        total_matches = Match.query.count()
        
        recent = Match.query.order_by(Match.date.desc()).limit(10).all()
        
        live_count = Match.query.filter_by(status='live').count()
        scheduled_count = Match.query.filter_by(status='scheduled').count()
        finished_count = Match.query.filter_by(status='finished').count()
        
        today = datetime.utcnow().date()
        today_count = Match.query.filter(
            db.func.date(Match.date) == today
        ).count()
        
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
    """Testa o scraper sem salvar"""
    try:
        from web_scraper.fifa25_scraper import FIFA25Scraper
        scraper = FIFA25Scraper()
        
        live = scraper.get_live_matches()
        recent = scraper.get_recent_matches()
        
        duplicates = 0
        new = 0
        
        for match_data in recent:
            existing = Match.query.filter_by(
                match_id=match_data.get('match_id')
            ).first()
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
    """Força uma coleta imediata"""
    try:
        result = collect_and_save_matches()
        
        if result:
            return jsonify({
                'status': 'success',
                'message': 'Coleta forçada executada!',
                'results': result,
                'total_matches_now': Match.query.count()
            })
        else:
            return jsonify({
                'status': 'error',
                'message': 'Erro durante a coleta'
            }), 500
            
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/debug/clear-old-matches')
def debug_clear_old():
    """Remove partidas antigas (7+ dias)"""
    try:
        week_ago = datetime.utcnow() - timedelta(days=7)
        deleted = Match.query.filter(Match.date < week_ago).delete()
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'deleted': deleted,
            'remaining': Match.query.count()
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/debug/reset-database')
def debug_reset():
    """⚠️ CUIDADO: Reseta todo o banco"""
    try:
        deleted = Match.query.delete()
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': '⚠️ Banco resetado!',
            'deleted_matches': deleted
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ============================================
# INICIALIZAÇÃO
# ============================================

with app.app_context():
    db.create_all()
    logger.info("✅ Tabelas do banco criadas/verificadas")
    start_scheduler()


if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
