# -*- coding: utf-8 -*-
"""
app.py

Aplicação principal Flask com scheduler para scraping periódico
"""

import os
import logging
from flask import Flask, render_template, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
from web_scraper.scraper_service import ScraperService

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('app.log', encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)

# Criar aplicação Flask
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SESSION_SECRET', 'dev-secret-key-change-in-production')

# Criar serviço de scraping
scraper_service = ScraperService()

# Estado da aplicação
app_state = {
    'status': 'initializing',
    'last_scrape': None,
    'last_result': None,
    'scheduler_running': False
}


def run_scheduled_scrape():
    """
    Executa scraping agendado
    Chamado pelo scheduler
    """
    try:
        logger.info("🔄 Iniciando scraping agendado...")
        
        # Verificar se deve executar
        if not scraper_service.should_run():
            logger.info("⏰ Fora do horário de torneios, aguardando...")
            return
        
        # Executar scraping
        result = scraper_service.run_scraping()
        
        # Atualizar estado
        app_state['last_scrape'] = datetime.now().isoformat()
        app_state['last_result'] = result
        app_state['status'] = 'running'
        
        # Log resumo
        if result['success']:
            processed = result.get('processed', {})
            logger.info(f"✅ Scraping concluído: "
                       f"{processed.get('tournaments', 0)} torneios, "
                       f"{processed.get('matches', 0)} partidas")
        else:
            logger.error(f"❌ Scraping falhou: {result.get('error')}")
        
    except Exception as e:
        logger.error(f"❌ Erro no scraping agendado: {e}")
        app_state['status'] = 'error'


# Configurar scheduler
scheduler = BackgroundScheduler()

# Obter intervalo de scraping das variáveis de ambiente
SCAN_INTERVAL = int(os.environ.get('SCAN_INTERVAL', 120))  # Padrão: 120 segundos (2 minutos)
RUN_SCRAPER = os.environ.get('RUN_SCRAPER', 'true').lower() == 'true'

if RUN_SCRAPER:
    logger.info(f"✅ Scheduler configurado: intervalo de {SCAN_INTERVAL}s")
    scheduler.add_job(
        func=run_scheduled_scrape,
        trigger='interval',
        seconds=SCAN_INTERVAL,
        id='scraper_job',
        name='Scraper de partidas FIFA25',
        replace_existing=True
    )
    scheduler.start()
    app_state['scheduler_running'] = True
    logger.info("✅ Scheduler iniciado")
else:
    logger.warning("⚠️  Scraper desabilitado (RUN_SCRAPER=false)")


# Rotas Flask
@app.route('/')
def index():
    """Página principal - Dashboard"""
    try:
        # Obter estatísticas
        stats = scraper_service.get_stats()
        
        # Obter resumo atual da API
        from web_scraper.api_client import FIFA25APIClient
        client = FIFA25APIClient()
        summary = client.get_summary()
        
        return render_template('dashboard.html',
                             app_state=app_state,
                             stats=stats,
                             summary=summary)
    except Exception as e:
        logger.error(f"Erro ao renderizar dashboard: {e}")
        return f"Erro: {e}", 500


@app.route('/api/status')
def api_status():
    """API endpoint - Status da aplicação"""
    stats = scraper_service.get_stats()
    
    return jsonify({
        'status': app_state['status'],
        'scheduler_running': app_state['scheduler_running'],
        'scan_interval': SCAN_INTERVAL,
        'last_scrape': app_state['last_scrape'],
        'last_result': app_state['last_result'],
        'stats': stats,
        'timestamp': datetime.now().isoformat()
    })


@app.route('/api/scrape/now')
def api_scrape_now():
    """API endpoint - Executar scraping manualmente"""
    try:
        logger.info("🔄 Scraping manual solicitado")
        result = scraper_service.run_scraping()
        
        app_state['last_scrape'] = datetime.now().isoformat()
        app_state['last_result'] = result
        
        return jsonify({
            'success': True,
            'result': result,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Erro no scraping manual: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500


@app.route('/api/summary')
def api_summary():
    """API endpoint - Resumo dos dados"""
    try:
        from web_scraper.api_client import FIFA25APIClient
        client = FIFA25APIClient()
        summary = client.get_summary()
        
        return jsonify({
            'success': True,
            'summary': summary,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Erro ao obter resumo: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500


@app.route('/api/stats')
def api_stats():
    """API endpoint - Estatísticas do scraper"""
    stats = scraper_service.get_stats()
    
    return jsonify({
        'success': True,
        'stats': stats,
        'timestamp': datetime.now().isoformat()
    })


@app.route('/health')
def health():
    """Health check para Render"""
    return jsonify({
        'status': 'healthy',
        'scheduler': app_state['scheduler_running'],
        'timestamp': datetime.now().isoformat()
    })


# Executar primeira verificação ao iniciar
@app.before_first_request
def initial_scrape():
    """Executa scraping inicial ao iniciar a aplicação"""
    logger.info("🚀 Executando scraping inicial...")
    try:
        result = scraper_service.run_scraping()
        app_state['last_scrape'] = datetime.now().isoformat()
        app_state['last_result'] = result
        app_state['status'] = 'running'
        logger.info("✅ Scraping inicial concluído")
    except Exception as e:
        logger.error(f"❌ Erro no scraping inicial: {e}")
        app_state['status'] = 'error'


# Cleanup ao encerrar
def shutdown_scheduler():
    """Encerra o scheduler gracefully"""
    if scheduler.running:
        logger.info("🛑 Encerrando scheduler...")
        scheduler.shutdown()
        logger.info("✅ Scheduler encerrado")


import atexit
atexit.register(shutdown_scheduler)


# Iniciar aplicação
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    
    logger.info("="*80)
    logger.info("🚀 FIFA25 Bot - ESportsBattle Scraper")
    logger.info("="*80)
    logger.info(f"   Porta: {port}")
    logger.info(f"   Debug: {debug}")
    logger.info(f"   Scraper: {'Ativo' if RUN_SCRAPER else 'Inativo'}")
    logger.info(f"   Intervalo: {SCAN_INTERVAL}s")
    logger.info("="*80)
    
    app.run(
        host='0.0.0.0',
        port=port,
        debug=debug
    )