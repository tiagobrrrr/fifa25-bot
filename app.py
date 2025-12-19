import os
import logging
from datetime import datetime

from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from apscheduler.schedulers.background import BackgroundScheduler

from web_scraper.stadium_scraper import StadiumScraper

# =========================
# CONFIGURAÇÃO BÁSICA
# =========================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "sqlite:///local.db"
)

# Fix para Render PostgreSQL (postgres:// -> postgresql://)
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# =========================
# MODELS
# =========================
class Match(db.Model):
    __tablename__ = "match"

    id = db.Column(db.Integer, primary_key=True)
    league = db.Column(db.String(120))
    home = db.Column(db.String(120))
    away = db.Column(db.String(120))
    score = db.Column(db.String(20))
    stadium = db.Column(db.String(120))
    status = db.Column(db.String(50))
    collected_at = db.Column(db.DateTime, default=datetime.utcnow)

class Player(db.Model):
    __tablename__ = "player"

    id = db.Column(db.Integer, primary_key=True)
    nickname = db.Column(db.String(120))
    team = db.Column(db.String(120))
    matches = db.Column(db.Integer, default=0)
    wins = db.Column(db.Integer, default=0)
    losses = db.Column(db.Integer, default=0)

# =========================
# BANCO - SETUP INICIAL
# =========================
def init_database():
    """Inicializa banco apenas uma vez"""
    try:
        with app.app_context():
            # Verifica se precisa criar
            inspector = db.inspect(db.engine)
            if not inspector.has_table("match"):
                logger.info("[DB] Criando tabelas...")
                db.create_all()
                logger.info("[DB] ✅ Tabelas criadas com sucesso")
            else:
                logger.info("[DB] Tabelas já existem")
    except Exception as e:
        logger.error(f"[DB] Erro ao inicializar: {e}")

init_database()

# =========================
# SCRAPER + SCHEDULER
# =========================
def scan_and_save():
    logger.info("[SCAN] Execução iniciada")

    try:
        scraper = StadiumScraper()
        results = scraper.collect()

        if not results:
            logger.warning("[SCAN] Nenhuma partida encontrada")
            return

        with app.app_context():
            for r in results:
                match = Match(
                    league=r.get("league"),
                    home=r.get("home"),
                    away=r.get("away"),
                    score=r.get("score"),
                    stadium=r.get("stadium"),
                    status=r.get("status"),
                )
                db.session.add(match)

            db.session.commit()
            logger.info(f"[SCAN] ✅ {len(results)} partidas salvas")

    except Exception as e:
        logger.exception("[SCAN] Erro crítico")

scheduler = BackgroundScheduler()
scheduler.add_job(scan_and_save, "interval", seconds=60)
scheduler.start()

logger.info("[SCHEDULER] Ativo (60s)")

# =========================
# ROTAS
# =========================
@app.route("/")
def dashboard():
    try:
        matches = Match.query.order_by(Match.collected_at.desc()).limit(100).all()
        players = Player.query.all()

        logger.info(f"Status DB → Matches: {len(matches)}")
        logger.info(f"Status DB → Players: {len(players)}")

        return render_template(
            "dashboard.html",
            matches=matches,
            players=players
        )
    except Exception as e:
        logger.exception("[ROUTE] Erro no dashboard")
        return f"Erro: {e}", 500

@app.route("/health")
def health():
    return {
        "status": "ok",
        "database": DATABASE_URL.split("@")[-1] if "@" in DATABASE_URL else "local"
    }

# =========================
# ENTRYPOINT
# =========================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)