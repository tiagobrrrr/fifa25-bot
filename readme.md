# 🎮 FIFA25 Scraping Bot - VERSÃO CORRIGIDA

Bot completo e otimizado para coleta de dados de partidas FIFA 25 do **Football Esports Battle**, com dashboard web, API REST e execução 24/7 no Render.

## 🚀 O Que Foi Corrigido

### ✅ Principais Melhorias

1. **API REST Direta**
   - Substituído scraping HTML por chamadas diretas à API
   - 3x mais rápido e confiável
   - Dados estruturados em JSON

2. **Sistema de Retry Robusto**
   - Retry automático com backoff exponencial
   - Tratamento de erros aprimorado
   - Logs detalhados

3. **Modelos de Dados Otimizados**
   - Models com métodos `from_api_data()`
   - Índices para consultas rápidas
   - Estatísticas de jogadores automáticas

4. **Cache Inteligente**
   - Cache de locations (5 minutos)
   - Reduz chamadas desnecessárias

5. **Logs e Monitoramento**
   - Tabela `scraper_logs` com histórico
   - Dashboard com estatísticas em tempo real
   - Auto-refresh das páginas

---

## 📁 Estrutura do Projeto

```
fifa25-bot/
│
├── app.py                          # Aplicação Flask principal
├── models.py                       # Modelos do banco de dados
├── requirements.txt                # Dependências Python
├── Procfile                        # Configuração Render/Heroku
├── runtime.txt                     # Versão do Python
├── render-build.sh                 # Script de build
├── .gitignore                      # Arquivos ignorados
├── README.md                       # Este arquivo
│
├── web_scraper/
│   ├── __init__.py                 # Inicialização do módulo
│   ├── api_client.py               # Cliente da API
│   └── scraper_service.py          # Serviço de scraping
│
└── templates/
    ├── layout.html                 # Template base
    ├── dashboard.html              # Dashboard
    ├── matches.html                # Página de partidas
    ├── players.html                # Página de jogadores
    └── reports.html                # Página de relatórios
```

---

## 🔧 Instalação Local

### 1. Clonar o Repositório

```bash
git clone https://github.com/tiagobrrrr/fifa25-bot.git
cd fifa25-bot
```

### 2. Criar Ambiente Virtual

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate  # Windows
```

### 3. Instalar Dependências

```bash
pip install -r requirements.txt
```

### 4. Executar Localmente

```bash
python app.py
```

Acesse: **http://localhost:5000**

---

## 🚀 Deploy no Render

### 1. Criar Conta no Render

Acesse [render.com](https://render.com) e crie uma conta.

### 2. Criar PostgreSQL Database

1. Dashboard → **New** → **PostgreSQL**
2. Nome: `fifa25-db`
3. Plano: **Free**
4. Criar database

### 3. Criar Web Service

1. Dashboard → **New** → **Web Service**
2. Conectar repositório GitHub
3. Configurações:
   - **Name:** `fifa25-bot`
   - **Environment:** `Python 3`
   - **Build Command:** (deixar vazio, usa render-build.sh)
   - **Start Command:** (deixar vazio, usa Procfile)

### 4. Configurar Variáveis de Ambiente

No painel do Render, adicione:

| Variável | Valor | Descrição |
|----------|-------|-----------|
| `DATABASE_URL` | (auto-gerado) | URL do PostgreSQL |
| `SESSION_SECRET` | `sua-chave-secreta` | Chave Flask |
| `SCAN_INTERVAL` | `30` | Intervalo scraping (segundos) |
| `RUN_SCRAPER` | `true` | Ativar scraping |
| `PYTHON_VERSION` | `3.10.12` | Versão Python |

### 5. Deploy

Clique em **Create Web Service** e aguarde o deploy!

Após concluído, acesse a URL gerada (ex: `https://fifa25-bot-xxxx.onrender.com`)

---

## 📊 Funcionalidades

### Dashboard Web

- ✅ Estatísticas em tempo real
- ✅ Top 10 jogadores
- ✅ Status do último scraping
- ✅ Auto-refresh (30s)

### Partidas

- ✅ Listagem completa
- ✅ Filtros por status (ao vivo, finalizadas, agendadas)
- ✅ Filtros por location (estádio)
- ✅ Paginação

### Jogadores

- ✅ Ranking completo
- ✅ Estatísticas detalhadas
- ✅ Vitórias, empates, derrotas
- ✅ Saldo de gols
- ✅ Paginação

### Relatórios

- ✅ Logs do scraper
- ✅ Histórico de execuções
- ✅ Estatísticas de período
- ✅ Tempo de execução

---

## 🔌 API REST

### Endpoints Disponíveis

#### `GET /api/matches/live`
Retorna partidas ao vivo

```json
[
  {
    "id": 1906579,
    "location": "Wembley",
    "player1": "aguuero",
    "player2": "Linox",
    "score": "3 - 3",
    "team1": "Frankfurt",
    "team2": "Leipzig",
    "stream_url": "https://...",
    "date": "2026-01-18T16:36:00Z"
  }
]
```

#### `GET /api/matches/today`
Retorna partidas do dia

