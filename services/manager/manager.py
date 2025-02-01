import json
import logging
from datetime import date
from action import Action
from confluent_kafka import Producer, KafkaException
from confluent_kafka.admin import AdminClient, NewTopic
from apscheduler.schedulers.blocking import BlockingScheduler
from dateutil.relativedelta import relativedelta
import psycopg2
import os

# Configuration du logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration de Kafka
kafka_config = {
    'bootstrap.servers': os.environ.get('KAFKA_BOOTSTRAP_SERVERS', 'kafka:9092'),
    'client.id': 'manager',
}

admin_client = AdminClient(kafka_config)
producer = Producer(kafka_config)

# Nom du topic Kafka
topic_name = 'stock_topic'

# Liste des symboles codée en dur
symbols = [
    'AAPL', 'GOOG', 'MSFT', 'AMZN', 'TSLA', 'META', 'NVDA', 'NFLX', 'BABA', 'INTC',
    'AMD', 'IBM', 'ORCL', 'CSCO', 'QCOM', 'SAP', 'ADBE', 'CRM', 'PYPL', 'UBER',
    'LYFT', 'SNAP', 'TWTR', 'SHOP', 'SQ', 'ZM', 'SPOT', 'PINS', 'ROKU', 'DOCU',
    'PLTR', 'NIO', 'XPEV', 'LI', 'BYND', 'PTON', 'ZM', 'SNOW', 'ABNB', 'DASH',
    'COIN', 'RBLX', 'AFRM', 'ASAN', 'BMBL', 'CLOV', 'DKNG', 'FUBO', 'HOOD', 'LCID',
    'NKLA', 'OPEN', 'PLUG', 'QS', 'RIDE', 'SOFI', 'SPCE', 'WISH', 'WKHS', 'XOM',
    'CVX', 'COP', 'OXY', 'SLB', 'HAL', 'BKR', 'MRO', 'PSX', 'VLO', 'KMI',
    'WMB', 'ET', 'PXD', 'EOG', 'DVN', 'FANG', 'APA', 'CLR', 'HES', 'MPC',
    'PSX', 'VLO', 'XOM', 'CVX', 'BP', 'TOT', 'RDS.A', 'RDS.B', 'EQNR', 'ENB',
    'TRP', 'SU', 'CNQ', 'IMO', 'HSE', 'CVE', 'PBR', 'VALE', 'RIO', 'BHP',
    'FCX', 'NEM', 'GOLD', 'ABX', 'AEM', 'NTR', 'MOS', 'CF', 'ADM', 'BG',
    'CARG', 'CAR', 'CVNA', 'KMX', 'LAD', 'AN', 'SAH', 'GPI', 'PAG', 'ABG',
    'AAP', 'AZO', 'ORLY', 'LKQ', 'GPC', 'DORM', 'BWA', 'ALV', 'LEA', 'MGA',
    'TEN', 'VC', 'GM', 'F', 'STLA', 'TM', 'HMC', 'NSANY', 'VWAGY', 'BMWYY',
    'DDAIF', 'HYMTF', 'KIA', 'TSLA', 'NIO', 'XPEV', 'LI', 'BYDDY', 'BYDDF', 'NKLA',
    'RIVN', 'LCID', 'FSR', 'GOEV', 'SOLO', 'AYRO', 'KNDI', 'ARVL', 'FFIE', 'MULN',
    'PEV', 'RIDE', 'WKHS', 'ELMS', 'FUV', 'CENN', 'BRDS', 'ZEV', 'REE', 'VLTA',
    'CHPT', 'BLNK', 'EVGO', 'WBX', 'BEEM', 'SNOW', 'MDB', 'DDOG', 'NET', 'ZS',
    'CRWD', 'OKTA', 'SPLK', 'ESTC', 'PANW', 'FTNT', 'CHKP', 'QLYS', 'TENB', 'SAIL',
    'CYBR', 'FEYE', 'MIME', 'NLOK', 'RPD', 'VRNS', 'S', 'BB', 'MSFT', 'GOOG',
    'AMZN', 'AAPL', 'META', 'NFLX', 'TSLA', 'NVDA', 'AMD', 'INTC', 'IBM', 'ORCL',
    'CSCO', 'QCOM', 'TXN', 'AVGO', 'ADI', 'NXPI', 'SWKS', 'QRVO', 'MCHP', 'MPWR',
    'ON', 'STM', 'IFNNY', 'ROHCY', 'NXPI', 'SWKS', 'QRVO', 'MCHP', 'MPWR', 'ON',
    'STM', 'IFNNY', 'ROHCY', 'NXPI', 'SWKS', 'QRVO', 'MCHP', 'MPWR', 'ON', 'STM',
    'IFNNY', 'ROHCY', 'NXPI', 'SWKS', 'QRVO', 'MCHP', 'MPWR', 'ON', 'STM', 'IFNNY',
    'ROHCY', 'NXPI', 'SWKS', 'QRVO', 'MCHP', 'MPWR', 'ON', 'STM', 'IFNNY', 'ROHCY',
    'NXPI', 'SWKS', 'QRVO', 'MCHP', 'MPWR', 'ON', 'STM', 'IFNNY', 'ROHCY', 'NXPI',
    'SWKS', 'QRVO', 'MCHP', 'MPWR', 'ON', 'STM', 'IFNNY', 'ROHCY', 'NXPI', 'SWKS',
    'QRVO', 'MCHP', 'MPWR', 'ON', 'STM', 'IFNNY', 'ROHCY', 'NXPI', 'SWKS', 'QRVO',
    'MCHP', 'MPWR', 'ON', 'STM', 'IFNNY', 'ROHCY', 'NXPI', 'SWKS', 'QRVO', 'MCHP',
    'MPWR', 'ON', 'STM', 'IFNNY', 'ROHCY', 'NXPI', 'SWKS', 'QRVO', 'MCHP', 'MPWR',
    'ON', 'STM', 'IFNNY', 'ROHCY', 'NXPI', 'SWKS', 'QRVO', 'MCHP', 'MPWR', 'ON',
    'STM', 'IFNNY', 'ROHCY', 'NXPI', 'SWKS', 'QRVO', 'MCHP', 'MPWR', 'ON', 'STM',
    'IFNNY', 'ROHCY', 'NXPI', 'SWKS', 'QRVO', 'MCHP', 'MPWR', 'ON', 'STM', 'IFNNY',
    'ROHCY', 'NXPI', 'SWKS', 'QRVO', 'MCHP', 'MPWR', 'ON', 'STM', 'IFNNY', 'ROHCY',
    'NXPI', 'SWKS', 'QRVO', 'MCHP', 'MPWR', 'ON', 'STM', 'IFNNY', 'ROHCY', 'NXPI',
    'SWKS', 'QRVO', 'MCHP', 'MPWR', 'ON', 'STM', 'IFNNY', 'ROHCY', 'NXPI']

