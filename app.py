import os
import logging
from datetime import datetime
import pytz

from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from apscheduler.schedulers.background import BackgroundScheduler

# ✅ IMPORT CORRETO DO SCRAPER
from web_scraper.stadium_scraper import StadiumScraper

# =========================
# CONFIGURAÇÕES BÁSICAS
# =========================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BR_TZ = pytz.timezone("America/Sao_Paulo")

app = Flask(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///fifa25.db")
app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# =========================
# MODELO
# =========================

class Match(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    league = db.Column(db.String(100))
    home = db.Column(db.String(100))
    away = db.Column(db.String(100))
    stadium = db.Column(db.String(100))
    match_time = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(BR_TZ))

# =========================
# SCRAPER
# =========================

scraper = StadiumScraper()

def scan_and_save():
    logger.info("[SCAN] Execução iniciada")

    try:
        matches = scraper.collect()

        if not matches:
            logger.warning("[SCAN] Nenhuma partida encontrada")
            return

        count = 0
        for m in matches:
            match = Match(
                league=m.get("league"),
                home=m.get("home"),
                away=m.get("away"),
                stadium=m.get("stadium"),
                match_time=m.get("time"),
            )
            db.session.add(match)
            count += 1

        db.session.commit()
        logger.info(f"[SCAN] OK — {count} partidas salvas")

    except Exception as e:
        logger.exception(f"[SCAN] Erro crítico: {e}")

# =========================
# ROTAS
# =========================

@app.route("/")
def dashboard():
    matches = Match.query.order_by(Match.created_at.desc()).limit(50).all()
    last_scan = datetime.now(BR_TZ).strftime("%d/%m/%Y %H:%M:%S")

    return render_template(
        "dashboard.html",
        matches=matches,
        last_scan=last_scan
    )

# =========================
# STARTUP
# =========================

with app.app_context():
    db.create_all()
    logger.info("[DB] Tabelas criadas/verificadas")

scheduler = BackgroundScheduler(timezone=BR_TZ)
scheduler.add_job(scan_and_save, "interval", seconds=30)
scheduler.start()

logger.info("[SCHEDULER] Ativo — intervalo 30s")

# ⚠️ IMPORTANTE PARA O RENDER
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
