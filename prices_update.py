from datetime import datetime, timedelta
import json
import os
import pytz  # Biblioteca para manipulação de timezones
import time as t
from db_connection import get_connection
from configparser import ConfigParser
from iq_connection import connect_to_iqoption
from iqoptionapi.stable_api import IQ_Option
import asyncio
import ccxt
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from concurrent.futures import ThreadPoolExecutor

# Configuração
config = ConfigParser()
config.read('config.ini')
iq_symbols = config.get('Candles', 'iq_symbols').split(', ')
mt5_symbols = config.get('Candles', 'mt5_symbols').split(', ')
binance_symbols = config.get('Candles', 'binance_symbols').split(', ')
timeframes_conf_str = config.get('Candles', 'timeframes_ia')  # Exemplo: '1, 5, 15'
timeframes_conf = [int(x) for x in timeframes_conf_str.split(', ')]
iq = connect_to_iqoption()
exchange = ccxt.binance()
logging.basicConfig()
logging.getLogger('apscheduler').setLevel(logging.ERROR)
scheduler = BackgroundScheduler()

def connect_to_database():
    global conn
    conn = get_connection()


def load_symbols():
    json_file_path = 'json/symbols.json'  # Caminho relativo para o arquivo JSON

    # Verifica se o arquivo existe
    if not os.path.exists(json_file_path):
        print("Arquivo JSON não encontrado. Retornando lista vazia.")
        return []  # Retorna uma lista vazia se o arquivo não existir

    try:
        with open(json_file_path, 'r') as json_file:
            symbols = json.load(json_file)  # Carrega os símbolos do arquivo
            return symbols
    except Exception as e:
        error = f"IA: Erro ao carregar arquivo JSON: {e}"
        print(error)
        return []  # Retorna uma lista vazia em caso de erro
    