# Configuration de la base de données PostgreSQL
db_config = {
    'host': os.environ.get('POSTGRES_HOST', 'localhost'),
    'port': os.environ.get('POSTGRES_PORT', '5432'),
    'dbname': os.environ.get('POSTGRES_DB', 'stock_data'),
    'user': os.environ.get('POSTGRES_USER', 'postgres'),
    'password': os.environ.get('POSTGRES_PASSWORD', 'postgres_password'),
}

def get_db_connection():
    try:
        conn = psycopg2.connect(**db_config)
        logger.info("Connexion à la base de données PostgreSQL réussie.")
        return conn
    except Exception as e:
        logger.error(f"Erreur de connexion à la base de données PostgreSQL: {e}")
        raise

def create_symbol_state_table():
    """
    Crée la table symbol_state si elle n'existe pas.
    """
    logger.info("Création de la table 'symbol_state' si elle n'existe pas.")
    conn = get_db_connection()
    cursor = conn.cursor()
    create_table_query = '''
    CREATE TABLE IF NOT EXISTS symbol_state (
        symbol VARCHAR PRIMARY KEY,
        last_date DATE
    );
    '''
    try:
        cursor.execute(create_table_query)
        conn.commit()
        logger.info("Table 'symbol_state' créée ou déjà existante.")
    except Exception as e:
        logger.error(f"Erreur lors de la création de la table 'symbol_state': {e}")
    finally:
        cursor.close()
        conn.close()

