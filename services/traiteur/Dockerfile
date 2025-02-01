# Dockerfile.traiteur
FROM python:3.9-slim

# Installer les dépendances
RUN apt-get update && apt-get install -y libpq-dev gcc
RUN pip uninstall numpy -y
RUN pip install numpy==1.26.4 confluent-kafka pandas pandas_ta psycopg2-binary

# Copier les scripts nécessaires
COPY services/traiteur/traiteur.py /app/traiteur.py

# Définir le répertoire de travail
WORKDIR /app

# Exécuter le script
CMD ["python", "traiteur.py"]
