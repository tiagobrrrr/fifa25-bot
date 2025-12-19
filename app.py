import os
import threading
import time
import logging
from datetime import datetime

from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.ext.automap import automap_base
from sqlalchemy.orm import scoped_session, sessionmaker

# -----------------------------------------------------------------------------
# CONFIG
# -----------------------------------------------------------------------------
DATABASE_URL = os.getenv("DATABASE_URL")

logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# -----------------------------------------------------------------------------
# AUTOMAP (REFLETE O BANCO REAL)
# -----------------------------------------------------------------------------
Base = automap_base()

with app.app_context():
    Base.prepare(db.engine, reflect=True)

# Ajuste os nomes conforme o que EXISTE no banco
Match = Base.classes.match if "match" in Base.classes else None
Player = Base.classes.player if "player" in Base.classes else None

# -----------------------------------------------------------------------------
# ROTAS
# -----------------------------------------------------------------------------
@app.route("/")
def dashboard():
    matches = []
    total_matches = 0
    total_players = 0

    if Match:
        matches = (
            db.session.query(Match)
            .order_by(Match.created_at.desc())
            .limit(50)
            .all()
        )
        total_matches = db.session.query(Match).count()

    if Player:
        total_players = db.session.query(Player).count()

    return render_template(
        "dashboard.html",
        matches=matches,
        total_matches=total_matches,
        total_players=total_players,
        last_scan=datetime.utcnow(),
    )


@app.route("/health")
def health():
    return {"status": "ok"}, 200


# -----------------------------------------------------------------------------
# WORKER EM BACKGROUND (SEGURO COM CONTEXTO)
# -----------------------------------------------------------------------------
def background_worker():
    logging.info("Worker iniciado")

    while True:
        try:
            with app.app_context():
                if Match:
                    count = db.session.query(Match).count()
                    logging.info(f"Status DB → Matches: {count}")
                if Player:
                    count_p = db.session.query(Player).count()
                    logging.info(f"Status DB → Players: {count_p}")

        except Exception as e:
            logging.error(f"Erro no worker: {e}")
            db.session.rollback()

        time.sleep(60)


# -----------------------------------------------------------------------------
# START
# -----------------------------------------------------------------------------
def start_worker():
    t = threading.Thread(target=background_worker, daemon=True)
    t.start()


start_worker()

# -----------------------------------------------------------------------------
# GUNICORN ENTRYPOINT
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
