import os
import logging
from datetime import datetime
import pytz

from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from apscheduler.schedulers.background import BackgroundScheduler

from web_scraper.stadium_scraper import StadiumScraper

# =========================
# CONFIG
# =========================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("app")

TZ_BR = pytz.timezone("America/Sao_Paulo")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///matches.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# =========================
# MODEL
# =========================
class Match(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    league = db.Column(db.String(100))
    player_home = db.Column(db.String(100))
    player_away = db.Column(db.String(100))
    stadium = db.Column(db.String(100))
    match_time = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(TZ_BR))

# =========================
# DB INIT
# =========================
with app.app_context():
    db.create_all()
    logger.info("[DB] Tabelas criadas/verificadas")

# =========================
# SCRAPER JOB
# =========================
def scan_and_save():
    logger.info("[SCAN] Execução iniciada")

    try:
        scraper = StadiumScraper()
        matches = scraper.scan_and_parse()

        if not matches:
            logger.warning("[SCAN] Nenhuma partida encontrada")
            return

        saved = 0
        for m in matches:
            match = Match(
                league=m.get("league"),
                player_home=m.get("player_home"),
                player_away=m.get("player_away"),
                stadium=m.get("stadium"),
                match_time=m.get("match_time"),
            )
            db.session.add(match)
            saved += 1

        db.session.commit()
        logger.info(f"[SCAN] OK — {saved} partidas salvas")

    except Exception as e:
        logger.exception(f"[SCAN] Erro crítico: {e}")

# =========================
# SCHEDULER
# =========================
scheduler = BackgroundScheduler(timezone=TZ_BR)
scheduler.add_job(scan_and_save, "interval", seconds=30)
scheduler.start()

logger.info("[SCHEDULER] Ativo — intervalo 30s")

# =========================
# ROUTES
# =========================
@app.route("/")
def dashboard():
    matches = Match.query.order_by(Match.created_at.desc()).limit(50).all()

    last_scan = matches[0].created_at.strftime("%d/%m/%Y %H:%M:%S") if matches else "—"

    return render_template(
        "dashboard.html",
        matches=matches,
        last_scan=last_scan
    )

# =========================
# MAIN
# =========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
