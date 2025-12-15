import logging
from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import os

from stadium_scraper import StadiumScraper

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("app")

app = Flask(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///fifa25.db")
app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# ===================== MODELS =====================

class Match(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    time1 = db.Column(db.String(120))
    time2 = db.Column(db.String(120))
    placar = db.Column(db.String(20))
    liga = db.Column(db.String(120))
    horario = db.Column(db.String(50))
    status = db.Column(db.String(50))
    updated_at = db.Column(db.DateTime)

# ===================== SCRAPER =====================

scraper = StadiumScraper(timeout=15)

# ===================== SCAN =====================

def scan_and_save():
    logger.info("[SCAN] Execução iniciada")

    try:
        matches = scraper.get_live_matches()

        if not matches:
            logger.warning("[SCAN] Nenhuma partida encontrada")
            return

        Match.query.delete()

        for m in matches:
            match = Match(**m)
            db.session.add(match)

        db.session.commit()
        logger.info(f"[SCAN] OK — {len(matches)} partidas salvas")

    except Exception as e:
        logger.error(f"[SCAN] Erro: {e}", exc_info=True)

# ===================== ROUTES =====================

@app.route("/")
def dashboard():
    matches = Match.query.all()
    last_scan = db.session.query(db.func.max(Match.updated_at)).scalar()

    return render_template(
        "dashboard.html",
        matches=matches,
        last_scan=last_scan.strftime("%d/%m/%Y %H:%M:%S") if last_scan else "Nunca executado"
    )

# ===================== INIT =====================

with app.app_context():
    db.create_all()
    logger.info("[DB] Tabelas criadas/verificadas")

scheduler = BackgroundScheduler(daemon=True)
scheduler.add_job(scan_and_save, "interval", seconds=30)
scheduler.start()

logger.info("[SCHEDULER] Ativo — intervalo 30s")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
