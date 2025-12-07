import time
import logging
from bs4 import BeautifulSoup

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager


class StadiumScraper:

    def __init__(self, url="https://football.esportsbattle.com/en", wait_seconds=6):
        self.url = url
        self.wait_seconds = wait_seconds

    # ------------------------------------------------------------
    # Cria o driver corretamente (Render compatible)
    # ------------------------------------------------------------
    def _get_driver(self):
        opts = Options()
        opts.add_argument("--headless")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--window-size=1920,1080")

        service = Service(ChromeDriverManager().install())
        return webdriver.Chrome(service=service, options=opts)

    # ------------------------------------------------------------
    # Carrega página inteira
    # ------------------------------------------------------------
    def fetch_page(self):
        driver = self._get_driver()
        try:
            driver.get(self.url)
            time.sleep(self.wait_seconds)
            return driver.page_source
        except Exception as e:
            logging.error(f"[SCRAPER] Erro ao carregar página: {e}")
            return None
        finally:
            driver.quit()

    # ------------------------------------------------------------
    # Parser do HTML
    # ------------------------------------------------------------
    def parse(self, html):
        if not html:
            return {}, []

        soup = BeautifulSoup(html, "html.parser")

        matches = []
        locations_map = {}

        cards = soup.find_all("div", class_="event-card")

        for c in cards:
            try:
                stadium = c.find("div", class_="event-card__location").text.strip()
                time_str = c.find("div", class_="event-card__time").text.strip()
                player1 = c.find("div", class_="event-card__player1").text.strip()
                player2 = c.find("div", class_="event-card__player2").text.strip()

                match_obj = {
                    "stadium": stadium,
                    "time": time_str,
                    "player1": player1,
                    "player2": player2
                }

                matches.append(match_obj)

                if stadium not in locations_map:
                    locations_map[stadium] = []
                locations_map[stadium].append(match_obj)

            except Exception:
                continue

        return locations_map, matches
