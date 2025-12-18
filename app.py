import os
import logging
from datetime import datetime
import pytz

from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from apscheduler.schedulers.background import BackgroundScheduler

from web_scraper.stadium_scraper import StadiumScraper

# ======================================================
# CONFIGURAÇÕES BÁSICAS
# ======================================================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("app")

BRAZIL_TZ = pytz.timezone("America/Sao_Paulo")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///database.db"
)

# ======================================================
# APP + DB
# ======================================================

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# ======================================================
# MODELO
# ======================================================

class Match(db.Model):
    __tablename__ = "match"

    id = db.Column(db.Integer, primary_key=True)

    league = db.Column(db.String(100))
    team_home = db.Column(db.String(100))
    team_away = db.Column(db.String(100))
    score = db.Column(db.String(20))
    stadium = db.Column(db.String(100))
    status = db.Column(db.String(50))

    collected_at = db.Column(db.DateTime, default=lambda: datetime.now(BRAZIL_TZ))

# ======================================================
# BANCO
# ======================================================

with app.app_context():
    db.drop_all()
    db.create_all()
    logger.info("[DB] Tabelas recriadas")

# ======================================================
# SCRAPER + SCHEDULER
# ======================================================

def scan_and_save():
    logger.info("[SCAN] Execução iniciada")

    try:
        scraper = StadiumScraper()
        matches = scraper.collect()

        if not matches:
            logger.warning("[SCAN] Nenhuma partida encontrada")
            return

        for m in matches:
            match = Match(
                league=m.get("league"),
                team_home=m.get("home"),
                team_away=m.get("away"),
                score=m.get("score"),
                stadium=m.get("stadium"),
                status=m.get("status"),
                collected_at=datetime.now(BRAZIL_TZ)
            )
            db.session.add(match)

        db.session.commit()
        logger.info(f"[SCAN] {len(matches)} partidas salvas")

    except Exception as e:
        logger.exception(f"[SCAN] Erro crítico: {e}")

# ======================================================
# SCHEDULER
# ======================================================

scheduler = BackgroundScheduler(timezone=BRAZIL_TZ)
scheduler.add_job(scan_and_save, "interval", seconds=30)

scheduler.start()
logger.info("[SCHEDULER] Ativo (30s)")

# ======================================================
# ROTAS
# ======================================================

@app.route("/")
def dashboard():
    matches = Match.query.order_by(Match.collected_at.desc()).all()

    last_scan = matches[0].collected_at if matches else None

    return render_template(
        "dashboard.html",
        matches=matches,
        last_scan=last_scan
    )

# ======================================================
# MAIN
# ======================================================

if __name__ == "__main__":
    app.run(debug=True)
