import os
import threading
import time
from datetime import datetime

from flask import Flask, render_template, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from dotenv import load_dotenv
import logging

# ======================================================
# Configuração básica
# ======================================================

load_dotenv()

logging.basicConfig(level=logging.INFO)

app = Flask(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL não definida")

# Corrige postgres:// para postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# ======================================================
# Models
# ======================================================

class Player(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)

class Match(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    player_home = db.Column(db.String(100))
    player_away = db.Column(db.String(100))
    score_home = db.Column(db.Integer)
    score_away = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# ======================================================
# Inicialização do banco
# ======================================================

with app.app_context():
    db.create_all()
    logging.info("Banco de dados inicializado")

# ======================================================
# Background worker (SEM SCRAPER por enquanto)
# ======================================================

def background_worker():
    logging.info("Background worker iniciado")

    while True:
        try:
            with app.app_context():
                logging.info("Worker ativo - verificação básica")

                total_matches = db.session.query(func.count(Match.id)).scalar()
                total_players = db.session.query(func.count(Player.id)).scalar()

                logging.info(
                    f"Status DB → Matches: {total_matches}, Players: {total_players}"
                )

        except Exception as e:
            logging.error(f"Erro no worker: {e}")

        time.sleep(60)

threading.Thread(target=background_worker, daemon=True).start()

# ======================================================
# Rotas
# ======================================================

@app.route("/")
def dashboard():
    with app.app_context():
        matches = Match.query.order_by(Match.created_at.desc()).limit(50).all()
        total_matches = Match.query.count()
        total_players = Player.query.count()

    return render_template(
        "dashboard.html",
        matches=matches,
        total_matches=total_matches,
        total_players=total_players,
        last_scan=datetime.utcnow()
    )

@app.route("/health")
def health():
    return jsonify({"status": "ok", "time": datetime.utcnow().isoformat()})

# ======================================================
# Entry point local
# ======================================================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)
