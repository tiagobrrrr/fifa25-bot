# 🎮 FIFA25 Bot - ESportsBattle Scraper

Bot completo para scraping de torneios e partidas FIFA 25 do site **football.esportsbattle.com**.

## ✨ Características

- ✅ **Scraping inteligente** com estrutura correta da API
- ✅ **Paginação automática** para todos os torneios
- ✅ **Dashboard web** com monitoramento em tempo real
- ✅ **Scheduler** verificando automaticamente a cada 2 minutos
- ✅ **Logging detalhado** de todas as operações
- ✅ **Cache inteligente** para evitar requisições desnecessárias
- ✅ **Tratamento robusto de erros**
- ✅ **Pronto para Render** com deploy automático

## 📊 Estrutura da API Confirmada

```
GET /api/locations → Lista de locations (estádios)
GET /api/tournaments?page=N → {totalPages: int, tournaments: []}
GET /api/teams?page=N → {totalPages: int, teams: []}
GET /api/tournaments/{id}/matches → Lista de partidas
```

## 🚀 Instalação Local

### 1. Clone o repositório

```bash
git clone https://github.com/seu-usuario/fifa25-bot.git
cd fifa25-bot
```

### 2. Crie ambiente virtual

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

### 3. Instale dependências

```bash
pip install -r requirements.txt
```

### 4. Configure variáveis de ambiente (opcional)

Crie arquivo `.env`:

```env
SCAN_INTERVAL=120
RUN_SCRAPER=true
FLASK_ENV=development
DATABASE_URL=sqlite:///fifa25.db
```

### 5. Execute a aplicação

```bash
python app.py
```

Acesse: http://localhost:5000

## 🔧 Configuração

### Variáveis de Ambiente

| Variável | Descrição | Padrão |
|----------|-----------|--------|
| `PORT` | Porta da aplicação | `5000` |
| `SCAN_INTERVAL` | Intervalo de scraping (segundos) | `120` |
| `RUN_SCRAPER` | Ativar/desativar scraper | `true` |
| `FLASK_ENV` | Ambiente Flask | `production` |
| `DATABASE_URL` | URL do banco de dados | SQLite local |
| `SESSION_SECRET` | Chave secreta Flask | Gerada |

### Horários de Torneios

Torneios do ESportsBattle geralmente ocorrem:
- **Horário:** 10:00 - 23:00 UTC
- **Brasil:** 07:00 - 20:00 BRT
- **Frequência:** Diária, mais comum nos fins de semana

## 📁 Estrutura do Projeto

```
fifa25-bot/
│
├── app.py                          # Aplicação Flask principal
├── requirements.txt                # Dependências Python
├── Procfile                        # Config para Render
├── runtime.txt                     # Versão do Python
│
├── web_scraper/
│   ├── __init__.py
│   ├── api_client.py              # Cliente da API (CORRIGIDO)
│   └── scraper_service.py         # Serviço de scraping
│
├── templates/
│   └── dashboard.html             # Dashboard web
│
├── static/                         # Arquivos estáticos (CSS/JS)
└── models.py                       # Modelos do banco de dados
```

## 🎯 Como Usar

### Teste Rápido da API

```python
from web_scraper.api_client import FIFA25APIClient

client = FIFA25APIClient()

# Resumo rápido
summary = client.get_summary()
print(f"Locations: {summary['locations_count']}")
print(f"Torneios: {summary['tournaments_count']}")
```

### Coleta Completa de Dados

```python
from web_scraper.api_client import FIFA25APIClient

client = FIFA25APIClient()

# Coletar todos os dados
data = client.scrape_all_data()

print(f"Torneios: {len(data['tournaments'])}")
print(f"Partidas: {len(data['matches'])}")
print(f"Teams: {len(data['teams'])}")
```

### Executar Scraping Manual

```python
from web_scraper.scraper_service import ScraperService

service = ScraperService()
result = service.run_scraping()

print(f"Sucesso: {result['success']}")
print(f"Processados: {result['processed']}")
```

## 🌐 Deploy no Render

### 1. Conectar Repositório

