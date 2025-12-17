import os
import logging
from datetime import datetime

from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from apscheduler.schedulers.background import BackgroundScheduler
from tzlocal import get_localzone

from web_scraper.stadium_scraper import StadiumScraper

# -----------------------------------------------------------------------------
# CONFIG
# -----------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///matches.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

LOCAL_TZ = get_localzone()

# -----------------------------------------------------------------------------
# MODEL
# -----------------------------------------------------------------------------
class Match(db.Model):
    __tablename__ = "match"

    id = db.Column(db.Integer, primary_key=True)

    league = db.Column(db.String(120))
    home_team = db.Column(db.String(120))
    away_team = db.Column(db.String(120))
    score = db.Column(db.String(20))
    stadium = db.Column(db.String(120))
    status = db.Column(db.String(50))

    collected_at = db.Column(db.DateTime, default=datetime.utcnow)

# -----------------------------------------------------------------------------
# DB INIT (recria corretamente)
# -----------------------------------------------------------------------------
with app.app_context():
    db.drop_all()
    db.create_all()
    logger.info("[DB] Tabelas recriadas")

# -----------------------------------------------------------------------------
# SCRAPER JOB
# -----------------------------------------------------------------------------
def scan_and_save():
    logger.info("[SCAN] Execução iniciada")

    try:
        scraper = StadiumScraper()
        matches = scraper.collect()

        if not matches:
            logger.warning("[SCAN] Nenhuma partida encontrada")
            return

        Match.query.delete()

        for m in matches:
            db.session.add(
                Match(
                    league=m.get("league"),
                    home_team=m.get("home"),
                    away_team=m.get("away"),
                    score=m.get("score"),
                    stadium=m.get("stadium"),
                    status=m.get("status"),
                    collected_at=datetime.now(LOCAL_TZ),
                )
            )

        db.session.commit()
        logger.info(f"[SCAN] {len(matches)} partidas salvas")

    except Exception as e:
        logger.exception(f"[SCAN] Erro crítico: {e}")

# -----------------------------------------------------------------------------
# SCHEDULER
# -----------------------------------------------------------------------------
scheduler = BackgroundScheduler(timezone=LOCAL_TZ)
scheduler.add_job(scan_and_save, "interval", seconds=30)
scheduler.start()

logger.info("[SCHEDULER] Ativo (30s)")

# -----------------------------------------------------------------------------
# ROUTES
# -----------------------------------------------------------------------------
@app.route("/")
def dashboard():
    matches = Match.query.order_by(Match.collected_at.desc()).all()

    last_scan = matches[0].collected_at.astimezone(LOCAL_TZ) if matches else None

    return render_template(
        "dashboard.html",
        matches=matches,
        last_scan=last_scan,
    )

# -----------------------------------------------------------------------------
# ENTRY
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=False)
