# -*- coding: utf-8 -*-
"""
Web Scraper Package
ESportsBattle FIFA25 Bot
"""

from .api_client import FIFA25APIClient, FIFA25Scraper
from .scraper_service import ScraperService

__version__ = '2.0.0'
__author__ = 'FIFA25 Bot Team'

__all__ = [
    'FIFA25APIClient',
    'FIFA25Scraper',
    'ScraperService'
]