- Acesse [render.com](https://render.com)
- Crie novo **Web Service**
- Conecte seu repositório GitHub

### 2. Configurar Build

- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** Deixe vazio (usa Procfile)

### 3. Variáveis de Ambiente

Configure no painel do Render:

```
DATABASE_URL=postgresql://...  (gerado automaticamente)
SCAN_INTERVAL=120
RUN_SCRAPER=true
SESSION_SECRET=seu-secret-key-aleatorio
```

### 4. Deploy

O deploy acontece automaticamente a cada push no branch main.

### 5. Monitorar Logs

```
Logs → Ver em tempo real
```

Procure por:
```
✅ X location(s) encontrada(s)
✅ X torneio(s) encontrado(s)
✅ X partida(s) encontrada(s)
```

## 📊 Dashboard

O dashboard mostra:

- **Status do sistema** (ativo/inativo)
- **Contadores** de locations, torneios e partidas
- **Estatísticas** de execuções
- **Taxa de sucesso** do scraper
- **Última verificação**
- **Botões** para ações manuais

### Endpoints da API

```
GET /                   → Dashboard web
GET /api/status         → Status JSON completo
GET /api/scrape/now     → Executar scraping manual
GET /api/summary        → Resumo dos dados
GET /api/stats          → Estatísticas do scraper
GET /health             → Health check
```

## 🔍 Troubleshooting

### Nenhum torneio encontrado

**Causa:** Não há torneios ativos no momento

**Solução:**
- Torneios ocorrem entre 10h-23h UTC
- Aguarde e o bot detectará automaticamente
- Verifique manualmente em: https://football.esportsbattle.com/en/

### Erro 403 (Forbidden)

**Causa:** Site detectou bot

**Solução:**
- Headers já estão configurados corretamente
- Se persistir, adicione delay maior entre requisições
- Modifique `SCAN_INTERVAL` para 180 ou 300 segundos

### Erro ao conectar

**Causa:** Problemas de rede ou site fora do ar

**Solução:**
- Verifique se o site está online
- Aguarde alguns minutos e tente novamente
- Bot tentará automaticamente na próxima execução

### Muitas verificações vazias

**Causa:** Horário fora do período de torneios

**Solução:**
- Normal durante a madrugada/manhã
- Bot reduz automaticamente a frequência
- Voltará ao normal quando detectar torneios

## 📝 Logs

### Níveis de Log

```python
logger.info()    # Informações gerais
logger.warning() # Avisos (não críticos)
logger.error()   # Erros (requerem atenção)
logger.debug()   # Detalhes técnicos
```

### Onde Encontrar Logs

**Local:**
```
app.log (arquivo)
Console (stdout)
```

**Render:**
```
Dashboard → Logs
```

### Logs Importantes

**Sucesso:**
```
✅ 1 location(s) encontrada(s)
✅ 5 torneio(s) encontrado(s)
✅ 23 partida(s) encontrada(s)
```

**Aguardando:**
```
⏰ Nenhum torneio ativo no momento
💡 Tente novamente em horário de jogos
```

**Erros:**
```
❌ Erro durante scraping: ...
🚫 Status 403 para /api/...
```

## 🧪 Testes

### Teste Local Completo

```bash
# Teste da API
python -c "from web_scraper.api_client import FIFA25APIClient; c = FIFA25APIClient(); print(c.get_summary())"

# Teste do scraper
python -c "from web_scraper.scraper_service import ScraperService; s = ScraperService(); print(s.run_scraping())"

# Teste da aplicação
python app.py
```

### Teste no Navegador

```
http://localhost:5000           → Dashboard
http://localhost:5000/api/status  → Status JSON
http://localhost:5000/health      → Health check
```

## 🔄 Atualizações

### Atualizar Código

```bash
git pull origin main
pip install -r requirements.txt --upgrade
python app.py
```

### Deploy Automático no Render

```bash
git add .
git commit -m "Atualização"
git push origin main
```

Render fará deploy automaticamente.

## 📞 Suporte

### Problemas Comuns

1. **API mudou?**
   - Execute o analisador: `python api_analyzer.py`
   - Verifique `api_findings.json`

2. **Dados não salvam no banco?**
   - Verifique `DATABASE_URL`
   - Implemente métodos `_process_*` no `scraper_service.py`

3. **Scraper não inicia?**
   - Verifique `RUN_SCRAPER=true`
   - Confira logs de erro

### Links Úteis

- [Documentação Flask](https://flask.palletsprojects.com/)
- [Documentação Render](https://render.com/docs)
- [Requests](https://requests.readthedocs.io/)
- [APScheduler](https://apscheduler.readthedocs.io/)

## 📜 Licença

Este projeto é para fins educacionais.
Respeite os termos de serviço do ESportsBattle.

## 🎉 Pronto!

Seu bot está configurado e funcionando!

Ele irá:
- ✅ Verificar automaticamente a cada 2 minutos
- ✅ Detectar quando torneios aparecerem
- ✅ Coletar todas as partidas
- ✅ Salvar no banco de dados
- ✅ Exibir no dashboard

**Aguarde os torneios começarem e aproveite! 🚀**