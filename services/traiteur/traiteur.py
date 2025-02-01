import json
import logging
import time
import pandas as pd
import pandas_ta as ta
from confluent_kafka import Consumer, KafkaException
from confluent_kafka.admin import AdminClient
import psycopg2
from datetime import datetime
import os

# Configuration du logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration de Kafka pour le consommateur
consumer_config = {
    'bootstrap.servers': os.environ.get('KAFKA_BOOTSTRAP_SERVERS', 'kafka:9092'),
    'group.id': 'technical_indicators_group',
    'auto.offset.reset': 'earliest',
    'retry.backoff.ms': 500,
    'socket.timeout.ms': 10000
}

consumer = Consumer(consumer_config)
admin_client = AdminClient({'bootstrap.servers': os.environ.get('KAFKA_BOOTSTRAP_SERVERS', 'kafka:9092')})

# Nom du topic source
source_topic = 'stock_data_topic'

# Configuration de la base de données PostgreSQL
db_config = {
    'host': os.environ.get('POSTGRES_HOST', 'localhost'),
    'port': os.environ.get('POSTGRES_PORT', '5432'),
    'dbname': os.environ.get('POSTGRES_DB', 'stock_data'),
    'user': os.environ.get('POSTGRES_USER', 'postgres'),
    'password': os.environ.get('POSTGRES_PASSWORD', 'postgres_password'),
}

