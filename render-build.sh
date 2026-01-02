#!/usr/bin/env bash
# exit on error
set -o errexit

# Instalar dependências Python
pip install --upgrade pip
pip install -r requirements.txt

# Inicializar banco de dados
python -c "from models import init_db; init_db()"

echo "✅ Build concluído com sucesso!"