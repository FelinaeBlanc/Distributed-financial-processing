import json
import logging
import time
from confluent_kafka import Consumer, Producer, KafkaException
from confluent_kafka.admin import AdminClient, NewTopic
import yfinance as yf
import os

# Configuration du logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration de Kafka pour le consommateur
consumer_config = {
    'bootstrap.servers': os.environ.get('KAFKA_BOOTSTRAP_SERVERS', 'kafka:9092'),
    'group.id': 'stock_agents_group',
    'auto.offset.reset': 'earliest',
}

# Configuration de Kafka pour le producteur
producer_config = {
    'bootstrap.servers': os.environ.get('KAFKA_BOOTSTRAP_SERVERS', 'kafka:9092'),
    'client.id': 'stock_agent_producer',
}

consumer = Consumer(consumer_config)
producer = Producer(producer_config)
admin_client = AdminClient({'bootstrap.servers': os.environ.get('KAFKA_BOOTSTRAP_SERVERS', 'kafka:9092')})

# Nom du topic source (actions) et du topic destination (données)
source_topic = 'stock_topic'
destination_topic = 'stock_data_topic'

def ensure_destination_topic_exists(topic_name):
    """Assure que le topic de destination existe, le crée s'il n'existe pas."""
    max_retries = 3
    retry_delay = 5  # secondes entre chaque tentative
    
    for attempt in range(max_retries):
        try:
            logger.info(f"Tentative {attempt + 1}/{max_retries} de création/vérification du topic '{topic_name}'")
            
            # Vérifier si le topic existe déjà
            topic_metadata = admin_client.list_topics(timeout=10)
            if topic_name in topic_metadata.topics:
                logger.info(f"Le topic '{topic_name}' existe déjà.")
                return True
                
            # Créer le topic s'il n'existe pas
            logger.info(f"Création du topic '{topic_name}'...")
            new_topic = NewTopic(
                topic=topic_name,
                num_partitions=30,
                replication_factor=1
            )
            
            # Créer le topic et attendre la confirmation
            future = admin_client.create_topics([new_topic])
            future.result(timeout=30)  # Attendre jusqu'à 30 secondes
            
            logger.info(f"Topic '{topic_name}' créé avec succès.")
            return True
            
        except KafkaException as ke:
            logger.error(f"Erreur Kafka lors de la tentative {attempt + 1}: {ke}")
            if attempt < max_retries - 1:
                logger.info(f"Nouvelle tentative dans {retry_delay} secondes...")
                time.sleep(retry_delay)
            else:
                logger.error(f"Échec de la création du topic après {max_retries} tentatives")
                raise
                
        except Exception as e:
            logger.error(f"Erreur inattendue lors de la tentative {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                logger.info(f"Nouvelle tentative dans {retry_delay} secondes...")
                time.sleep(retry_delay)
            else:
                logger.error(f"Échec après {max_retries} tentatives")
                raise

def fetch_stock_data(symbol, month_year):
    """Récupère les données boursières pour le symbole et le mois/année donnés."""
    logger.info(f"Récupération des données boursières pour le symbole '{symbol}' et le mois '{month_year}'.")
    start_date = f"{month_year}-01"
    year, month = map(int, month_year.split('-'))
    if month == 12:
        end_year = year + 1
        end_month = 1
    else:
        end_year = year
        end_month = month + 1
    end_date = f"{end_year}-{end_month:02d}-01"

    try:
        logger.info(f"Intervalle de récupération : {start_date} à {end_date}.")
        ticker = yf.Ticker(symbol)
        df = ticker.history(start=start_date, end=end_date, interval='1d')
        if df.empty:
            logger.warning(f"Aucune donnée trouvée pour le symbole '{symbol}' entre {start_date} et {end_date}.")
            return None
        logger.info(f"Données récupérées avec succès pour le symbole '{symbol}'. Nombre d'enregistrements : {len(df)}.")
        data = df.reset_index().to_json(orient='records', date_format='iso')
        return data
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des données pour le symbole '{symbol}': {e}")
        return None

def process_message(msg):
    """Traite un message consommé."""
    try:
        symbol = msg.key().decode('utf-8')
        action_json = msg.value().decode('utf-8')
        action = json.loads(action_json)
        month_year = action.get('month_year')

        logger.info(f"Traitement du message pour le symbole '{symbol}' et le mois '{month_year}'.")

        data = fetch_stock_data(symbol, month_year)
        if data:
            message_value = json.dumps({
                'symbol': symbol,
                'month_year': month_year,
                'data': json.loads(data)
            })
            try:
                logger.info(f"Envoi des données pour le symbole '{symbol}' et le mois '{month_year}' au topic '{destination_topic}'.")
                producer.produce(
                    topic=destination_topic,
                    key=symbol.encode('utf-8'),
                    value=message_value.encode('utf-8')
                )
                producer.flush()
                logger.info(f"Données pour le symbole '{symbol}' et le mois '{month_year}' envoyées avec succès au topic '{destination_topic}'.")
            except KafkaException as ke:
                logger.error(f"Erreur Kafka lors de l'envoi des données pour '{symbol}' au topic '{destination_topic}': {ke}")
            except Exception as e:
                logger.error(f"Erreur inattendue lors de l'envoi des données pour '{symbol}' au topic '{destination_topic}': {e}")
        else:
            logger.warning(f"Aucune donnée valide à envoyer pour le symbole '{symbol}' et le mois '{month_year}'. Continuation...")
    except Exception as e:
        logger.error(f"Erreur lors du traitement du message: {e}")

def main():
    logger.info("Initialisation de l'agent Kafka pour traiter les actions boursières.")
    
    # S'assurer que le topic de destination existe avant de commencer
    logger.info("Vérification et création éventuelle du topic de destination...")
    ensure_destination_topic_exists(destination_topic)
    
    # S'abonner au topic source
    logger.info(f"S'abonne au topic source '{source_topic}'.")
    consumer.subscribe([source_topic])

    try:
        while True:
            msg = consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                logger.error(f"Erreur du consommateur: {msg.error()}")
                continue

            process_message(msg)
    except KeyboardInterrupt:
        logger.info("Arrêt de l'agent Kafka suite à une interruption utilisateur.")
    finally:
        consumer.close()
        logger.info("Consommateur Kafka fermé.")

if __name__ == "__main__":
    main()