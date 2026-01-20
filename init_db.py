#!/usr/bin/env python3
"""
Script para inicializar o banco de dados
Execute este script para criar as tabelas necessárias
"""

import os
import sys
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Importar modelos e app
from app import app, db
from models import Match, Player, Analysis

def init_database():
    """Cria todas as tabelas no banco de dados"""
    logger.info("="*80)
    logger.info("🗄️  INICIALIZANDO BANCO DE DADOS")
    logger.info("="*80)
    
    with app.app_context():
        try:
            # Dropar todas as tabelas (cuidado em produção!)
            logger.info("🗑️  Removendo tabelas antigas (se existirem)...")
            db.drop_all()
            
            # Criar todas as tabelas
            logger.info("🔨 Criando tabelas...")
            db.create_all()
            
            # Verificar se as tabelas foram criadas
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            
            logger.info(f"✅ Tabelas criadas com sucesso:")
            for table in tables:
                logger.info(f"   - {table}")
            
            # Verificar colunas da tabela matches
            if 'matches' in tables:
                columns = [col['name'] for col in inspector.get_columns('matches')]
                logger.info(f"\n📋 Colunas da tabela 'matches':")
                for col in columns:
                    logger.info(f"   - {col}")
            
            logger.info("\n" + "="*80)
            logger.info("✅ BANCO DE DADOS INICIALIZADO COM SUCESSO!")
            logger.info("="*80)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro ao inicializar banco de dados: {e}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == "__main__":
    success = init_database()
    sys.exit(0 if success else 1)