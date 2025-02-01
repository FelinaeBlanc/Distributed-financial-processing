# Dockerfile.manager
FROM python:3.9-slim

# Installer les dépendances
RUN pip install --upgrade pip
RUN pip install confluent-kafka apscheduler python-dateutil  psycopg2-binary

# Copier les scripts nécessaires
COPY services/manager/manager.py /app/manager.py
COPY services/common/action.py /app/action.py

# Définir le répertoire de travail
WORKDIR /app

# Exécuter le script
CMD ["python", "manager.py"]