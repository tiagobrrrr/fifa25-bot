import os
import logging
from datetime import datetime

from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from apscheduler.schedulers.background import BackgroundScheduler

from web_scraper.stadium_scraper import StadiumScraper

# --------------------------------------------------
# CONFIGURAÇÕES BÁSICAS
# --------------------------------------------------

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///fifa25.db"
).replace("postgres://", "postgresql://")

app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# --------------------------------------------------
# MODELO
# --------------------------------------------------

class Match(db.Model):
    __tablename__ = "match"

    id = db.Column(db.Integer, primary_key=True)
    league = db.Column(db.String(120))
    team_a = db.Column(db.String(120))
    team_b = db.Column(db.String(120))
    score = db.Column(db.String(20))
    stadium = db.Column(db.String(120))
    status = db.Column(db.String(50))
    collected_at = db.Column(db.DateTime, default=datetime.utcnow)

# --------------------------------------------------
# SCRAPER + SCHEDULER
# --------------------------------------------------

def scan_and_save():
    logger.info("[SCAN] Execução iniciada")

    try:
        scraper = StadiumScraper()
        matches = scraper.collect_matches()

        if not matches:
            logger.warning("[SCAN] Nenhuma partida encontrada")
            return

        Match.query.delete()

        for m in matches:
            db.session.add(Match(
                league=m.get("league"),
                team_a=m.get("team_a"),
                team_b=m.get("team_b"),
                score=m.get("score"),
                stadium=m.get("stadium"),
                status=m.get("status"),
                collected_at=datetime.utcnow()
            ))

        db.session.commit()
        logger.info(f"[SCAN] {len(matches)} partidas salvas")

    except Exception as e:
        logger.exception(f"[SCAN] Erro crítico: {e}")

# --------------------------------------------------
# ROTAS
# --------------------------------------------------

@app.route("/")
def dashboard():
    matches = Match.query.order_by(Match.collected_at.desc()).all()
    last_scan = datetime.utcnow().strftime("%d/%m/%Y %H:%M:%S UTC")

    return render_template(
        "dashboard.html",
        matches=matches,
        last_scan=last_scan
    )

# --------------------------------------------------
# INIT
# --------------------------------------------------

with app.app_context():
    db.create_all()
    logger.info("[DB] Tabelas recriadas")

scheduler = BackgroundScheduler()
scheduler.add_job(scan_and_save, "interval", seconds=30)
scheduler.start()
logger.info("[SCHEDULER] Ativo (30s)")

# --------------------------------------------------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
