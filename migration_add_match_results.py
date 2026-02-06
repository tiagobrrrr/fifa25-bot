# migration_add_match_results.py - SCRIPT DE MIGRAÇÃO
# Execute este script UMA VEZ para adicionar os campos necessários

"""
INSTRUÇÕES DE USO:

1. Fazer backup do banco atual:
   pg_dump $DATABASE_URL > backup_$(date +%Y%m%d).sql

2. Executar migração:
   python migration_add_match_results.py

3. Verificar se funcionou:
   psql $DATABASE_URL -c "\\d matches"
"""

import os
import sys
from sqlalchemy import create_engine, inspect, text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_migration():
    """
    Adiciona campos necessários para armazenar resultados das partidas
    """
    
    # Obtém URL do banco
    database_url = os.environ.get('DATABASE_URL')
    
    if not database_url:
        logger.error("❌ DATABASE_URL não configurada!")
        sys.exit(1)
    
    # Corrige URL se necessário (Render usa postgres://, SQLAlchemy precisa postgresql://)
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    
    try:
        engine = create_engine(database_url)
        inspector = inspect(engine)
        
        # Verifica se tabela matches existe
        if 'matches' not in inspector.get_table_names():
            logger.error("❌ Tabela 'matches' não encontrada!")
            sys.exit(1)
        
        # Obtém colunas existentes
        existing_columns = [col['name'] for col in inspector.get_columns('matches')]
        
        logger.info(f"✅ Tabela 'matches' encontrada com {len(existing_columns)} colunas")
        
        # Define colunas a adicionar
        columns_to_add = {
            'final_score_home': 'INTEGER DEFAULT 0',
            'final_score_away': 'INTEGER DEFAULT 0',
            'winner': 'VARCHAR(100)',
            'finished_at': 'TIMESTAMP',
            'home_player': 'VARCHAR(100)',  # Se ainda não existir
            'away_player': 'VARCHAR(100)',  # Se ainda não existir
        }
        
        # Adiciona apenas colunas que não existem
        with engine.connect() as conn:
            for column_name, column_type in columns_to_add.items():
                if column_name not in existing_columns:
                    sql = f"ALTER TABLE matches ADD COLUMN {column_name} {column_type}"
                    
                    try:
                        conn.execute(text(sql))
                        conn.commit()
                        logger.info(f"✅ Coluna '{column_name}' adicionada")
                    except Exception as e:
                        logger.warning(f"⚠️ Erro ao adicionar '{column_name}': {e}")
                else:
                    logger.info(f"ℹ️ Coluna '{column_name}' já existe")
            
            # Cria índices para melhorar performance
            indices = [
                "CREATE INDEX IF NOT EXISTS idx_matches_status ON matches(status)",
                "CREATE INDEX IF NOT EXISTS idx_matches_location ON matches(location)",
                "CREATE INDEX IF NOT EXISTS idx_matches_finished_at ON matches(finished_at)",
                "CREATE INDEX IF NOT EXISTS idx_matches_home_player ON matches(home_player)",
                "CREATE INDEX IF NOT EXISTS idx_matches_away_player ON matches(away_player)"
            ]
            
            for index_sql in indices:
                try:
                    conn.execute(text(index_sql))
                    conn.commit()
                    logger.info(f"✅ Índice criado")
                except Exception as e:
                    logger.warning(f"⚠️ Erro ao criar índice: {e}")
        
        logger.info("\n" + "="*60)
        logger.info("✅ MIGRAÇÃO CONCLUÍDA COM SUCESSO!")
        logger.info("="*60)
        
        # Mostra estrutura final
        logger.info("\n📋 ESTRUTURA FINAL DA TABELA 'matches':")
        final_columns = [col['name'] for col in inspector.get_columns('matches')]
        for col in final_columns:
            logger.info(f"   - {col}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ ERRO NA MIGRAÇÃO: {e}")
        return False


def verify_migration():
    """
    Verifica se migração foi aplicada corretamente
    """
    database_url = os.environ.get('DATABASE_URL')
    
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    
    engine = create_engine(database_url)
    inspector = inspect(engine)
    
    columns = [col['name'] for col in inspector.get_columns('matches')]
    
    required_columns = [
        'final_score_home',
        'final_score_away',
        'winner',
        'finished_at',
        'home_player',
        'away_player'
    ]
    
    missing = [col for col in required_columns if col not in columns]
    
    if missing:
        logger.error(f"❌ Colunas faltando: {missing}")
        return False
    else:
        logger.info("✅ Todas as colunas necessárias estão presentes!")
        return True


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Migração do banco de dados')
    parser.add_argument('--verify', action='store_true', help='Apenas verificar migração')
    
    args = parser.parse_args()
    
    if args.verify:
        verify_migration()
    else:
        print("\n⚠️  ATENÇÃO: Esta migração irá modificar o banco de dados!")
        print("Certifique-se de ter um backup antes de continuar.\n")
        
        response = input("Deseja continuar? (s/N): ")
        
        if response.lower() == 's':
            success = run_migration()
            
            if success:
                print("\n🎉 Migração concluída! Execute os próximos passos:")
                print("1. Reinicie o aplicativo no Render")
                print("2. Teste uma partida ao vivo")
                print("3. Verifique se estatísticas estão sendo calculadas")
        else:
            print("Migração cancelada.")
