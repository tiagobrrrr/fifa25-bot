"""
Script de migração para corrigir o schema do banco de dados
Converte score1 e score2 para uma única coluna 'score'
"""

import os
from sqlalchemy import create_engine, text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('Migration')

DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///fifa25_bot.db')

# Fix para Render/Heroku
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

engine = create_engine(DATABASE_URL)


def migrate_database():
    """
    Executa a migração do banco de dados
    """
    try:
        with engine.connect() as conn:
            # Inicia transação
            trans = conn.begin()
            
            try:
                logger.info("🔄 Iniciando migração do banco de dados...")
                
                # Verifica se a coluna 'score' já existe
                result = conn.execute(text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name='matches' AND column_name='score'
                """))
                
                if result.fetchone():
                    logger.info("✅ Coluna 'score' já existe. Migração não necessária.")
                    trans.rollback()
                    return True
                
                # Adiciona coluna 'score'
                logger.info("➕ Adicionando coluna 'score'...")
                conn.execute(text("ALTER TABLE matches ADD COLUMN score VARCHAR(20)"))
                
                # Migra dados de score1 e score2 para score
                logger.info("🔄 Migrando dados de score1 e score2 para score...")
                conn.execute(text("""
                    UPDATE matches 
                    SET score = COALESCE(score1, '0') || '-' || COALESCE(score2, '0')
                    WHERE score1 IS NOT NULL AND score2 IS NOT NULL
                """))
                
                # Remove colunas antigas
                logger.info("🗑️  Removendo colunas score1 e score2...")
                conn.execute(text("ALTER TABLE matches DROP COLUMN IF EXISTS score1"))
                conn.execute(text("ALTER TABLE matches DROP COLUMN IF EXISTS score2"))
                
                # Commit da transação
                trans.commit()
                logger.info("✅ Migração concluída com sucesso!")
                return True
                
            except Exception as e:
                trans.rollback()
                logger.error(f"❌ Erro durante migração: {e}")
                logger.info("🔄 Tentando abordagem alternativa...")
                
                # Se falhar, tenta criar uma nova tabela
                return migrate_with_new_table(conn)
                
    except Exception as e:
        logger.error(f"❌ Erro fatal na migração: {e}")
        return False


def migrate_with_new_table(conn):
    """
    Migração alternativa: cria nova tabela e migra dados
    """
    try:
        trans = conn.begin()
        
        # Cria tabela temporária com schema correto
        logger.info("🔄 Criando tabela temporária...")
        conn.execute(text("""
            CREATE TABLE matches_new (
                id SERIAL PRIMARY KEY,
                team1 VARCHAR(100),
                team2 VARCHAR(100),
                player1 VARCHAR(100),
                player2 VARCHAR(100),
                score VARCHAR(20),
                tournament VARCHAR(200),
                match_time VARCHAR(50),
                location VARCHAR(100),
                status VARCHAR(50),
                scraped_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        
        # Migra dados
        logger.info("🔄 Migrando dados...")
        conn.execute(text("""
            INSERT INTO matches_new 
            (id, team1, team2, player1, player2, score, tournament, match_time, location, status, scraped_at, created_at)
            SELECT 
                id, team1, team2, player1, player2,
                COALESCE(score1, '0') || '-' || COALESCE(score2, '0'),
                tournament, match_time, location, status, scraped_at, created_at
            FROM matches
        """))
        
        # Remove tabela antiga
        logger.info("🗑️  Removendo tabela antiga...")
        conn.execute(text("DROP TABLE matches"))
        
        # Renomeia tabela nova
        logger.info("✏️  Renomeando tabela...")
        conn.execute(text("ALTER TABLE matches_new RENAME TO matches"))
        
        trans.commit()
        logger.info("✅ Migração alternativa concluída com sucesso!")
        return True
        
    except Exception as e:
        trans.rollback()
        logger.error(f"❌ Erro na migração alternativa: {e}")
        return False


def verify_migration():
    """
    Verifica se a migração foi bem-sucedida
    """
    try:
        with engine.connect() as conn:
            # Verifica estrutura da tabela
            result = conn.execute(text("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name='matches'
                ORDER BY ordinal_position
            """))
            
            logger.info("\n📋 Estrutura atual da tabela 'matches':")
            for row in result:
                logger.info(f"  - {row[0]}: {row[1]}")
            
            # Conta registros
            result = conn.execute(text("SELECT COUNT(*) FROM matches"))
            count = result.fetchone()[0]
            logger.info(f"\n📊 Total de registros: {count}")
            
            return True
            
    except Exception as e:
        logger.error(f"❌ Erro ao verificar migração: {e}")
        return False


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("🔧 SCRIPT DE MIGRAÇÃO - FIFA25 Bot")
    print("=" * 70 + "\n")
    
    # Executa migração
    if migrate_database():
        print("\n✅ Migração executada com sucesso!")
        
        # Verifica resultado
        print("\n🔍 Verificando resultado...")
        verify_migration()
        
    else:
        print("\n❌ Falha na migração. Verifique os logs acima.")
        print("\n⚠️  OPÇÃO ALTERNATIVA:")
        print("Se a migração falhar, você pode:")
        print("1. Fazer backup dos dados")
        print("2. Dropar a tabela 'matches'")
        print("3. Deixar o models.py recriar a tabela com o schema correto")
    
    print("\n" + "=" * 70)