def get_last_action_date(symbol):
    """
    Récupère la dernière date traitée pour un symbole donné.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    query = "SELECT last_date FROM symbol_state WHERE symbol = %s;"
    try:
        cursor.execute(query, (symbol,))
        result = cursor.fetchone()
        if result and result[0]:
            logger.info(f"Dernière action pour {symbol}: {result[0]}.")
            return result[0]
        else:
            logger.info(f"Aucune action précédente pour {symbol}.")
            return None
    except Exception as e:
        logger.error(f"Erreur lors de la récupération de la dernière action pour {symbol}: {e}")
        return None
    finally:
        cursor.close()
        conn.close()

def update_last_action_date(symbol, new_date):
    """
    Met à jour la dernière date traitée pour un symbole donné.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    upsert_query = '''
    INSERT INTO symbol_state (symbol, last_date)
    VALUES (%s, %s)
    ON CONFLICT (symbol) DO UPDATE SET last_date = EXCLUDED.last_date;
    '''
    try:
        cursor.execute(upsert_query, (symbol, new_date))
        conn.commit()
        logger.info(f"Dernière date mise à jour pour {symbol}: {new_date}.")
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour de la dernière date pour {symbol}: {e}")
    finally:
        cursor.close()
        conn.close()

def ensure_topic_exists(topic_name):
    """
    Assure que le topic Kafka existe, le crée s'il n'existe pas.
    """
    try:
        topic_metadata = admin_client.list_topics(timeout=10)
        if topic_name in topic_metadata.topics:
            logger.info(f"Le topic '{topic_name}' existe déjà.")
        else:
            num_partitions = 30
            replication_factor = 1
            new_topic = NewTopic(
                topic=topic_name,
                num_partitions=num_partitions,
                replication_factor=replication_factor
            )
            admin_client.create_topics([new_topic])
            logger.info(f"Topic '{topic_name}' créé avec {num_partitions} partitions.")
    except KafkaException as e:
        logger.error(f"Échec lors de la création ou de la vérification du topic '{topic_name}': {e}")
    except Exception as e:
        logger.error(f"Exception lors de la création ou de la vérification du topic '{topic_name}': {e}")

def generate_actions():
    current_date = date.today()
    logger.info(f"Démarrage de la génération d'actions jusqu'à {current_date}.")

    # Assure que le topic Kafka existe
    ensure_topic_exists(topic_name)

    # Calcule le premier jour du mois courant
    first_day_of_current_month = current_date.replace(day=1)

    for symbol in symbols:
        last_action_date = get_last_action_date(symbol)

        # Si aucune date, on commence au 01/2010
        if last_action_date:
            current_processing_date = last_action_date + relativedelta(months=2)
        else:
            current_processing_date = date(2010, 1, 1)

        # Boucle tant qu'on est avant le premier jour du mois courant
        while current_processing_date < first_day_of_current_month:
            month_year = current_processing_date.strftime('%Y-%m')
            logger.info(f"Traitement pour {symbol} au mois: {month_year}")

            # Crée l'action
            action = Action(symbol, month_year)
            action_json = action.to_json()
            logger.info(f"Action générée: {action_json}")

            # Envoie à Kafka
            try:
                producer.produce(
                    topic=topic_name,
                    key=symbol.encode('utf-8'),
                    value=action_json.encode('utf-8')
                )
                producer.flush()
                logger.info(f"Message pour {symbol} au mois '{month_year}' envoyé à Kafka.")

                # Met à jour la date traitée
                update_last_action_date(symbol, current_processing_date)

            except KafkaException as e:
                logger.error(f"Échec de l'envoi pour {symbol} au mois '{month_year}': {e}")
                break
            except Exception as e:
                logger.error(f"Exception lors de l'envoi pour {symbol} au mois '{month_year}': {e}")
                break

            # Avance d'un mois
            current_processing_date += relativedelta(months=1)

def main():
    # Initialisation de la table de suivi
    create_symbol_state_table()

    # Pour les tests, vous pouvez appeler generate_actions() directement
    generate_actions()

    # Crée un planificateur pour exécuter la fonction generate_actions mensuellement
    scheduler = BlockingScheduler()
    scheduler.add_job(
        generate_actions,
        'cron',
        day='1',
        hour=0,
        minute=0,
        id='monthly_generate_actions'
    )

    try:
        logger.info("Démarrage du planificateur...")
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Arrêt du planificateur.")

if __name__ == "__main__":
    main()
