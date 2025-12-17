import os
import logging
from datetime import datetime
import pytz

from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from apscheduler.schedulers.background import BackgroundScheduler

from web_scraper.stadium_scraper import StadiumScraper

# ==========================================================
# CONFIGURAÇÕES GERAIS
# ==========================================================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BR_TZ = pytz.timezone("America/Sao_Paulo")

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)

app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
    "DATABASE_URL",
    "sqlite:///" + os.path.join(BASE_DIR, "database.db")
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# ==========================================================
# MODELO
# ==========================================================

class Match(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    league = db.Column(db.String(120))
    home = db.Column(db.String(120))
    away = db.Column(db.String(120))
    score = db.Column(db.String(20))
    stadium = db.Column(db.String(120))
    status = db.Column(db.String(50))
    collected_at = db.Column(db.DateTime)

# ==========================================================
# FUNÇÃO DE SCAN
# ==========================================================

def scan_and_save():
    logger.info("[SCAN] Execução iniciada")

    try:
        scraper = StadiumScraper()
        matches = scraper.collect()  # 🔥 MÉTODO REAL E EXISTENTE

        if not matches:
            logger.warning("[SCAN] Nenhuma partida encontrada")
            return

        Match.query.delete()

        for m in matches:
            match = Match(
                league=m.get("league"),
                home=m.get("home"),
                away=m.get("away"),
                score=m.get("score"),
                stadium=m.get("stadium"),
                status=m.get("status"),
                collected_at=datetime.now(BR_TZ)
            )
            db.session.add(match)

        db.session.commit()
        logger.info(f"[SCAN] {len(matches)} partidas salvas com sucesso")

    except Exception as e:
        logger.exception(f"[SCAN] Erro crítico: {e}")

# ==========================================================
# ROTAS
# ==========================================================

@app.route("/")
def dashboard():
    matches = Match.query.all()
    last_scan = db.session.query(db.func.max(Match.collected_at)).scalar()

    return render_template(
        "dashboard.html",
        matches=matches,
        last_scan=last_scan
    )

# ==========================================================
# STARTUP
# ==========================================================

def start_scheduler():
    scheduler = BackgroundScheduler(timezone=BR_TZ)
    scheduler.add_job(scan_and_save, "interval", seconds=30)
    scheduler.start()
    logger.info("[SCHEDULER] Ativo (30s)")

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        logger.info("[DB] Tabelas criadas")

    start_scheduler()
    app.run(host="0.0.0.0", port=10000)