def wait_for_topic(topic_name, max_retries=12, retry_delay=5):
    """Attend que le topic soit disponible."""
    logger.info(f"Attente de la disponibilité du topic '{topic_name}'...")
    
    for attempt in range(max_retries):
        try:
            topics = admin_client.list_topics(timeout=10).topics
            if topic_name in topics:
                logger.info(f"Topic '{topic_name}' trouvé et disponible.")
                return True
                
            logger.warning(f"Topic '{topic_name}' non trouvé. Tentative {attempt + 1}/{max_retries}")
            time.sleep(retry_delay)
            
        except Exception as e:
            logger.error(f"Erreur lors de la vérification du topic (tentative {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                
    logger.error(f"Le topic '{topic_name}' n'est pas disponible après {max_retries} tentatives")
    return False

def get_db_connection():
    """Établit une connexion à la base de données."""
    try:
        conn = psycopg2.connect(**db_config)
        logger.info("Connexion à la base de données PostgreSQL réussie.")
        return conn
    except Exception as e:
        logger.error(f"Erreur de connexion à la base de données PostgreSQL: {e}")
        raise

def create_table():
    """Crée la table des indicateurs techniques si elle n'existe pas."""
    logger.info("Création de la table 'technical_indicators' si elle n'existe pas.")
    conn = get_db_connection()
    cursor = conn.cursor()
    create_table_query = '''
    CREATE TABLE IF NOT EXISTS technical_indicators (
        id SERIAL PRIMARY KEY,
        symbol VARCHAR(10),
        date DATE,
        open FLOAT,
        high FLOAT,
        low FLOAT,
        close FLOAT,
        volume BIGINT,
        rsi FLOAT,
        macd FLOAT,
        macd_signal FLOAT,
        macd_hist FLOAT,
        UNIQUE (symbol, date)
    );
    '''
    try:
        cursor.execute(create_table_query)
        conn.commit()
        logger.info("Table 'technical_indicators' créée ou déjà existante.")
    except Exception as e:
        logger.error(f"Erreur lors de la création de la table: {e}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def load_historical_data(symbol):
    """Charge les données historiques depuis la base de données."""
    logger.info(f"Chargement des données historiques pour le symbole '{symbol}'.")
    conn = get_db_connection()
    query = '''
    SELECT date, open, high, low, close, volume, rsi, macd, macd_signal, macd_hist
    FROM technical_indicators
    WHERE symbol = %s
    ORDER BY date ASC;
    '''
    try:
        df = pd.read_sql(query, conn, params=(symbol,))
        logger.info(f"{len(df)} enregistrements historiques chargés pour '{symbol}'.")
        return df
    except Exception as e:
        logger.error(f"Erreur lors du chargement des données historiques: {e}")
        return pd.DataFrame()
    finally:
        conn.close()

def store_data(symbol, df):
    """Stocke les données avec les indicateurs techniques dans la base de données."""
    logger.info(f"Stockage des données pour le symbole '{symbol}' dans la base de données.")
    conn = get_db_connection()
    cursor = conn.cursor()
    insert_query = '''
    INSERT INTO technical_indicators 
    (symbol, date, open, high, low, close, volume, rsi, macd, macd_signal, macd_hist)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (symbol, date) DO NOTHING;
    '''
    try:
        for index, row in df.iterrows():
            cursor.execute(insert_query, (
                symbol,
                row['Date'],
                row['Open'],
                row['High'],
                row['Low'],
                row['Close'],
                row['Volume'],
                row['RSI'],
                row['MACD'],
                row['MACD_SIGNAL'],
                row['MACD_HIST']
            ))
        conn.commit()
        logger.info(f"Données stockées pour le symbole '{symbol}'.")
    except Exception as e:
        logger.error(f"Erreur lors du stockage des données: {e}")
    finally:
        cursor.close()
        conn.close()

def calculate_indicators(df):
    """Calcule les indicateurs techniques pour un DataFrame."""
    try:
        # Calcul du RSI
        df['RSI'] = ta.rsi(df['Close'], length=14)
        
        # Calcul de la MACD
        macd = ta.macd(df['Close'], fast=12, slow=26, signal=9)
        df['MACD'] = df['RSI']
        df['MACD_SIGNAL'] = df['RSI']
        df['MACD_HIST'] = df['RSI']
        ## à changer


        # df_final = df_combined[df_combined['Date'].dt.strftime('%Y-%m') == month_year]
        # store_data(symbol, df_final)
        
        logger.info(f"Indicateurs techniques calculés avec succès.")
        return df
    except Exception as e:
        logger.error(f"Erreur lors du calcul des indicateurs techniques: {e}")
        raise

def process_message(msg):
    """Traite un message consommé."""
    try:
        symbol = msg.key().decode('utf-8')
        message_value = msg.value().decode('utf-8')
        data = json.loads(message_value)
        month_year = data.get('month_year')
        stock_data = data.get('data')
        
        logger.info(f"Traitement du message pour le symbole '{symbol}' et le mois '{month_year}'.")

        if not stock_data:
            logger.error(f"Le message pour '{symbol}' ne contient pas de données de stock ('data').")
            return

        if not month_year:
            logger.error(f"Le message pour '{symbol}' ne contient pas 'month_year'.")
            return
        
        # Conversion en DataFrame et préparation des données
        df_new = pd.DataFrame(stock_data)
        df_new['Date'] = pd.to_datetime(df_new['Date'])
        df_new.sort_values('Date', inplace=True)
        
        # Chargement des données historiques et combinaison avec les nouvelles données
        df_historical = load_historical_data(symbol)
        df_combined = pd.concat([df_historical, df_new], ignore_index=True)
        df_combined.drop_duplicates(subset='Date', keep='last', inplace=True)
        df_combined.sort_values('Date', inplace=True)
        df_combined.reset_index(drop=True, inplace=True)
        
        # Calcul des indicateurs techniques
        df_with_indicators = calculate_indicators(df_combined)
        
        # Filtrage des données pour le mois en cours
        df_final = df_with_indicators[df_with_indicators['Date'].dt.strftime('%Y-%m') == month_year]
        
        # Stockage des données
        store_data(symbol, df_final)
        
        logger.info(f"Traitement terminé pour '{symbol}' et le mois '{month_year}'.")
        
    except Exception as e:
        logger.error(f"Erreur lors du traitement du message: {e}")

def main():
    """Fonction principale."""
    try:
        # Création de la table si elle n'existe pas
        create_table()
        
        # Attente de la disponibilité du topic
        if not wait_for_topic(source_topic):
            logger.error("Impossible de démarrer le traiteur: topic non disponible")
            return
        
        # Abonnement au topic
        consumer.subscribe([source_topic])
        logger.info(f"Abonné au topic '{source_topic}'")
        
        # Boucle principale de consommation
        while True:
            msg = consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                logger.error(f"Erreur du consommateur: {msg.error()}")
                if "Subscribed topic not available" in str(msg.error()):
                    logger.info("Tentative de reconnexion au topic...")
                    time.sleep(5)  # Attente avant nouvelle tentative
                    continue
                
            process_message(msg)
            
    except KeyboardInterrupt:
        logger.info("Arrêt du traiteur suite à une interruption utilisateur.")
    except Exception as e:
        logger.error(f"Erreur inattendue dans la boucle principale: {e}")
    finally:
        consumer.close()
        logger.info("Consommateur Kafka fermé.")

if __name__ == "__main__":
    main()