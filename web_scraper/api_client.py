import requests
from datetime import datetime, timedelta
import time
import logging
from functools import wraps

logger = logging.getLogger(__name__)

def retry_on_failure(max_retries=3, delay=2, backoff=2):
    """Decorator para retry automático com backoff exponencial"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            current_delay = delay
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except requests.exceptions.RequestException as e:
                    if attempt == max_retries - 1:
                        logger.error(f"❌ Falha após {max_retries} tentativas: {e}")
                        raise
                    
                    logger.warning(f"⚠️  Tentativa {attempt + 1}/{max_retries} falhou: {e}")
                    logger.warning(f"   Aguardando {current_delay}s antes de tentar novamente...")
                    time.sleep(current_delay)
                    current_delay *= backoff
                except Exception as e:
                    logger.error(f"❌ Erro inesperado: {e}")
                    raise
            
        return wrapper
    return decorator


class FIFA25APIClient:
    """Cliente para a API do Football Esports Battle"""
    
    BASE_URL = "https://football.esportsbattle.com/api"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://football.esportsbattle.com/',
            'Origin': 'https://football.esportsbattle.com'
        })
        
        self._locations_cache = None
        self._cache_time = None
        self._cache_duration = timedelta(minutes=5)
    
    @retry_on_failure(max_retries=3, delay=2)
    def get_locations(self, use_cache=True):
        """Busca todas as locations (estádios) disponíveis"""
        if use_cache and self._locations_cache is not None:
            if self._cache_time and datetime.now() - self._cache_time < self._cache_duration:
                logger.debug("📦 Usando cache de locations")
                return self._locations_cache
        
        try:
            url = f"{self.BASE_URL}/locations"
            logger.debug(f"🔗 GET {url}")
            
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            self._locations_cache = data
            self._cache_time = datetime.now()
            
            logger.info(f"✅ {len(data)} locations encontradas")
            return data
            
        except Exception as e:
            logger.error(f"❌ Erro ao buscar locations: {e}")
            return []
    
    @retry_on_failure(max_retries=3, delay=2)
    def get_tournament(self, tournament_id):
        """Busca dados de um torneio específico"""
        try:
            url = f"{self.BASE_URL}/tournaments/{tournament_id}"
            logger.debug(f"🔗 GET {url}")
            
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            # Verificar se é uma lista
            if isinstance(data, list) and len(data) > 0:
                data = data[0]
            
            # DEBUG: Log completo dos dados
            logger.debug(f"📦 Dados do torneio {tournament_id}: {data.keys() if isinstance(data, dict) else 'não é dict'}")
            
            return data
            
        except Exception as e:
            logger.error(f"❌ Erro ao buscar torneio {tournament_id}: {e}")
            return None
    
    def get_all_active_matches(self, delay_between_requests=0.5):
        """Coleta todas as partidas ativas de todos os torneios"""
        all_matches = []
        all_tournaments = []
        
        try:
            locations = self.get_locations()
            
            if not locations:
                logger.warning("⚠️  Nenhuma location encontrada")
                return all_matches, all_tournaments
            
            logger.info(f"📍 Encontradas {len(locations)} locations")
            
            # DEBUG: Mostrar detalhes de cada location
            for location in locations:
                location_name = location.get('token', 'Unknown')
                tournaments = location.get('tournaments', [])
                match_count = location.get('matchCount', 0)
                
                logger.info(f"   🏟️  {location_name}: {len(tournaments)} torneio(s), {match_count} partida(s)")
                
                # Se não há torneios, pular
                if not tournaments:
                    logger.debug(f"      ⚠️  Sem torneios ativos em {location_name}")
                    continue
                
                for tournament_id in tournaments:
                    if delay_between_requests > 0:
                        time.sleep(delay_between_requests)
                    
                    logger.info(f"      🔍 Buscando torneio {tournament_id}...")
                    
                    tournament_data = self.get_tournament(tournament_id)
                    
                    if not tournament_data:
                        logger.warning(f"      ⚠️  Torneio {tournament_id} não retornou dados")
                        continue
                    
                    # DEBUG: Verificar estrutura do torneio
                    if isinstance(tournament_data, dict):
                        logger.debug(f"      📊 Keys do torneio: {list(tournament_data.keys())}")
                        
                        # Verificar se tem matches
                        if 'matches' in tournament_data:
                            matches = tournament_data['matches']
                            logger.info(f"      ✅ Encontradas {len(matches)} partidas no torneio")
                        else:
                            logger.warning(f"      ⚠️  Torneio não tem key 'matches'")
                            logger.debug(f"      📦 Estrutura: {tournament_data}")
                            matches = []
                    else:
                        logger.warning(f"      ⚠️  tournament_data não é dict: {type(tournament_data)}")
                        continue
                    
                    all_tournaments.append(tournament_data)
                    
                    if not matches:
                        logger.debug(f"      ℹ️  Torneio {tournament_id}: sem partidas")
                        continue
                    
                    # Adicionar TODAS as partidas (não filtrar por status)
                    all_matches.extend(matches)
                    
                    active_count = len([m for m in matches if m.get('status_id') in [1, 2]])
                    finished_count = len([m for m in matches if m.get('status_id') == 3])
                    
                    logger.info(f"      ✅ Torneio {tournament_id}: {active_count} ativa(s), {finished_count} finalizada(s)")
            
            logger.info(f"\n📊 Total coletado: {len(all_matches)} partidas de {len(all_tournaments)} torneios")
            
            return all_matches, all_tournaments
            
        except Exception as e:
            logger.error(f"❌ Erro ao coletar partidas: {e}", exc_info=True)
            return all_matches, all_tournaments
    
    def close(self):
        """Fecha a sessão HTTP"""
        self.session.close()
        logger.debug("🔒 Sessão HTTP fechada")