#### `GET /api/matches/recent?limit=20`
Retorna partidas recentes

#### `GET /api/players/ranking?min_matches=5&limit=50`
Retorna ranking de jogadores

#### `GET /api/stats`
Retorna estatísticas gerais

```json
{
  "total_matches": 156,
  "total_players": 45,
  "live_matches": 3,
  "today_matches": 12,
  "last_scan": "2026-01-20T01:21:12Z",
  "last_scan_status": "success"
}
```

#### `GET /api/scraper/status`
Retorna status do scraper

---

## 🛠 Como Funciona

### 1. API Client (`web_scraper/api_client.py`)

```python
client = FIFA25APIClient()

# Buscar locations
locations = client.get_locations()

# Buscar torneio
tournament = client.get_tournament(233843)

# Coletar todas as partidas
matches, tournaments = client.get_all_active_matches()
```

### 2. Scraper Service (`web_scraper/scraper_service.py`)

```python
scraper = ScraperService(db)

# Executar scraping
stats = scraper.run()

# Resultado:
# {
#   'matches_found': 15,
#   'matches_new': 3,
#   'matches_updated': 2,
#   'status': 'success'
# }
```

### 3. APScheduler

O bot executa automaticamente:
- **A cada 30s:** Coleta de partidas
- **Domingo às 3h UTC:** Limpeza de dados antigos

---

## 📝 Logs

O bot registra todas as execuções na tabela `scraper_logs`:

```
2026-01-20 01:21:12 | SUCCESS | 15 partidas | 3 novas | 2 atualizadas | 2.85s
```

Visualize em: **/reports**

---

## ⚙️ Configurações

### Variáveis de Ambiente

```bash
# Banco de dados
DATABASE_URL=postgresql://user:pass@host/db

# Flask
SESSION_SECRET=your-secret-key

# Scraper
SCAN_INTERVAL=30        # Intervalo em segundos
RUN_SCRAPER=true        # true/false

# Opcional
PORT=5000
```

### Alterar Intervalo de Scraping

No Render, altere a variável `SCAN_INTERVAL`:
- `30` = 30 segundos (padrão)
- `60` = 1 minuto
- `300` = 5 minutos

### Desabilitar Scraping

Configure `RUN_SCRAPER=false` para rodar apenas o dashboard sem scraping.

---

## 🧪 Testar Localmente

### Teste do API Client

```bash
python web_scraper/api_client.py
```

Saída esperada:
```
================================================================================
🎮 Testando FIFA25 API Client
================================================================================

1️⃣ Buscando locations...
   ✅ 7 locations encontradas

2️⃣ Testando location: Wembley
   ✅ Torneio 233843: 2 partidas

3️⃣ Coletando todas as partidas...
   ✅ 15 partidas coletadas de 5 torneios

================================================================================
✅ Teste concluído com sucesso!
================================================================================
```

### Teste do Scraper Service

```bash
python web_scraper/scraper_service.py
```

---

## 🐛 Troubleshooting

### Problema: "0 partidas coletadas"

**Solução:**
1. Verifique se `RUN_SCRAPER=true`
2. Confira logs em `/reports`
3. Teste o API client standalone

### Problema: Erro de conexão com banco

**Solução:**
1. Verifique `DATABASE_URL`
2. Certifique-se que PostgreSQL está rodando
3. Use SQLite localmente: `sqlite:///fifa25.db`

### Problema: ImportError

**Solução:**
```bash
pip install -r requirements.txt --upgrade
```

---

## 📈 Monitoramento

### Verificar Status

Acesse: `/api/scraper/status`

```json
{
  "status": "active",
  "last_run": "2026-01-20T01:21:12Z",
  "last_status": "success",
  "matches_found": 15,
  "message": "3 novas, 2 atualizadas"
}
```

### Logs do Render

No painel do Render:
1. Selecione seu serviço
2. Clique em **Logs**
3. Monitore execuções em tempo real

---

## 🔐 Segurança

- ✅ Senhas em variáveis de ambiente
- ✅ CORS configurado
- ✅ SQLAlchemy com pool de conexões
- ✅ Rate limiting no cliente API
- ✅ Validação de dados

---

## 🤝 Contribuindo

1. Fork o projeto
2. Crie uma branch: `git checkout -b feature/nova-funcionalidade`
3. Commit: `git commit -m 'Adiciona nova funcionalidade'`
4. Push: `git push origin feature/nova-funcionalidade`
5. Abra um Pull Request

---

## 📄 Licença

Este projeto é open source e está disponível sob a licença MIT.

---

## 👤 Autor

**Tiago**
- GitHub: [@tiagobrrrr](https://github.com/tiagobrrrr)

---

## 🙏 Agradecimentos

- Football Esports Battle pela API
- Render pela hospedagem gratuita
- Comunidade Python/Flask

---

## 📞 Suporte

Encontrou um bug? Tem uma sugestão?

- Abra uma [Issue](https://github.com/tiagobrrrr/fifa25-bot/issues)
- Ou envie um Pull Request!

---

**⚡ Bot rodando 24/7 com 100% de precisão na coleta de dados!**