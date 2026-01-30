"""
Serviço de Email - FIFA 25 Bot
Envio de emails com relatórios
"""

import os
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from typing import List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class EmailService:
    """Serviço para envio de emails"""
    
    def __init__(self):
        self.smtp_server = os.environ.get('EMAIL_SMTP_SERVER', 'smtp.gmail.com')
        self.smtp_port = int(os.environ.get('EMAIL_SMTP_PORT', 587))
        self.user = os.environ.get('EMAIL_USER')
        self.password = os.environ.get('EMAIL_PASSWORD')
        self.enabled = bool(self.user and self.password)
        
        if self.enabled:
            logger.info(f"✅ Email Service ativado ({self.smtp_server}:{self.smtp_port})")
        else:
            logger.warning("⚠️ Email Service desativado (configure EMAIL_USER e EMAIL_PASSWORD)")
    
    def send_email(
        self,
        to_address: str,
        subject: str,
        body: str,
        html: bool = False,
        attachments: List[str] = None
    ) -> bool:
        """
        Envia um email
        
        Args:
            to_address: Email do destinatário
            subject: Assunto
            body: Corpo do email
            html: Se True, body é HTML, senão é texto plano
            attachments: Lista de caminhos de arquivos para anexar
        
        Returns:
            True se enviado com sucesso
        """
        if not self.enabled:
            logger.debug("Email desabilitado, mensagem não enviada")
            return False
        
        try:
            # Criar mensagem
            msg = MIMEMultipart()
            msg['From'] = self.user
            msg['To'] = to_address
            msg['Subject'] = subject
            msg['Date'] = datetime.now().strftime('%a, %d %b %Y %H:%M:%S %z')
            
            # Adicionar corpo
            if html:
                msg.attach(MIMEText(body, 'html'))
            else:
                msg.attach(MIMEText(body, 'plain'))
            
            # Adicionar anexos
            if attachments:
                for file_path in attachments:
                    try:
                        with open(file_path, 'rb') as f:
                            part = MIMEBase('application', 'octet-stream')
                            part.set_payload(f.read())
                            encoders.encode_base64(part)
                            
                            filename = os.path.basename(file_path)
                            part.add_header(
                                'Content-Disposition',
                                f'attachment; filename= {filename}'
                            )
                            msg.attach(part)
                    except Exception as e:
                        logger.error(f"❌ Erro ao anexar arquivo {file_path}: {e}")
            
            # Conectar e enviar
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(self.user, self.password)
                server.send_message(msg)
            
            logger.info(f"✅ Email enviado para {to_address}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro ao enviar email: {e}")
            return False
    
    def send_daily_report(
        self,
        to_address: str,
        report_data: dict,
        attachment_path: Optional[str] = None
    ) -> bool:
        """
        Envia relatório diário
        
        Args:
            to_address: Email do destinatário
            report_data: Dados do relatório
            attachment_path: Caminho do arquivo Excel (opcional)
        
        Returns:
            True se enviado com sucesso
        """
        try:
            subject = f"FIFA 25 Bot - Relatório Diário {datetime.now().strftime('%Y-%m-%d')}"
            
            # Corpo HTML
            html_body = self._format_daily_report_html(report_data)
            
            # Anexos
            attachments = [attachment_path] if attachment_path else None
            
            return self.send_email(
                to_address=to_address,
                subject=subject,
                body=html_body,
                html=True,
                attachments=attachments
            )
            
        except Exception as e:
            logger.error(f"❌ Erro ao enviar relatório diário: {e}")
            return False
    
    def _format_daily_report_html(self, report_data: dict) -> str:
        """Formata relatório diário em HTML"""
        total_matches = report_data.get('total_matches', 0)
        live_matches = report_data.get('live_matches', 0)
        finished_matches = report_data.get('finished_matches', 0)
        unique_players = report_data.get('unique_players', 0)
        
        top_players = report_data.get('top_players', [])
        top_teams = report_data.get('top_teams', [])
        
        # Gerar lista de top players
        players_html = ""
        for i, player in enumerate(top_players[:5], 1):
            nickname = player.get('nickname', 'Unknown')
            matches = player.get('matches', 0)
            players_html += f"<li>{i}. {nickname} - {matches} partidas</li>\n"
        
        # Gerar lista de top teams
        teams_html = ""
        for i, team in enumerate(top_teams[:5], 1):
            name = team.get('name', 'Unknown')
            count = team.get('count', 0)
            teams_html += f"<li>{i}. {name} - {count} usos</li>\n"
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{
            font-family: Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }}
        .header {{
            background-color: #4CAF50;
            color: white;
            padding: 20px;
            text-align: center;
            border-radius: 5px;
        }}
        .stats {{
            background-color: #f4f4f4;
            padding: 15px;
            margin: 20px 0;
            border-radius: 5px;
        }}
        .stat-item {{
            display: flex;
            justify-content: space-between;
            padding: 10px 0;
            border-bottom: 1px solid #ddd;
        }}
        .stat-item:last-child {{
            border-bottom: none;
        }}
        .section {{
            margin: 20px 0;
        }}
        .section h2 {{
            color: #4CAF50;
            border-bottom: 2px solid #4CAF50;
            padding-bottom: 10px;
        }}
        ul {{
            list-style-type: none;
            padding-left: 0;
        }}
        li {{
            padding: 5px 0;
        }}
        .footer {{
            text-align: center;
            color: #666;
            font-size: 12px;
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #ddd;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🎮 FIFA 25 Bot</h1>
        <p>Relatório Diário - {datetime.now().strftime('%d/%m/%Y')}</p>
    </div>
    
    <div class="stats">
        <div class="stat-item">
            <strong>📊 Total de Partidas:</strong>
            <span>{total_matches}</span>
        </div>
        <div class="stat-item">
            <strong>🔴 Ao Vivo:</strong>
            <span>{live_matches}</span>
        </div>
        <div class="stat-item">
            <strong>✅ Finalizadas:</strong>
            <span>{finished_matches}</span>
        </div>
        <div class="stat-item">
            <strong>👥 Jogadores Únicos:</strong>
            <span>{unique_players}</span>
        </div>
    </div>
    
    <div class="section">
        <h2>🏆 Top 5 Jogadores</h2>
        <ul>
            {players_html}
        </ul>
    </div>
    
    <div class="section">
        <h2>⚽ Top 5 Times</h2>
        <ul>
            {teams_html}
        </ul>
    </div>
    
    <div class="footer">
        <p>Este é um relatório automático gerado pelo FIFA 25 Bot</p>
        <p>© 2026 ESportsBattle Monitor</p>
    </div>
</body>
</html>
"""
        return html
    
    def send_error_notification(self, to_address: str, error_message: str) -> bool:
        """
        Envia notificação de erro
        
        Args:
            to_address: Email do destinatário
            error_message: Mensagem de erro
        
        Returns:
            True se enviado com sucesso
        """
        try:
            subject = "⚠️ FIFA 25 Bot - Erro Detectado"
            
            body = f"""
Alerta de Erro - FIFA 25 Bot

Um erro foi detectado no sistema:

{error_message}

Data/Hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Por favor, verifique os logs do sistema.

---
Este é um alerta automático do FIFA 25 Bot
"""
            
            return self.send_email(
                to_address=to_address,
                subject=subject,
                body=body,
                html=False
            )
            
        except Exception as e:
            logger.error(f"❌ Erro ao enviar notificação de erro: {e}")
            return False
    
    def test_connection(self) -> bool:
        """
        Testa a conexão SMTP
        
        Returns:
            True se conectado com sucesso
        """
        if not self.enabled:
            logger.warning("Email não configurado")
            return False
        
        try:
            with smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=5) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(self.user, self.password)
            
            logger.info("✅ Conexão SMTP estabelecida com sucesso")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro ao testar conexão SMTP: {e}")
            return False


# Teste standalone
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    email_service = EmailService()
    
    if email_service.enabled:
        print("\n🧪 Testando Email Service...\n")
        
        # Teste 1: Conexão
        print("1️⃣ Testando conexão SMTP...")
        if email_service.test_connection():
            print("✅ Conexão OK\n")
        else:
            print("❌ Falha na conexão\n")
        
        # Teste 2: Email simples (COMENTADO PARA EVITAR SPAM)
        # test_email = input("Digite um email para teste (ou Enter para pular): ").strip()
        # if test_email:
        #     print("2️⃣ Enviando email de teste...")
        #     if email_service.send_email(
        #         to_address=test_email,
        #         subject="Teste FIFA 25 Bot",
        #         body="Este é um email de teste do FIFA 25 Bot"
        #     ):
        #         print("✅ Email enviado\n")
        #     else:
        #         print("❌ Falha ao enviar\n")
        
        print("✅ Testes concluídos!")
    else:
        print("⚠️ Email não configurado. Configure as variáveis de ambiente:")
        print("   - EMAIL_USER")
        print("   - EMAIL_PASSWORD")
        print("   - EMAIL_SMTP_SERVER (opcional, padrão: smtp.gmail.com)")
        print("   - EMAIL_SMTP_PORT (opcional, padrão: 587)")
