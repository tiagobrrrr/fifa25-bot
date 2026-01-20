"""
Script de teste para debugar a API do ESportsBattle
"""

import requests
import json
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

BASE_URL = "https://football.esportsbattle.com/api"

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json',
    'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
    'Referer': 'https://football.esportsbattle.com/en/',
}

def test_endpoint(endpoint):
    """Testa um endpoint e mostra a estrutura dos dados"""
    url = f"{BASE_URL}{endpoint}"
    print(f"\n{'='*80}")
    print(f"Testando: {url}")
    print(f"{'='*80}")
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        # Salva resposta em arquivo
        filename = endpoint.replace('/', '_') + '.json'
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Status: {response.status_code}")
        print(f"💾 Salvo em: {filename}")
        
        # Analisa estrutura
        if isinstance(data, list):
            print(f"📊 Tipo: Lista com {len(data)} itens")
            if data:
                print(f"\n🔍 Estrutura do primeiro item:")
                print(json.dumps(data[0], indent=2, ensure_ascii=False))
        elif isinstance(data, dict):
            print(f"📊 Tipo: Dicionário")
            print(f"🔑 Chaves: {list(data.keys())}")
            
            if 'matches' in data:
                matches = data['matches']
                print(f"⚽ Total de partidas: {len(matches)}")
                if matches:
                    print(f"\n🔍 Estrutura da primeira partida:")
                    print(json.dumps(matches[0], indent=2, ensure_ascii=False))
            else:
                print(f"\n🔍 Estrutura completa:")
                print(json.dumps(data, indent=2, ensure_ascii=False)[:1000])
        
    except Exception as e:
        print(f"❌ Erro: {str(e)}")

if __name__ == "__main__":
    endpoints = [
        '/locations/streaming',
        '/locations/1/streaming',
        '/locations/2/streaming',
        '/nearest-matches'
    ]
    
    for endpoint in endpoints:
        test_endpoint(endpoint)
        print("\n")
    
    print("\n" + "="*80)
    print("✅ Teste completo! Verifique os arquivos JSON gerados.")
    print("="*80)