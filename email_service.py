import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class EmailService:
    """Serviço de envio de emails com relatórios"""
    
    def __init__(self):
        # Configurações do SMTP
        self.smtp_server = os.getenv('EMAIL_SMTP_SERVER', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('EMAIL_SMTP_PORT', 587))
        self.email_user = os.getenv('EMAIL_USER')
        self.email_password = os.getenv('EMAIL_PASSWORD')
        
        # Email de destino (para onde enviar os relatórios)
        self.recipient_email = os.getenv('RECIPIENT_EMAIL')
        
        # Validação
        self.is_configured = all([
            self.email_user,
            self.email_password,
            self.recipient_email
        ])
        
        if not self.is_configured:
            logger.warning("⚠️  Email não configurado. Configure as variáveis de ambiente.")
    
    def send_report(self, excel_file, report_type='manual', stats=None):
        """
        Envia relatório por email
        
        Args:
            excel_file: BytesIO com o arquivo Excel
            report_type: 'daily', 'weekly', 'monthly', ou 'manual'
            stats: Dicionário com estatísticas para incluir no corpo do email
        """
        
        if not self.is_configured:
            logger.error("❌ Email não configurado!")
            return False
        
        try:
            # Cria mensagem
            msg = MIMEMultipart()
            msg['From'] = self.email_user
            msg['To'] = self.recipient_email
            msg['Subject'] = self._get_subject(report_type)
            
            # Corpo do email
            body = self._create_email_body(report_type, stats)
            msg.attach(MIMEText(body, 'html'))
            
            # Anexa o arquivo Excel
            filename = f"FIFA25_Relatorio_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(excel_file.read())
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', f'attachment; filename={filename}')
            msg.attach(part)
            
            # Envia email
            logger.info(f"📧 Enviando email para {self.recipient_email}...")
            
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.email_user, self.email_password)
                server.send_message(msg)
            
            logger.info(f"✅ Email enviado com sucesso!")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro ao enviar email: {e}", exc_info=True)
            return False
    
    def _get_subject(self, report_type):
        """Gera assunto do email"""
        date_str = datetime.now().strftime('%d/%m/%Y')
        
        subjects = {
            'daily': f'🎮 Relatório Diário FIFA25 - {date_str}',
            'weekly': f'📊 Relatório Semanal FIFA25 - {date_str}',
            'monthly': f'📈 Relatório Mensal FIFA25 - {date_str}',
            'manual': f'📋 Relatório FIFA25 - {date_str}'
        }
        
        return subjects.get(report_type, subjects['manual'])
    
    def _create_email_body(self, report_type, stats):
        """Cria corpo do email em HTML"""
        
        # Estatísticas padrão
        if stats is None:
            stats = {
                'total_matches': 0,
                'live': 0,
                'finished': 0,
                'by_location': {}
            }
        
        # Template HTML
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
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
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    padding: 30px;
                    border-radius: 10px;
                    text-align: center;
                    margin-bottom: 20px;
                }}
                .stats {{
                    background: #f8f9fa;
                    padding: 20px;
                    border-radius: 10px;
                    margin-bottom: 20px;
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
                .stat-label {{
                    font-weight: bold;
                }}
                .stat-value {{
                    color: #667eea;
                    font-size: 1.2em;
                    font-weight: bold;
                }}
                .footer {{
                    text-align: center;
                    color: #888;
                    font-size: 0.9em;
                    margin-top: 30px;
                    padding-top: 20px;
                    border-top: 1px solid #ddd;
                }}
                .location-list {{
                    margin-top: 10px;
                    padding-left: 20px;
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>🎮 FIFA25 Bot</h1>
                <p>Relatório de Partidas</p>
            </div>
            
            <p>Olá!</p>
            
            <p>Segue em anexo o relatório completo com <strong>{stats['total_matches']}</strong> partidas.</p>
            
            <div class="stats">
                <h3>📊 Resumo do Período</h3>
                
                <div class="stat-item">
                    <span class="stat-label">Total de Partidas:</span>
                    <span class="stat-value">{stats['total_matches']}</span>
                </div>
                
                <div class="stat-item">
                    <span class="stat-label">Partidas ao Vivo:</span>
                    <span class="stat-value">{stats.get('live', 0)}</span>
                </div>
                
                <div class="stat-item">
                    <span class="stat-label">Partidas Finalizadas:</span>
                    <span class="stat-value">{stats.get('finished', 0)}</span>
                </div>
                
                {self._format_locations_html(stats.get('by_location', {}))}
            </div>
            
            <div style="background: #fff3cd; padding: 15px; border-radius: 8px; border-left: 4px solid #ffc107;">
                <strong>📋 O arquivo Excel contém 5 abas:</strong>
                <ul>
                    <li><strong>Visão Geral</strong> - Estatísticas resumidas</li>
                    <li><strong>Por Estádio</strong> - Detalhado por location</li>
                    <li><strong>Por Jogador</strong> - Ranking e estatísticas</li>
                    <li><strong>Ao Vivo</strong> - Partidas em andamento</li>
                    <li><strong>Histórico</strong> - Dados completos</li>
                </ul>
            </div>
            
            <div class="footer">
                <p>Este é um email automático do FIFA25 Bot</p>
                <p>Dashboard: <a href="https://fifa25-bot-i1zf.onrender.com">fifa25-bot-i1zf.onrender.com</a></p>
                <p>Enviado em {datetime.now().strftime('%d/%m/%Y às %H:%M:%S')} (Horário de São Paulo)</p>
            </div>
        </body>
        </html>
        """
        
        return html
    
    def _format_locations_html(self, by_location):
        """Formata locações para HTML"""
        if not by_location:
            return ''
        
        html = '<div style="margin-top: 20px;"><strong>Por Estádio:</strong><div class="location-list">'
        
        for location, count in sorted(by_location.items(), key=lambda x: x[1], reverse=True):
            html += f'<div>• {location}: <strong>{count}</strong> partidas</div>'
        
        html += '</div></div>'
        
        return html
