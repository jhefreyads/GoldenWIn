import MetaTrader5 as mt5
import pandas as pd
import mysql.connector
from mysql.connector import Error
from configparser import ConfigParser
import os
from datetime import datetime, timedelta
import time
import asyncio
import logging

# Ler as configurações do arquivo config.ini
config = ConfigParser()
config.read('config.ini')

db_config = {
    'host': config.get('database', 'host'),
    'port': config.getint('database', 'port'),
    'database': config.get('database', 'database'),
    'user': config.get('database', 'user'),
    'password': config.get('database', 'password'),
    'autocommit': True  # Ativar o autocommit para commit automático
}

conn = None  # Variável global para a conexão

# Função para limpar logs antigos
def clean_old_logs(log_dir, days=2):
    now = time.time()
    cutoff = now - (days * 86400)  # 86400 segundos em um dia

    if os.path.exists(log_dir):
        for filename in os.listdir(log_dir):
            file_path = os.path.join(log_dir, filename)
            if os.path.isfile(file_path):
                file_mtime = os.path.getmtime(file_path)
                if file_mtime < cutoff:
                    os.remove(file_path)
                    print(f"Log antigo removido: {file_path}")

# Cria a pasta logs se não existir
log_dir = 'logs'
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

# Limpa logs antigos
clean_old_logs(log_dir, days=2)

# Configuração do log
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[logging.FileHandler(os.path.join(log_dir, 'logs_candles_mt5.log'), 'a', 'utf-8')])

# Função para conectar ao MetaTrader 5 assincronamente
async def connect_to_mt5():
    if not mt5.initialize():
        logging.error("Erro ao inicializar o MetaTrader 5. Verifique se a plataforma está instalada.")
        return False
    return True

# Função para desconectar do MetaTrader 5
def disconnect_from_mt5():
    mt5.shutdown()

# Mapeamento dos intervalos de tempo
timeframe_mapping = {
    1: mt5.TIMEFRAME_M1,
    5: mt5.TIMEFRAME_M5,
    15: mt5.TIMEFRAME_M15,
}

# Função para obter o histórico de velas assincronamente do MetaTrader 5
async def get_candle_history_mt5(symbol, timeframe_minutes, num_candles):
    try:
        if timeframe_minutes not in timeframe_mapping:
            logging.error("Intervalo de tempo não suportado: %s", timeframe_minutes)
            return None

        rates = mt5.copy_rates_from_pos(symbol, timeframe_mapping[timeframe_minutes], 0, num_candles + 1)
        if rates is None or len(rates) == 0:
            return None

        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        df['time'] = df['time'] - pd.Timedelta(hours=6)

        # Remova a última vela, pois ela ainda está aberta
        df = df.iloc[:-1]

        return df
    except Exception as e:
        logging.error("Erro ao obter o histórico de velas do MetaTrader 5: %s", e)
        print("Erro ao obter o histórico de velas do MetaTrader 5: %s", e)
        return None

# Função para reconectar ao banco de dados se a conexão falhar
async def reconnect_db():
    global conn
    while True:
        try:
            conn = mysql.connector.connect(**db_config)
            if conn.is_connected():
                logging.info("Reconectado ao banco de dados com sucesso.")
                return
        except Error as e:
            logging.error("Erro ao reconectar ao banco de dados: %s", e)
            await asyncio.sleep(5)

# Função para inserir os dados das velas no banco de dados assincronamente
async def insert_candle_data(symbol, timeframe_minutes, df, source):
    timeframe_text = f"M{timeframe_minutes}"

    try:
        cursor = conn.cursor()

        for _, row in df.iterrows():
            time_str = row['time'].strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute("SELECT COUNT(*) FROM candle_history WHERE symbol = %s AND timeframe = %s AND time = %s", 
                           (symbol, timeframe_text, time_str))
            count = cursor.fetchone()[0]

            if count == 0:
                cursor.execute("""
                    INSERT INTO candle_history (symbol, timeframe, time, open, high, low, close, tick_volume, spread, real_volume, source) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (symbol, timeframe_text, time_str, row['open'], row['high'], row['low'], row['close'], row['tick_volume'], row['spread'], row['real_volume'], source))
                logging.info("Vela inserida com sucesso: %s, %s, %s, %f, %f, %f, %f, %d, %d, %d, %s", 
                             symbol, timeframe_text, time_str, row['open'], row['high'], row['low'], row['close'], 
                             row['tick_volume'], row['spread'], row['real_volume'], source)
                print("Vela inserida com sucesso:", 
                             symbol, timeframe_text, time_str, row['open'], row['high'], row['low'], row['close'], 
                             row['tick_volume'], row['spread'], row['real_volume'], source)

        cursor.close()
    except Exception as e:
        logging.error("Erro ao inserir dados das velas no banco de dados: %s", e)
        print("Erro ao inserir dados das velas no banco de dados: %s", e)
        await reconnect_db()  # Tentar reconectar ao banco de dados se falhar

async def main_mt5():
    symbols = ["AUDCAD", "EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD", "NZDUSD", "EURGBP", "EURJPY", "GBPJPY", "EURAUD", "EURCHF", "GBPCHF", "AUDJPY", "NZDJPY", "AUDNZD", "GBPAUD"]

    timeframes = [1, 5, 15]  # Em minutos
    num_candles = 1000  # Número de velas históricas a serem buscadas
    print("Iniciando captura de candles")
    if not await connect_to_mt5():
        return

    logging.info("Iniciando captura de Candles")

    # Dicionário para rastrear o último timestamp de cada par de moedas e intervalo de tempo
    last_inserted_timestamps_mt5 = {}

    try:
        # Carregar os últimos timestamps inseridos do banco de dados
        cursor = conn.cursor()
        for symbol in symbols:
            for timeframe_minutes in timeframes:
                cursor.execute("SELECT MAX(time) FROM candle_history WHERE symbol = %s AND timeframe = %s AND source = 'MT5'", 
                               (symbol, f"M{timeframe_minutes}"))
                last_inserted_timestamps_mt5[(symbol, timeframe_minutes)] = cursor.fetchone()[0]
        cursor.close()
    except Exception as e:
        logging.error("Erro ao carregar os últimos timestamps inseridos do banco de dados: %s", e)
        print("Erro ao carregar os últimos timestamps inseridos do banco de dados: %s", e)

    while True:
        tasks_mt5 = []

        for symbol in symbols:
            for timeframe_minutes in timeframes:
                tasks_mt5.append(process_symbol_timeframe_mt5(symbol, timeframe_minutes, num_candles, last_inserted_timestamps_mt5))

        await asyncio.gather(*tasks_mt5)
        await asyncio.sleep(5)

async def process_symbol_timeframe_mt5(symbol, timeframe_minutes, num_candles, last_inserted_timestamps):
    candle_history = await get_candle_history_mt5(symbol, timeframe_minutes, num_candles)
    if candle_history is not None:
        # Filtrar apenas as velas mais recentes que não foram inseridas anteriormente
        last_timestamp = last_inserted_timestamps.get((symbol, timeframe_minutes), None)
        if last_timestamp is not None:
            candle_history = candle_history[candle_history['time'] > last_timestamp]

        if not candle_history.empty:
            await insert_candle_data(symbol, timeframe_minutes, candle_history, "MT5")
            # Atualizar o último timestamp inserido para este par de moedas e intervalo de tempo
            last_inserted_timestamps[(symbol, timeframe_minutes)] = candle_history['time'].max()

async def main():
    global conn
    await reconnect_db()
    await asyncio.gather(main_mt5())

if __name__ == "__main__":
    asyncio.run(main())
