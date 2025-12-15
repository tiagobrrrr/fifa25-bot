import os
import logging
from datetime import datetime
from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from apscheduler.schedulers.background import BackgroundScheduler

from web_scraper.stadium_scraper import StadiumScraper

# =====================
# LOG
# =====================
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("app")

# =====================
# DATABASE
# =====================
DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# =====================
# APP
# =====================
app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# =====================
# MODEL
# =====================
class Match(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    match_id = db.Column(db.String(64), unique=True, index=True)
    stadium = db.Column(db.String(120))
    league = db.Column(db.String(120))
    match_time = db.Column(db.String(40))
    team1 = db.Column(db.String(120))
    player1 = db.Column(db.String(120))
    team2 = db.Column(db.String(120))
    player2 = db.Column(db.String(120))
    score = db.Column(db.String(20))
    status = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# =====================
# DB INIT
# =====================
with app.app_context():
    db.create_all()
    log.info("[DB] Tabelas criadas/verificadas")

# =====================
# SCAN
# =====================
def scan_and_save():
    log.info("[SCAN] Execução iniciada")

    scraper = StadiumScraper()  # <<< CORREÇÃO CRÍTICA
    _, matches = scraper.collect()

    if not matches:
        log.warning("[SCAN] Nenhuma partida encontrada")
        return

    inserted = 0
    updated = 0

    with app.app_context():
        for m in matches:
            existing = Match.query.filter_by(match_id=m["match_id"]).first()

            if existing:
                existing.score = m["score"]
                existing.status = m["status"]
                updated += 1
            else:
                db.session.add(Match(**m))
                inserted += 1

        db.session.commit()

    log.info(f"[SCAN] OK — {inserted} novas | {updated} atualizadas")

# =====================
# SCHEDULER
# =====================
scheduler = BackgroundScheduler(daemon=True)
scheduler.add_job(scan_and_save, "interval", seconds=30)
scheduler.start()
log.info("[SCHEDULER] Ativo — intervalo 30s")

# =====================
# ROUTES
# =====================
@app.route("/")
def dashboard():
    matches = Match.query.order_by(Match.id.desc()).limit(200).all()
    return render_template("dashboard.html", matches=matches)

# =====================
# ENTRY
# =====================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
