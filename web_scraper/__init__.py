"""
FIFA25 Web Scraper Module
Módulo responsável por scraping de dados do Football Esports Battle
"""

from .api_client import FIFA25APIClient
from .scraper_service import ScraperService

__all__ = ['FIFA25APIClient', 'ScraperService']