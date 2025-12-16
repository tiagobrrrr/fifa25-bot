import logging
from datetime import datetime
import pytz

from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from apscheduler.schedulers.background import BackgroundScheduler

from web_scraper.stadium_scraper import StadiumScraper

# ------------------------------------------------------------------------------
# CONFIG
# ------------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("app")

BR_TZ = pytz.timezone("America/Sao_Paulo")

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///matches.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# ------------------------------------------------------------------------------
# MODEL
# ------------------------------------------------------------------------------
class Match(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    league = db.Column(db.String(120))
    home = db.Column(db.String(120))
    away = db.Column(db.String(120))
    stadium = db.Column(db.String(120))
    match_time = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(BR_TZ))

# ------------------------------------------------------------------------------
# DB INIT (RESET SEGURO)
# ------------------------------------------------------------------------------
with app.app_context():
    db.drop_all()
    db.create_all()
    logger.info("[DB] Tabelas recriadas")

# ------------------------------------------------------------------------------
# SCAN JOB
# ------------------------------------------------------------------------------
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
                    home=m.get("home"),
                    away=m.get("away"),
                    stadium=m.get("stadium"),
                    match_time=m.get("time"),
                )
            )

        db.session.commit()
        logger.info(f"[SCAN] {len(matches)} partidas salvas")

    except Exception as e:
        logger.exception(f"[SCAN] Erro crítico: {e}")

# ------------------------------------------------------------------------------
# SCHEDULER
# ------------------------------------------------------------------------------
scheduler = BackgroundScheduler(timezone=BR_TZ)
scheduler.add_job(scan_and_save, "interval", seconds=30)
scheduler.start()
logger.info("[SCHEDULER] Ativo (30s)")

# ------------------------------------------------------------------------------
# ROUTES
# ------------------------------------------------------------------------------
@app.route("/")
def dashboard():
    matches = Match.query.order_by(Match.created_at.desc()).limit(50).all()
    last_scan = datetime.now(BR_TZ).strftime("%d/%m/%Y %H:%M:%S")

    return render_template(
        "dashboard.html",
        matches=matches,
        last_scan=last_scan
    )

# ------------------------------------------------------------------------------
# MAIN
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
