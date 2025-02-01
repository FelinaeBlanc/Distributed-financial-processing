# Dockerfile.agent
FROM python:3.9-slim

RUN apt-get update && apt-get install -y 

# Installer les dépendances
RUN pip install confluent-kafka yfinance

# Copier les scripts
COPY services/agent/agent.py /app/agent.py

# Définir le répertoire de travail
WORKDIR /app

# Exécuter le script
CMD ["python", "agent.py"]
