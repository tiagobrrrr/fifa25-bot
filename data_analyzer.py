class DataAnalyzer:

    # ===========================
    #   Estatísticas do dia
    # ===========================
    def get_daily_stats(self, matches):
        if not matches or len(matches) == 0:
            return None

        total = len(matches)
        wins = sum(1 for m in matches if m.get("win") is True)
        losses = sum(1 for m in matches if m.get("win") is False)
        goals_for = sum(m.get("goals") or 0 for m in matches)
        goals_against = sum(m.get("goals_against") or 0 for m in matches)

        return {
            "total": total,
            "wins": wins,
            "losses": losses,
            "goals_for": goals_for,
            "goals_against": goals_against,
        }

    # ===========================
    #   Estatísticas gerais
    # ===========================
    def analyze_list(self, matches):
        """
        Recebe uma lista de dicionários de partidas
        e retorna estatísticas consolidadas.
        """
        if not matches:
            return None
        
        stats = {}
        for m in matches:
            player = m.get("player")
            if player not in stats:
                stats[player] = {
                    "matches": 0,
                    "wins": 0,
                    "losses": 0,
                    "goals_for": 0,
                    "goals_against": 0,
                    "teams": {}
                }

            stats[player]["matches"] += 1
            stats[player]["goals_for"] += m.get("goals") or 0
            stats[player]["goals_against"] += m.get("goals_against") or 0

            if m.get("win") is True:
                stats[player]["wins"] += 1
            elif m.get("win") is False:
                stats[player]["losses"] += 1

            team = m.get("team")
            if team:
                if team not in stats[player]["teams"]:
                    stats[player]["teams"][team] = {
                        "games": 0,
                        "wins": 0,
                        "losses": 0
                    }
                stats[player]["teams"][team]["games"] += 1
                if m.get("win") is True:
                    stats[player]["teams"][team]["wins"] += 1
                elif m.get("win") is False:
                    stats[player]["teams"][team]["losses"] += 1

        return stats
