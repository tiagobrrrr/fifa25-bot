import os
import threading
import time
import logging
from datetime import datetime

from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy

# -------------------------------------------------
# APP CONFIG
# -------------------------------------------------
app = Flask(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL não configurada")

app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

logging.basicConfig(level=logging.INFO)

# -------------------------------------------------
# MODELS (ALINHE OS NOMES COM O BANCO!)
# -------------------------------------------------
class Player(db.Model):
    __tablename__ = "player"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)

class Match(db.Model):
    __tablename__ = "match"

    id = db.Column(db.Integer, primary_key=True)

    # ⚠️ AJUSTE ESTES NOMES CONFORME O BANCO
    player_home = db.Column(db.String(100))
    player_away = db.Column(db.String(100))

    score_home = db.Column(db.Integer)
    score_away = db.Column(db.Integer)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# -------------------------------------------------
# ROUTES
# -------------------------------------------------
@app.route("/")
def dashboard():
    matches = Match.query.order_by(Match.created_at.desc()).limit(50).all()
    total_matches = Match.query.count()
    total_players = Player.query.count()

    return render_template(
        "dashboard.html",
        matches=matches,
        total_matches=total_matches,
        total_players=total_players
    )

# -------------------------------------------------
# BACKGROUND WORKER (SAFE)
# -------------------------------------------------
def background_worker():
    with app.app_context():
        logging.info("Worker em background iniciado")

        while True:
            try:
                total_matches = Match.query.count()
                total_players = Player.query.count()

                logging.info(
                    f"Status DB → Matches: {total_matches}, Players: {total_players}"
                )

            except Exception as e:
                logging.error(f"Erro no worker: {e}")

            time.sleep(60)

# -------------------------------------------------
# START WORKER ON BOOT
# -------------------------------------------------
def start_worker():
    t = threading.Thread(target=background_worker, daemon=True)
    t.start()

start_worker()

# -------------------------------------------------
# ENTRYPOINT LOCAL
# -------------------------------------------------
if __name__ == "__main__":
    with app.app_context():
        db.create_all()

    app.run(host="0.0.0.0", port=10000)
