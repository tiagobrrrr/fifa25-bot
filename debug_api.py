"""
Debug - Mostra a estrutura EXATA da API
"""

import requests
import json

BASE_URL = "https://football.esportsbattle.com/api"

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json',
    'Referer': 'https://football.esportsbattle.com/en/',
}

def debug_endpoint(endpoint_name, endpoint_path):
    """Debug de um endpoint específico"""
    url = f"{BASE_URL}{endpoint_path}"
    print(f"\n{'='*80}")
    print(f"🔍 ENDPOINT: {endpoint_name}")
    print(f"📍 URL: {url}")
    print(f"{'='*80}")
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        print(f"✅ Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            # Mostra tipo de resposta
            print(f"📦 Tipo: {type(data).__name__}")
            
            if isinstance(data, list):
                print(f"📊 Total de itens: {len(data)}")
                if data:
                    print(f"\n{'─'*80}")
                    print("🔎 PRIMEIRA PARTIDA (estrutura completa):")
                    print(f"{'─'*80}")
                    print(json.dumps(data[0], indent=2, ensure_ascii=False))
                    
                    # Analisa estrutura
                    print(f"\n{'─'*80}")
                    print("📋 CHAVES DISPONÍVEIS:")
                    print(f"{'─'*80}")
                    for key in data[0].keys():
                        value = data[0][key]
                        print(f"  • {key}: {type(value).__name__}")
                        if isinstance(value, dict):
                            print(f"    └─ Subchaves: {list(value.keys())}")
                    
                    # Tenta encontrar informações dos times/jogadores
                    print(f"\n{'─'*80}")
                    print("🎯 BUSCANDO INFORMAÇÕES DE TIMES/JOGADORES:")
                    print(f"{'─'*80}")
                    
                    match = data[0]
                    
                    # Possíveis localizações de dados
                    possible_keys = [
                        'homeTeam', 'awayTeam', 
                        'home_team', 'away_team',
                        'teams', 'participants',
                        'home', 'away',
                        'player1', 'player2'
                    ]
                    
                    for key in possible_keys:
                        if key in match:
                            print(f"✅ Encontrado: '{key}'")
                            print(json.dumps(match[key], indent=4, ensure_ascii=False))
                        else:
                            print(f"❌ Não encontrado: '{key}'")
            
            elif isinstance(data, dict):
                print(f"🔑 Chaves principais: {list(data.keys())}")
                
                if 'matches' in data:
                    matches = data['matches']
                    print(f"⚽ Total de partidas: {len(matches)}")
                    if matches:
                        print(f"\n{'─'*80}")
                        print("🔎 PRIMEIRA PARTIDA:")
                        print(f"{'─'*80}")
                        print(json.dumps(matches[0], indent=2, ensure_ascii=False))
                else:
                    print(f"\n{'─'*80}")
                    print("ESTRUTURA COMPLETA:")
                    print(f"{'─'*80}")
                    print(json.dumps(data, indent=2, ensure_ascii=False)[:2000])
        
        else:
            print(f"❌ Erro: {response.status_code}")
            print(f"Resposta: {response.text[:500]}")
    
    except Exception as e:
        print(f"❌ ERRO: {str(e)}")

if __name__ == "__main__":
    print("""
╔════════════════════════════════════════════════════════════════════════════╗
║                    DEBUG DA API - ESPORTSBATTLE                            ║
║                                                                            ║
║  Este script mostra a estrutura EXATA dos dados retornados pela API       ║
║  para identificar onde estão os nomes dos jogadores e times                ║
╚════════════════════════════════════════════════════════════════════════════╝
    """)
    
    endpoints = [
        ("STREAMING (Principal)", "/locations/streaming"),
        ("LOCATION 1", "/locations/1/streaming"),
        ("LOCATION 2", "/locations/2/streaming"),
    ]
    
    for name, path in endpoints:
        debug_endpoint(name, path)
    
    print(f"\n{'='*80}")
    print("✅ DEBUG COMPLETO")
    print("="*80)
    print("\n💡 Use os dados acima para ajustar o método _extract_match_data()")
    print("   no arquivo web_scraper/scraper.py\n")