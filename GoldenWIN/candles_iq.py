import time
from datetime import datetime, timedelta
import mysql.connector
from configparser import ConfigParser
from mysql.connector import Error
import asyncio
from iqoptionapi.stable_api import IQ_Option
import logging
import os

check_assets = 0
assets = ['EURJPY-OTC', 'AUDCAD-OTC', 'USDJPY-OTC', 'EURUSD-OTC', 'NZDUSD-OTC', 'GBPUSD-OTC', 'GBPJPY-OTC', 'USDCHF-OTC', 'EURGBP-OTC', 'EURUSD-OTC', 'EURGBP-OTC', 'USDCHF-OTC', 'GBPUSD-OTC', 'GBPJPY-OTC']

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

# Configuração do log
log_dir = 'logs'
if not os.path.exists(log_dir):
    os.makedirs(log_dir)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[logging.FileHandler(os.path.join(log_dir, 'logs_candles_iqoption.log'), 'a', 'utf-8')])

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

async def connect_to_iqoption():
    max_attempts = 20
    attempt = 0
    while attempt < max_attempts:
        try:
            Iq = IQ_Option("jhefrey@leoh.store", "Hanna@0502")
            Iq.connect()
            if Iq.check_connect():
                logging.info("Conectado com sucesso ao IQ Option.")
                return Iq
            else:
                logging.warning("Falha na conexão inicial.")
        except Exception as e:
            logging.error(f"Tentativa {attempt+1} falhou: {e}")
        attempt += 1
        await asyncio.sleep(1)  # Espera antes de tentar novamente
    
    logging.error(f"Atingido o número máximo de tentativas ({max_attempts}). Não foi possível conectar ao IQ Option.")
    return None

def get_symbols(Iq):
    if check_assets == 0:
        return assets

    all_asset = Iq.get_all_open_time()
    all_assets_list = []
    for market_type in ['binary', 'digital']:
        if market_type in all_asset:
            for asset_name, details in all_asset[market_type].items():
                asset_name_without_op = asset_name.replace('-op', '')
                if asset_name_without_op.endswith('OTC'):
                    all_assets_list.append(asset_name_without_op)
    return all_assets_list

async def get_candles(Iq, symbol, timeframe, count):
    try:
        return Iq.get_candles(symbol, timeframe, count, time.time())
    except Exception as e:
        logging.error(f"Erro ao obter velas para {symbol}: {e}")
        return None

async def format_candles(symbol, timeframe_text, candles):
    utc_to_brasilia = timedelta(hours=-3)
    current_time = time.time()

    if candles and candles[-1]['to'] > current_time:
        candles.pop()

    try:
        cursor = conn.cursor()

        for candle in candles:
            time_brasilia = datetime.utcfromtimestamp(candle['from']) + utc_to_brasilia
            time_str = time_brasilia.strftime('%Y-%m-%d %H:%M:%S')
            
            open_price = candle['open'] if candle['open'] is not None else 0
            high_price = candle['max'] if candle['max'] is not None else 0
            low_price = candle['min'] if candle['min'] is not None else 0
            close_price = candle['close'] if candle['close'] is not None else 0
            tick_volume = candle['volume'] if candle['volume'] is not None else 0

            cursor.execute("SELECT COUNT(*) FROM candle_history WHERE symbol = %s AND timeframe = %s AND time = %s", (symbol, timeframe_text, time_str))
            count = cursor.fetchone()[0]
            
            if count == 0:
                cursor.execute("""
                    INSERT INTO candle_history (symbol, timeframe, time, open, high, low, close, tick_volume, spread, real_volume, source) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (symbol, timeframe_text, time_str, open_price, high_price, low_price, close_price, tick_volume, "0", "0", "IQ Option"))
                logging.info("Vela inserida com sucesso: %s, %s, %s, %f, %f, %f, %f, %d, %s", 
                             symbol, timeframe_text, time_str, open_price, high_price, low_price, close_price, tick_volume, "IQ Option")
                conn.commit()  # Commit da transação para cada vela

        
    except mysql.connector.Error as e:
        logging.error(f"Erro ao inserir dados das velas no banco de dados: {e}")
        await reconnect_db()  # Tentar reconectar ao banco de dados se falhar
        
    finally:
        if 'cursor' in locals() and cursor.is_connected():
            cursor.close()  # Fechar o cursor

async def main():
    global conn
    await reconnect_db()
    logging.info("Buscando Candles")
    Iq = await connect_to_iqoption()
    if not Iq or not Iq.check_connect():
        logging.error("Falha ao conectar ao IQ Option. Encerrando.")
        return

    symbols = get_symbols(Iq)
    logging.info("Símbolos: %s", symbols)

    timeframes = {
        "M1": 60,
        "M5": 300,
        "M15": 900,
        "M30": 1800
    }

    while True:
        try:
            if not Iq.check_connect():
                logging.warning("Desconectado. Tentando reconectar.")
                Iq = await connect_to_iqoption()
                if not Iq or not Iq.check_connect():
                    logging.error("Falha ao reconectar. Tentando novamente em 1 segundo.")
                    await asyncio.sleep(1)
                    continue

            tasks = []
            for symbol in symbols:
                for timeframe_text, timeframe_seconds in timeframes.items():
                    tasks.append(handle_symbol_timeframe(Iq, symbol, timeframe_text, timeframe_seconds))

            await asyncio.gather(*tasks)
            await asyncio.sleep(1)

        except Exception as e:
            logging.error(f"Ocorreu um erro: {e}. Tentando novamente em 1 segundo.")
            await asyncio.sleep(1)

async def handle_symbol_timeframe(Iq, symbol, timeframe_text, timeframe_seconds):
    candles = await get_candles(Iq, symbol, timeframe_seconds, 1000)
    if candles:
        await format_candles(symbol, timeframe_text, candles)

if __name__ == "__main__":
    asyncio.run(main())
