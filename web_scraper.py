import requests
from bs4 import BeautifulSoup
import datetime
import pytz

BRAZIL_TZ = pytz.timezone("America/Sao_Paulo")

class FIFA25Scraper:

    BASE_URL = "https://football.esportsbattle.com"

    # ===========================
    #   Coletar página HTML
    # ===========================
    def fetch(self, url):
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
            }
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            return response.text
        except Exception as e:
            print(f"[SCRAPER] Erro ao carregar {url}: {e}")
            return None

    # ===========================
    #   Extrair dados de um card
    # ===========================
    def parse_match_card(self, card):
        try:
            match_id = card.get("data-id") or card.get("id") or None

            player_left = card.select_one(".player-left .player-name")
            player_right = card.select_one(".player-right .player-name")

            team_left = card.select_one(".team-left .team-name")
            team_right = card.select_one(".team-right .team-name")

            score_left = card.select_one(".score-left")
            score_right = card.select_one(".score-right")

            league = card.select_one(".match-event")
            stadium = card.select_one(".match-arena")
            datetime_el = card.select_one(".match-date")

            # Status do jogo (ex.: Live, Finished, Planned)
            status_el = card.select_one(".match-status")

            timestamp = None
            if datetime_el:
                try:
                    # Formato do site: "21.01 | 14:32"
                    raw = datetime_el.text.strip()
                    day, time_str = raw.split("|")
                    day = day.strip()
                    time_str = time_str.strip()

                    now_year = datetime.datetime.now().year
                    dt = datetime.datetime.strptime(f"{day}/{now_year} {time_str}", "%d.%m/%Y %H:%M")
                    timestamp = BRAZIL_TZ.localize(dt).isoformat()
                except:
                    pass

            return {
                "match_id": match_id,
                "player_left": player_left.text.strip() if player_left else None,
                "player_right": player_right.text.strip() if player_right else None,
                "team_left": team_left.text.strip() if team_left else None,
                "team_right": team_right.text.strip() if team_right else None,
                "goals_left": int(score_left.text.strip()) if score_left and score_left.text.strip().isdigit() else None,
                "goals_right": int(score_right.text.strip()) if score_right and score_right.text.strip().isdigit() else None,
                "league": league.text.strip() if league else None,
                "stadium": stadium.text.strip() if stadium else None,
                "timestamp": timestamp,
                "status": status_el.text.strip() if status_el else "Unknown",
            }

        except Exception as e:
            print(f"[SCRAPER] Erro ao parsear card: {e}")
            return None

    # ===========================
    #   Partidas AO VIVO
    # ===========================
    def get_live_matches(self):
        print("[SCRAPER] Buscando partidas ao vivo...")
        url = f"{self.BASE_URL}/football/live"
        html = self.fetch(url)
        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        cards = soup.select(".match-card")

        results = []
        for card in cards:
            parsed = self.parse_match_card(card)
            if parsed:
                results.append(parsed)

        print(f"[SCRAPER] Encontradas {len(results)} partidas AO VIVO")
        return results

    # ===========================
    #   Partidas RECENTES
    # ===========================
    def get_recent_matches(self):
        print("[SCRAPER] Buscando partidas recentes...")
        url = f"{self.BASE_URL}/football/recent"
        html = self.fetch(url)
        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        cards = soup.select(".match-card")

        results = []
        for card in cards:
            parsed = self.parse_match_card(card)
            if parsed:
                results.append(parsed)

        print(f"[SCRAPER] Encontradas {len(results)} partidas RECENTES")
        return results
