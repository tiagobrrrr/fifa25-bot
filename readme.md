# 🎮 FIFA25 WebScraping Bot — Render 24/7

Bot completo para raspagem de partidas FIFA 25 do site  
**football.esportsbattle.com**, com:

- Scraper inteligente (BeautifulSoup + Requests)
- Dashboard Flask com monitoramento em tempo real
- Banco de dados (PostgreSQL ou SQLite)
- Worker em background rodando 24/7
- Envio de alertas por Telegram
- Geração de relatórios XLSX
- Deploy no Render usando Gunicorn + Flask

---

## 🚀 Estrutura do Projeto

fifa25-bot/
│── app.py
│── web_scraper.py
│── data_analyzer.py
│── telegram_service.py
│── email_service.py
│── models.py
│── requirements.txt
│── Procfile
│── runtime.txt
│── .gitignore
│
└── templates/
├── layout.html
├── dashboard.html
├── matches.html
├── players.html
└── reports.html

---

## 🔧 Variáveis de Ambiente Necessárias (Render)

Defina no painel do Render ➝ *Environment Variables*:

| Variável | Função |
|---------|---------|
| `DATABASE_URL` | URL do PostgreSQL (Render Managed DB) |
| `SESSION_SECRET` | Chave secreta do Flask |
| `SCAN_INTERVAL` | Intervalo do scraper (padrão: 30s) |
| `RUN_SCRAPER` | true/false para ativar ou desativar o scraping |
| `TELEGRAM_TOKEN` | Token do bot no Telegram |
| `TELEGRAM_CHAT_ID` | Chat ID para envio de alertas |
| `EMAIL_SMTP_SERVER` | Servidor SMTP |
| `EMAIL_SMTP_PORT` | Porta SMTP |
| `EMAIL_USER` | Usuário SMTP |
| `EMAIL_PASSWORD` | Senha SMTP |

> 💡 **Dica:** No Render, o PostgreSQL já cria automaticamente a variável `DATABASE_URL`.

---

## 📦 Como Instalar Localmente

pip install -r requirements.txt
python app.py

Acesse em:  
👉 http://localhost:5000

---

## 🚀 Como Fazer Deploy no Render

### 1️⃣ Criar repositório no GitHub  
Envie todos os arquivos do bot.

### 2️⃣ Criar Web Service no Render  
- New ➝ Web Service  
- Conectar GitHub  
- Escolher o repositório do bot  
- Build command:  
pip install -r requirements.txt
- Start command: deixe em branco (o Render usará o Procfile automaticamente)

### 3️⃣ Configurar variáveis de ambiente  
Incluindo as chaves de Telegram e SMTP (opcional).

### 4️⃣ Deploy  
O Render vai iniciar o bot Flask + background worker 24h/dia.

---

## 📊 Dashboard

O painel mostra:

- Partidas ao vivo  
- Partidas recentes  
- Partidas do dia  
- Estatísticas dos jogadores  
- Análises do dia  
- Último horário de varredura  
- Status do bot  

---

## 🤖 Sobre o Scraper

O scraper utiliza:

- `FIFA25Scraper.get_live_matches()`
- `FIFA25Scraper.get_recent_matches()`

E roda continuamente em *background*, com intervalo configurável:

SCAN_INTERVAL = 30

Em caso de erro:
- é registrado no log  
- bot envia notificação (se Telegram estiver ligado)

---

## 📥 Relatórios XLSX

O bot gera:

- Relatórios diários  
- Relatórios por faixa de datas  
- Envio por e-mail (SMTP)

Usa:

- pandas  
- openpyxl  

---

## 🛠 Tecnologias Utilizadas

- Python 3.10  
- Flask  
- SQLAlchemy  
- BeautifulSoup4  
- Requests  
- Pandas  
- Matplotlib  
- Gunicorn  
- PostgreSQL (Render)  

---

## ❤️ Criado para rodar 24/7 no Render, de forma estável, automática e escalável.
