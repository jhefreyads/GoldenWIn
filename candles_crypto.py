import requests
import pandas as pd
from datetime import datetime, timedelta
import time
from db_connection import get_connection
from configparser import ConfigParser
from concurrent.futures import ThreadPoolExecutor, as_completed

# Configuração
config = ConfigParser()
config.read('config.ini')
binance_symbols = config.get('Candles', 'binance_symbols').split(', ')
num_candles = int(config.get('Candles', 'num_candles'))
timeframes_conf_str = config.get('Candles', 'timeframes')  # Exemplo: '1, 5, 15'
timeframes_conf = [int(x) for x in timeframes_conf_str.split(', ')]

def connect_to_database():
    global conn
    conn = get_connection()

# Mapeamento dos intervalos de tempo da Binance
timeframe_mapping = {
    1: '1m',
    5: '5m',
    15: '15m',
    30: '30m',
    60: '1h',
    1440: '1d'
}

timeframe_mapping_text = {
    1: 'M1',
    5: 'M5',
    15: 'M15',
    30: 'M30',
    60: 'H1',
    1440: 'D1'
}

# Função para obter o histórico de velas da Binance
def get_candle_history(symbol, timeframe_minutes, num_candles):
    try:
        timeframe = timeframe_mapping.get(timeframe_minutes)
        if not timeframe:
            print("Intervalo de tempo não suportado:", timeframe_minutes)
            return None

        url = f"https://api.binance.com/api/v3/klines"
        params = {
            'symbol': symbol,
            'interval': timeframe,
            'limit': num_candles + 1  # Para pegar a vela mais recente que está aberta
        }
        response = requests.get(url, params=params)
        data = response.json()

        # Convertendo para DataFrame
        df = pd.DataFrame(data, columns=['time', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'quote_asset_volume', 'number_of_trades', 'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'])
        df['time'] = pd.to_datetime(df['time'], unit='ms')
        df['time'] = df['time'] - pd.Timedelta(hours=3)
        # Remova a última vela, pois ela ainda está aberta
        df = df.iloc[:-1]

        return df
    except Exception as e:
        print("Erro ao obter o histórico de velas:", e)
        return None

# Função para inserir os dados das velas no banco de dados
def insert_candle_data(symbol, timeframe_minutes, df):
    # Utilizando o mapeamento correto para o texto do timeframe
    timeframe_text = timeframe_mapping_text.get(timeframe_minutes, str(timeframe_minutes))
    now = datetime.now()
    try:
        cursor = conn.cursor()

        for _, row in df.iterrows():
            time_str = row['time'].strftime('%Y-%m-%d %H:%M:%S')
            
            # Conversão dos valores para tipos adequados
            open_price = float(row['open'])
            high_price = float(row['high'])
            low_price = float(row['low'])
            close_price = float(row['close'])
            tick_volume = float(row['volume'])  # Mantenha como float, não int
            spread = high_price - low_price
            
            # Checar se o volume está dentro do intervalo aceitável para o tipo de dado
            # Se precisar de volume como INTEGER e estiver enfrentando problemas de overflow, considere usar BIGINT no banco de dados
            if tick_volume < -2147483648:
                tick_volume = -2147483648
            elif tick_volume > 2147483647:
                tick_volume = 2147483647
            
            # Verificar se o registro já existe
            cursor.execute("SELECT COUNT(*) FROM candle_history WHERE symbol = %s AND timeframe = %s AND time = %s", (symbol, timeframe_text, time_str))
            count = cursor.fetchone()[0]

            if count == 0:
                cursor.execute("""
                    INSERT INTO candle_history (symbol, timeframe, time, open, high, low, close, tick_volume, spread, real_volume, source, inserted) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (symbol, timeframe_text, time_str, open_price, high_price, low_price, close_price, tick_volume, spread, "0", "crypto", now))
                
                print("Vela inserida com sucesso:", symbol, timeframe_text, time_str, open_price, high_price, low_price, close_price, tick_volume, spread, "crypto", now)

                conn.commit()

    except ValueError as ve:
        print(f"Erro de valor ao inserir dados das velas no banco de dados: {ve}")
    except Exception as e:
        print("Erro ao inserir dados das velas no banco de dados:", e)

# Função para processar um símbolo e um intervalo de tempo
def process_symbol_timeframe(symbol, timeframe_minutes):
    candle_history = get_candle_history(symbol, timeframe_minutes, num_candles)
    if candle_history is not None:
        # Filtrar apenas as velas mais recentes que não foram inseridas anteriormente
        last_timestamp = last_inserted_timestamps.get((symbol, timeframe_minutes), None)
        if last_timestamp is not None:
            candle_history = candle_history[candle_history['time'] > last_timestamp]

        if not candle_history.empty:
            insert_candle_data(symbol, timeframe_minutes, candle_history)
            # Atualizar o último timestamp inserido para este par de moedas e intervalo de tempo
            last_inserted_timestamps[(symbol, timeframe_minutes)] = candle_history['time'].max()

def should_run():
    """Verifica se o minuto atual está dentro dos intervalos permitidos (0-2 ou 5-7)."""
    current_minute = datetime.now().minute
    return (0 <= current_minute <= 2) or (5 <= current_minute <= 7)

def main():
    connect_to_database()
    
    symbols = binance_symbols
    timeframes = timeframes_conf  # Em minutos

    print("Iniciando captura de Candles")

    # Dicionário para rastrear o último timestamp de cada par de moedas e intervalo de tempo
    global last_inserted_timestamps
    last_inserted_timestamps = {}

    try:
        # Carregar os últimos timestamps inseridos do banco de dados
        cursor = conn.cursor()
        for symbol in symbols:
            for timeframe_minutes in timeframes:
                cursor.execute("SELECT MAX(time) FROM candle_history WHERE symbol = %s AND timeframe = %s", (symbol, timeframe_mapping.get(timeframe_minutes, str(timeframe_minutes))))
                last_inserted_timestamps[(symbol, timeframe_minutes)] = cursor.fetchone()[0]
    except Exception as e:
        print("Erro ao carregar os últimos timestamps inseridos do banco de dados:", e)
        return

    # Define o número máximo de threads simultâneas
    max_threads = 1
    with ThreadPoolExecutor(max_threads) as executor:
        while True:
            now = datetime.now()
            current_minute = now.minute
            current_second = now.second

            # Verificar se o minuto está dentro dos intervalos 0-2 ou 5-7 e se está no final do minuto (>=55 segundos)
            futures = []
            for symbol in symbols:
                for timeframe_minutes in timeframes:
                    futures.append(executor.submit(process_symbol_timeframe, symbol, timeframe_minutes))

            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    print("Erro durante a execução paralela:", e)

            time.sleep(1)

if __name__ == "__main__":
    main()
