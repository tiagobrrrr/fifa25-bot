import os
import logging
from datetime import datetime

from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from apscheduler.schedulers.background import BackgroundScheduler
from tzlocal import get_localzone

# IMPORT CORRETO DO SCRAPER
from web_scraper.stadium_scraper import StadiumScraper

# --------------------
# CONFIG
# --------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("app")

app = Flask(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///matches.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# --------------------
# MODEL
# --------------------
class Match(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    league = db.Column(db.String(120))
    title = db.Column(db.String(255))       # Texto completo do card
    stadium = db.Column(db.String(120))
    match_time = db.Column(db.String(60))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# --------------------
# DB INIT
# --------------------
with app.app_context():
    db.drop_all()
    db.create_all()
    logger.info("[DB] Tabelas recriadas")

# --------------------
# SCRAPER JOB
# --------------------
def scan_and_save():
    logger.info("[SCAN] Execução iniciada")

    try:
        scraper = StadiumScraper()
        results = scraper.run()  # 🔥 MÉTODO CORRETO

        if not results:
            logger.warning("[SCAN] Nenhuma partida encontrada")
            return

        saved = 0

        for item in results:
            match = Match(
                league=item.get("league"),
                title=item.get("title"),
                stadium=item.get("stadium"),
                match_time=item.get("match_time"),
            )
            db.session.add(match)
            saved += 1

        db.session.commit()
        logger.info(f"[SCAN] {saved} partidas salvas")

    except Exception as e:
        logger.exception(f"[SCAN] Erro crítico: {e}")

# --------------------
# SCHEDULER
# --------------------
scheduler = BackgroundScheduler(timezone=str(get_localzone()))
scheduler.add_job(scan_and_save, "interval", seconds=30)
scheduler.start()
logger.info("[SCHEDULER] Ativo (30s)")

# --------------------
# ROUTES
# --------------------
@app.route("/")
def dashboard():
    matches = (
        Match.query
        .order_by(Match.created_at.desc())
        .limit(50)
        .all()
    )

    last_scan = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    return render_template(
        "dashboard.html",
        matches=matches,
        last_scan=last_scan
    )

# --------------------
# ENTRY
# --------------------
if __name__ == "__main__":
    app.run(debug=True)