def get_symbols_with_null_result():
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT symbol
            FROM trading_signals
            WHERE result IS NULL
        """)
        rows = cursor.fetchall()
        return [row[0] for row in rows]
    except Exception as e:
        print(f"Erro ao buscar símbolos prioritários: {e}")
        return []    





def is_within_trading_hours():
    # Timezone São Paulo
    timezone = pytz.timezone('America/Sao_Paulo')
    now = datetime.now(timezone)
    
    # Definindo o horário de início (domingo 20h) e fim (sexta 17h)
    start_time = now.replace(hour=17, minute=0, second=0, microsecond=0)
    end_time = now.replace(hour=17, minute=30, second=0, microsecond=0)

    # Se hoje for domingo, verificar se a hora atual é após 20:00
    if now.weekday() == 6:
        if now.time() >= start_time.time():
            return True

    # Se hoje for sexta-feira, verificar se a hora atual é antes de 17:00
    elif now.weekday() == 4:
        if now.time() <= end_time.time():
            return True

    # Se for um dia entre segunda e quinta-feira, sempre dentro do horário
    elif 0 <= now.weekday() <= 3:
        return True

    # Qualquer outro horário é considerado fora do horário de negociação
    return False



# Armazena os ativos e timeframes que já foram feitos o streaming
processed_streams = set()

def start_stream(symbol, timeframe):
    # Gera uma chave única para cada combinação de ativo e timeframe
    stream_key = (symbol, timeframe)

    # Verifica se o streaming já foi feito para esse ativo/timeframe
    if stream_key not in processed_streams:
        size = timeframe * 60  # Converter o timeframe para segundos
        iq.start_candles_stream(symbol, size, 10)  # Inicia o streaming para o símbolo e timeframe
        processed_streams.add(stream_key)  # Marca o streaming como iniciado
        print(f"Streaming do ativo {symbol}, timeframe M{timeframe} iniciado")


def start_stream_for_all_symbols():
    global symbols, timeframes_conf

    if iq is None:
        connect_to_iqoption()

    # Define o número máximo de threads simultâneas
    with ThreadPoolExecutor(max_workers=10) as executor:
        # Inicia o streaming para cada símbolo e timeframe em threads separadas
        for symbol in symbols:
            for timeframe in timeframes_conf:
                executor.submit(start_stream, symbol, timeframe)




def stop_stream_for_all_symbols():
    global symbols, timeframes_conf

    for symbol in symbols:
        if symbol is None or symbol == "":
            continue
        for timeframe in timeframes_conf:
            size = timeframe * 60  # Converter o timeframe para segundos
            iq.stop_candles_stream(symbol, size)

def get_current_prices_and_open_prices():
    global symbols, timeframes_conf

    results = {}

    for symbol in symbols:
        if symbol is None or symbol == "":
            continue
        for timeframe in timeframes_conf:
            size = timeframe * 60  # Converter o timeframe para segundos
            candles = iq.get_realtime_candles(symbol, size)
            if candles is None or len(candles) == 0:
                print(f"Erro ao obter candles do ativo {symbol}")
                continue

            # Obter a última vela, que é a mais recente
            last_candle = candles[list(candles.keys())[-1]]
            # Obter preços da vela
            open_price = last_candle['open']  # Preço de abertura
            close_price = last_candle['close']  # Preço de fechamento
            high_price = last_candle['max']  # Preço mais alto
            low_price = last_candle['min']  # Preço mais baixo
            open_time_s = last_candle['from']

            # Se for string, converta para float
            if isinstance(open_time_s, str):
                try:
                    open_time_s = float(open_time_s)
                except ValueError:
                    raise TypeError(f"Não é possível converter open_time para float: {open_time_s}")

            # Converter para datetime em UTC
            open_time_dt = datetime.utcfromtimestamp(open_time_s)
            # Subtrair 3 horas para ajustar ao horário de Brasília (UTC-3)
            open_time_br = open_time_dt - timedelta(hours=3)

            # Formatar para HH:MM no horário de Brasília
            open_time = open_time_br.strftime('%Y-%m-%d %H:%M:%S')

            # Armazenar resultados
            if symbol not in results:
                results[symbol] = {}
            results[symbol][timeframe] = (symbol, timeframe, open_time, close_price, open_price, high_price, low_price)

    return results

def update_iq_prices():
    prices = get_current_prices_and_open_prices()
    cursor = conn.cursor()

    for symbol, timeframes in prices.items():
        if symbol is None or symbol == "":
            continue
        for timeframe, (symbol, timeframe, formatted_open_time, current_price, open_price, high_price, low_price) in timeframes.items():

            # Modificar a atribuição de timeframe_label
            if timeframe == 60:
                timeframe_label = "H1"
            else:
                timeframe_label = f"M{timeframe}"


            # Formatando os preços com 6 casas decimais
            formatted_open_price = f"{open_price:.6f}"
            formatted_current_price = f"{current_price:.6f}"
            formatted_high_price = f"{high_price:.6f}"
            formatted_low_price = f"{low_price:.6f}"
            if symbol.endswith('-OTC'):
                source = 'OTC'
            else:
                source = 'Forex'

            # Verificar se o registro existe
            cursor.execute("""
                SELECT id FROM trading_data 
                WHERE symbol = %s AND timeframe = %s
            """, (symbol, timeframe_label))
            result = cursor.fetchone()

            if result:
                # Atualizar registro existente
                cursor.execute("""
                    UPDATE trading_data
                    SET open_price = %s, current_price = %s, open_time = %s, high_price = %s, low_price = %s
                    WHERE id = %s
                """, (formatted_open_price, formatted_current_price, formatted_open_time, formatted_high_price, formatted_low_price, result[0]))
                print(f"Atualizado {symbol} {timeframe_label} às {formatted_open_time} (São Paulo)")
            else:
                # Inserir novo registro
                cursor.execute("""
                    INSERT INTO trading_data (symbol, timeframe, open_price, current_price, open_time, high_price, low_price, source)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (symbol, timeframe_label, formatted_open_price, formatted_current_price, formatted_open_time, formatted_high_price, formatted_low_price, source,))
                print(f"Inserido {symbol} {timeframe_label} às {formatted_open_time} (São Paulo)")

            conn.commit()



if __name__ == "__main__":
    connect_to_database()
    print("Iniciando atualização dos preços")
    while True:
        json_symbols = load_symbols()
        null_symbols = get_symbols_with_null_result()
        symbols = json_symbols + null_symbols
        start_stream_for_all_symbols()
        update_iq_prices()
        t.sleep(2)

