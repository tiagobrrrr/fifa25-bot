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
        self._cache_duration = timedelta(minutes=2)  # Cache menor (2 min)
    
    @retry_on_failure(max_retries=3, delay=2)
    def get_locations(self, use_cache=True):
        """Busca todas as locations (estádios) disponíveis"""
        if use_cache and self._locations_cache is not None:
            if self._cache_time and datetime.now() - self._cache_time < self._cache_duration:
                logger.debug("📦 Usando cache de locations")
                return self._locations_cache
        
        try:
            url = f"{self.BASE_URL}/locations"
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
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if isinstance(data, list) and len(data) > 0:
                data = data[0]
            
            return data
            
        except Exception as e:
            logger.error(f"❌ Erro ao buscar torneio {tournament_id}: {e}")
            return None
    
    def scan_recent_tournament_ids(self, start_id=233800, count=200):
        """
        Escaneia IDs de torneios recentes para encontrar partidas
        Útil quando a API /locations não retorna torneios ativos
        """
        logger.info(f"🔍 Escaneando torneios de {start_id} até {start_id + count}...")
        
        found_tournaments = []
        
        for tournament_id in range(start_id, start_id + count):
            try:
                time.sleep(0.3)  # Rate limiting
                
                tournament = self.get_tournament(tournament_id)
                
                if tournament and isinstance(tournament, dict):
                    matches = tournament.get('matches', [])
                    
                    if matches:
                        # Verificar se há partidas ativas ou finalizadas recentemente
                        active_matches = [m for m in matches if m.get('status_id') in [1, 2]]
                        recent_finished = [m for m in matches if m.get('status_id') == 3]
                        
                        if active_matches or recent_finished:
                            found_tournaments.append(tournament)
                            logger.info(f"   ✅ Torneio {tournament_id}: {len(active_matches)} ativas, {len(recent_finished)} finalizadas")
                
                # Log a cada 20 torneios
                if (tournament_id - start_id) % 20 == 0:
                    logger.debug(f"   📊 Escaneados {tournament_id - start_id}/{count} torneios...")
                    
            except Exception as e:
                logger.debug(f"   ⚠️  Erro ao escanear torneio {tournament_id}: {e}")
                continue
        
        logger.info(f"🎯 Escaneamento completo: {len(found_tournaments)} torneios com partidas encontrados")
        return found_tournaments
    
    def get_all_active_matches(self, delay_between_requests=0.5, fallback_scan=True):
        """
        Coleta todas as partidas ativas de todos os torneios
        
        Args:
            delay_between_requests: Delay entre requisições
            fallback_scan: Se True, faz scan de IDs quando locations não retornam torneios
        """
        all_matches = []
        all_tournaments = []
        
        try:
            # MÉTODO 1: Buscar via locations (método oficial)
            locations = self.get_locations(use_cache=False)  # Sempre buscar fresh
            
            if not locations:
                logger.warning("⚠️  Nenhuma location encontrada")
                return all_matches, all_tournaments
            
            logger.info(f"📍 Encontradas {len(locations)} locations")
            
            has_active_tournaments = False
            
            for location in locations:
                location_name = location.get('token', 'Unknown')
                tournaments = location.get('tournaments', [])
                match_count = location.get('matchCount', 0)
                
                logger.info(f"   🏟️  {location_name}: {len(tournaments)} torneio(s), {match_count} partida(s)")
                
                if tournaments:
                    has_active_tournaments = True
                    
                    for tournament_id in tournaments:
                        if delay_between_requests > 0:
                            time.sleep(delay_between_requests)
                        
                        logger.info(f"      🔍 Buscando torneio {tournament_id}...")
                        
                        tournament_data = self.get_tournament(tournament_id)
                        
                        if not tournament_data:
                            continue
                        
                        matches = tournament_data.get('matches', [])
                        
                        if matches:
                            all_tournaments.append(tournament_data)
                            all_matches.extend(matches)
                            
                            active = len([m for m in matches if m.get('status_id') in [1, 2]])
                            finished = len([m for m in matches if m.get('status_id') == 3])
                            
                            logger.info(f"      ✅ {len(matches)} partidas: {active} ativas, {finished} finalizadas")
            
            # MÉTODO 2: Fallback - escanear IDs de torneios recentes
            if not has_active_tournaments and fallback_scan:
                logger.warning("⚠️  Nenhum torneio retornado por locations, ativando scan de IDs...")
                
                # Calcular ID base (torneios são criados diariamente)
                # Estimativa: ~50-100 torneios por dia, IDs sequenciais
                base_id = 233900  # Ajuste conforme necessário
                
                found_tournaments = self.scan_recent_tournament_ids(
                    start_id=base_id,
                    count=100  # Escanear últimos 100 IDs
                )
                
                if found_tournaments:
                    all_tournaments.extend(found_tournaments)
                    
                    for tournament in found_tournaments:
                        matches = tournament.get('matches', [])
                        all_matches.extend(matches)
                else:
                    logger.warning("⚠️  Scan de IDs não encontrou torneios com partidas")
            
            logger.info(f"\n📊 Total coletado: {len(all_matches)} partidas de {len(all_tournaments)} torneios")
            
            return all_matches, all_tournaments
            
        except Exception as e:
            logger.error(f"❌ Erro ao coletar partidas: {e}", exc_info=True)
            return all_matches, all_tournaments
    
    def close(self):
        """Fecha a sessão HTTP"""
        self.session.close()
        logger.debug("🔒 Sessão HTTP fechada")