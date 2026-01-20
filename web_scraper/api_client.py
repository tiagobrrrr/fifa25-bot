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
                    current_delay *= backoff  # Backoff exponencial
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
        
        # Cache para locations (5 minutos)
        self._locations_cache = None
        self._cache_time = None
        self._cache_duration = timedelta(minutes=5)
    
    @retry_on_failure(max_retries=3, delay=2)
    def get_locations(self, use_cache=True):
        """
        Busca todas as locations (estádios) disponíveis
        
        Returns:
            list: Lista de dicionários com dados das locations
        """
        # Verificar cache
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
            
            # Atualizar cache
            self._locations_cache = data
            self._cache_time = datetime.now()
            
            logger.info(f"✅ {len(data)} locations encontradas")
            return data
            
        except requests.exceptions.Timeout:
            logger.error("❌ Timeout ao buscar locations")
            return []
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Erro HTTP ao buscar locations: {e}")
            return []
        except Exception as e:
            logger.error(f"❌ Erro inesperado ao buscar locations: {e}")
            return []
    
    @retry_on_failure(max_retries=3, delay=2)
    def get_tournament(self, tournament_id):
        """
        Busca dados de um torneio específico
        
        Args:
            tournament_id (int): ID do torneio
            
        Returns:
            dict: Dados do torneio incluindo partidas
        """
        try:
            url = f"{self.BASE_URL}/tournaments/{tournament_id}"
            logger.debug(f"🔗 GET {url}")
            
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            # Verificar se é uma lista (formato antigo da API)
            if isinstance(data, list) and len(data) > 0:
                data = data[0]
            
            return data
            
        except requests.exceptions.Timeout:
            logger.error(f"❌ Timeout ao buscar torneio {tournament_id}")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Erro HTTP ao buscar torneio {tournament_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Erro inesperado ao buscar torneio {tournament_id}: {e}")
            return None
    
    @retry_on_failure(max_retries=3, delay=2)
    def get_tournament_results(self, tournament_id):
        """
        Busca resultados/classificação de um torneio
        
        Args:
            tournament_id (int): ID do torneio
            
        Returns:
            dict: Dados de resultados e classificação
        """
        try:
            url = f"{self.BASE_URL}/tournaments/{tournament_id}/results"
            logger.debug(f"🔗 GET {url}")
            
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            return response.json()
            
        except requests.exceptions.Timeout:
            logger.error(f"❌ Timeout ao buscar resultados do torneio {tournament_id}")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Erro HTTP ao buscar resultados: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Erro inesperado ao buscar resultados: {e}")
            return None
    
    def get_all_active_matches(self, delay_between_requests=0.5):
        """
        Coleta todas as partidas ativas de todos os torneios
        
        Args:
            delay_between_requests (float): Delay em segundos entre requisições
            
        Returns:
            list: Lista de partidas ativas
        """
        all_matches = []
        all_tournaments = []
        
        try:
            # 1. Buscar todas as locations
            locations = self.get_locations()
            
            if not locations:
                logger.warning("⚠️  Nenhuma location encontrada")
                return all_matches, all_tournaments
            
            logger.info(f"📍 Encontradas {len(locations)} locations")
            
            # 2. Para cada location, buscar seus torneios
            for location in locations:
                location_name = location.get('token', 'Unknown')
                tournaments = location.get('tournaments', [])
                match_count = location.get('matchCount', 0)
                
                if not tournaments:
                    logger.debug(f"   🏟️  {location_name}: sem torneios ativos")
                    continue
                
                logger.info(f"   🏟️  {location_name}: {len(tournaments)} torneio(s), {match_count} partida(s)")
                
                for tournament_id in tournaments:
                    # Delay para não sobrecarregar a API
                    if delay_between_requests > 0:
                        time.sleep(delay_between_requests)
                    
                    logger.debug(f"      🔍 Buscando torneio {tournament_id}...")
                    
                    # Buscar dados do torneio
                    tournament_data = self.get_tournament(tournament_id)
                    
                    if not tournament_data:
                        logger.warning(f"      ⚠️  Torneio {tournament_id} não retornou dados")
                        continue
                    
                    # Adicionar torneio à lista
                    all_tournaments.append(tournament_data)
                    
                    # Extrair partidas
                    matches = tournament_data.get('matches', [])
                    
                    if not matches:
                        logger.debug(f"      ℹ️  Torneio {tournament_id}: sem partidas")
                        continue
                    
                    # Filtrar apenas partidas ativas ou agendadas (status_id = 1 ou 2)
                    active_matches = [
                        m for m in matches 
                        if m.get('status_id') in [1, 2]
                    ]
                    
                    finished_matches = [
                        m for m in matches
                        if m.get('status_id') == 3
                    ]
                    
                    # Adicionar todas as partidas (ativas e finalizadas)
                    all_matches.extend(matches)
                    
                    logger.info(f"      ✅ Torneio {tournament_id}: {len(active_matches)} ativa(s), {len(finished_matches)} finalizada(s)")
            
            logger.info(f"\n📊 Total coletado: {len(all_matches)} partidas de {len(all_tournaments)} torneios")
            
            return all_matches, all_tournaments
            
        except Exception as e:
            logger.error(f"❌ Erro ao coletar partidas: {e}", exc_info=True)
            return all_matches, all_tournaments
    
    def close(self):
        """Fecha a sessão HTTP"""
        self.session.close()
        logger.debug("🔒 Sessão HTTP fechada")


# Teste standalone
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("=" * 80)
    print("🎮 Testando FIFA25 API Client")
    print("=" * 80)
    
    client = FIFA25APIClient()
    
    try:
        # Testar locations
        print("\n1️⃣ Buscando locations...")
        locations = client.get_locations()
        print(f"   ✅ {len(locations)} locations encontradas\n")
        
        # Testar torneios
        if locations:
            for loc in locations[:3]:  # Apenas primeiras 3
                tournaments = loc.get('tournaments', [])
                if tournaments:
                    print(f"\n2️⃣ Testando location: {loc.get('token')}")
                    tournament_id = tournaments[0]
                    tournament = client.get_tournament(tournament_id)
                    
                    if tournament:
                        matches = tournament.get('matches', [])
                        print(f"   ✅ Torneio {tournament_id}: {len(matches)} partidas")
                    
                    break
        
        # Testar coleta completa
        print("\n3️⃣ Coletando todas as partidas...")
        matches, tournaments = client.get_all_active_matches()
        print(f"   ✅ {len(matches)} partidas coletadas de {len(tournaments)} torneios")
        
        print("\n" + "=" * 80)
        print("✅ Teste concluído com sucesso!")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ Erro no teste: {e}")
    finally:
        client.close()