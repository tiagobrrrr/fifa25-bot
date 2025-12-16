import os
import logging
from datetime import datetime

from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from apscheduler.schedulers.background import BackgroundScheduler

# IMPORT CORRETO DO SCRAPER
from web_scraper.stadium_scraper import StadiumScraper

# --------------------------------------------------
# CONFIG
# --------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("app")

app = Flask(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///matches.db")
app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# --------------------------------------------------
# MODEL (ALINHADO COM O BANCO REAL)
# --------------------------------------------------
class Match(db.Model):
    __tablename__ = "match"

    id = db.Column(db.Integer, primary_key=True)
    league = db.Column(db.String(120))
    title = db.Column(db.String(255))        # Ex: "Player A vs Player B"
    stadium = db.Column(db.String(120))
    match_time = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# --------------------------------------------------
# INIT DB
# --------------------------------------------------
with app.app_context():
    db.create_all()
    logger.info("[DB] Tabelas criadas/verificadas")

# --------------------------------------------------
# SCAN FUNCTION
# --------------------------------------------------
def scan_and_save():
    logger.info("[SCAN] Execução iniciada")

    try:
        scraper = StadiumScraper()
        matches = scraper.collect()  # AGORA EXISTE

        if not matches:
            logger.warning("[SCAN] Nenhuma partida encontrada")
            return

        for m in matches:
            match = Match(
                league=m.get("league"),
                title=m.get("title"),
                stadium=m.get("stadium"),
                match_time=m.get("match_time"),
            )
            db.session.add(match)

        db.session.commit()
        logger.info(f"[SCAN] OK — {len(matches)} partidas salvas")

    except Exception as e:
        logger.exception(f"[SCAN] Erro crítico: {e}")

# --------------------------------------------------
# SCHEDULER
# --------------------------------------------------
scheduler = BackgroundScheduler(timezone="America/Sao_Paulo")
scheduler.add_job(scan_and_save, "interval", seconds=30)
scheduler.start()

logger.info("[SCHEDULER] Ativo — intervalo 30s")

# --------------------------------------------------
# ROUTES
# --------------------------------------------------
@app.route("/")
def dashboard():
    matches = Match.query.order_by(Match.created_at.desc()).limit(50).all()

    last_scan = (
        matches[0].created_at.strftime("%d/%m/%Y %H:%M:%S")
        if matches else "Nenhuma varredura ainda"
    )

    return render_template(
        "dashboard.html",
        matches=matches,
        last_scan=last_scan
    )

# --------------------------------------------------
# MAIN
# --------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True)
