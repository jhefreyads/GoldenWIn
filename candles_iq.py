from iqoptionapi.stable_api import IQ_Option, OP_code
import pandas as pd
from datetime import datetime, timedelta, timezone
import time
from db_connection import get_connection
from configparser import ConfigParser
from concurrent.futures import ThreadPoolExecutor, as_completed
from iq_connection import connect_to_iqoption
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import ativos_iq
import os
import json
import math


# Configuração
config = ConfigParser()
config.read('config.ini')
iq_symbols = config.get('Candles', 'iq_symbols').split(', ')
mt5_symbols = config.get('Candles', 'mt5_symbols').split(', ')

num_candles = int(config.get('Candles', 'num_candles'))
timeframes_conf_str = config.get('Candles', 'timeframes')  # Exemplo: '1, 5, 15'
timeframes_conf = [int(x) for x in timeframes_conf_str.split(', ')]
login = config.get('API', 'iq_login')
password = config.get('API', 'iq_password')
# Mapeamento dos intervalos de tempo
timeframe_mapping = {
    1: 'M1',
    5: 'M5',
    15: 'M15',
    30: 'M30',
    60: 'H1',
    1440: 'D1'
}
# Carregar o arquivo JSON
with open('json/all_symbols.json', 'r') as file:
    data = json.load(file)
# Obter somente a lista de "actives" (chaves do dicionário)
all_symbols = list(data.keys())

def connect_to_database():
    while True:
        try:
            global conn
            conn = get_connection()
            return conn
        except Exception as e:
            print(f"Erro ao conectar ao banco de dados: {e}. Tentando novamente em 2 segundos...")
            time.sleep(2)



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

def get_candle_history(Iq, symbol, timeframe_minutes, num_candles, last_timestamp):
    try:
        # Converte last_timestamp de string para float (timestamp)
        if isinstance(last_timestamp, str):
            # Supondo que a string esteja no formato 'YYYY-MM-DD HH:MM:SS'
            dt = datetime.strptime(last_timestamp, '%Y-%m-%d %H:%M:%S')
            last_timestamp = dt.timestamp()  # Converte para float (timestamp em segundos)
        else:
            last_timestamp = float(last_timestamp)

        if timeframe_minutes not in timeframe_mapping:
            print("Intervalo de tempo não suportado:", timeframe_minutes)
            return None

        # Calcula o intervalo de tempo em segundos
        timeframe_sec = timeframe_minutes * 60
        
        # Obtém o timestamp atual
        now = time.time()
        
        # Calcula a diferença em segundos entre o last_timestamp e o now
        time_diff = now - last_timestamp
        
        # Calcula o número de candles a serem buscados, arredondando para cima
        required_candles = math.ceil(time_diff / timeframe_sec)
        
        # Define o número de candles a serem buscados como o menor entre required_candles e num_candles
        candles_to_fetch = min(required_candles, num_candles)

        # Buscamos uma vela extra para garantir que estamos excluindo a vela mais recente
        candles = Iq.get_candles(symbol, timeframe_sec, candles_to_fetch + 1, now)
        
        # Verifica se há dados retornados
        if candles is None or len(candles) == 0:
            print("Nenhum dado de vela retornado.")
            return None

        # Remover a última vela (vela atual que ainda não fechou)
        candles = candles[:-1]

        utc_to_brasilia = timedelta(hours=-3)
        df = pd.DataFrame(candles)
        df['time'] = df['from'].apply(lambda x: pd.Timestamp.fromtimestamp(x, tz=timezone.utc) + utc_to_brasilia)
        
        # Verifica se o intervalo de tempo entre as velas é consistente com o timeframe solicitado
        df['time_diff'] = df['time'].diff().dt.total_seconds().fillna(0)
        expected_time_diff = timeframe_minutes * 60  # Diferença de tempo esperada em segundos
        
        # Filtra as velas que não têm o intervalo de tempo correto
        df = df[df['time_diff'] == expected_time_diff].copy()
        if df.empty:
            return None

        df['open'] = df['open'].fillna(0)
        df['high'] = df['max'].fillna(0)
        df['low'] = df['min'].fillna(0)
        df['close'] = df['close'].fillna(0)
        df['volume'] = df['volume'].fillna(0)
        df['spread'] = df['high'] - df['low']

        return df
    except Exception as e:
        print("Erro ao obter o histórico de velas:", e)
        return None


def insert_candle_data(conn, symbol, timeframe_minutes, df):
    timeframe_text = timeframe_mapping.get(timeframe_minutes, str(timeframe_minutes))
    now = datetime.now()

    if symbol.endswith("-OTC"):
        source = "otc"
    else:
        source = "mt5"

    try:
        cursor = conn.cursor()
        for _, row in df.iterrows():
            time_str = row['time'].strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute("SELECT COUNT(*) FROM candle_history WHERE symbol = %s AND timeframe = %s AND time = %s",
                           (symbol, timeframe_text, time_str))
            count = cursor.fetchone()[0]

            if count == 0:
                cursor.execute("""
                    INSERT INTO candle_history (symbol, timeframe, time, open, high, low, close, tick_volume, spread, real_volume, source, inserted)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (symbol, timeframe_text, time_str, row['open'], row['high'], row['low'], row['close'], row['volume'], row['spread'], "0", source, now))
                conn.commit()
                print(f"Vela inserida com sucesso: {symbol}, {timeframe_text}, {time_str}")
    except Exception as e:
        print(f"Erro ao inserir dados das velas no banco de dados: {e}")

def process_symbol_timeframe(Iq, conn, symbol, timeframe_minutes, last_timestamp):
    candle_history = get_candle_history(Iq, symbol, timeframe_minutes, num_candles, last_timestamp)
    if candle_history is not None:
        if last_timestamp is not None:
            last_timestamp = pd.Timestamp(last_timestamp).tz_localize(None)
            candle_history['time'] = pd.to_datetime(candle_history['time']).dt.tz_localize(None)
            candle_history = candle_history[candle_history['time'] > last_timestamp]

        if not candle_history.empty:
            insert_candle_data(conn, symbol, timeframe_minutes, candle_history)

def get_symbols_with_null_result():
    conn = connect_to_database()
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

def get_symbols():
    try:
        print("Buscando Ativos")
        # ConfigParser para manipular o arquivo de configuração
        config = ConfigParser()
        config.read('config.ini')  # Nome do arquivo de configuração

        # Lendo as listas existentes no arquivo de configuração, removendo espaços e valores vazios
        iq_symbols = [symbol.strip() for symbol in config.get('Candles', 'iq_symbols').split(',') if symbol.strip()]
        mt5_symbols = [symbol.strip() for symbol in config.get('Candles', 'mt5_symbols').split(',') if symbol.strip()]

        # Função para remover '-op' de um símbolo
        def remove_op_suffix(symbol):
            return symbol[:-3] if symbol.endswith('-op') else symbol

        for symbol in all_symbols:
            if symbol.endswith('-OTC'):
                if symbol not in iq_symbols:  # Adiciona ao iq_symbols se ainda não estiver
                    iq_symbols.append(symbol)
            else:
                symbol = remove_op_suffix(symbol)
                if symbol not in mt5_symbols:  # Adiciona ao mt5_symbols se ainda não estiver
                    mt5_symbols.append(symbol)
        # Atualizando o arquivo de configuração
        config.set('Candles', 'iq_symbols', ', '.join(iq_symbols))
        config.set('Candles', 'mt5_symbols', ', '.join(mt5_symbols))

        with open('config.ini', 'w') as configfile:
            config.write(configfile)

        symbols_config = [symbol for symbol in (iq_symbols + mt5_symbols) if symbol]

        # Obtendo os ativos disponíveis e validando
        symbols_iq = ativos_iq.get_open_assets()
        validated_symbols = [symbol for symbol in symbols_iq if symbol in symbols_config]

        # Separando os ativos entre OTC e não-OTC
        for symbol in validated_symbols:
            if symbol.endswith('-OTC'):
                if symbol not in iq_symbols:  # Adiciona ao iq_symbols se ainda não estiver
                    iq_symbols.append(symbol)
            else:
                if symbol not in mt5_symbols:  # Adiciona ao mt5_symbols se ainda não estiver
                    mt5_symbols.append(symbol)

    
        # Unindo as listas e removendo valores vazios
        print(f"Ativos encontrados e atualizados no arquivo de configuração: {validated_symbols}")

    except Exception as e:
        # Caso ocorra um erro, usa os símbolos padrões
        symbols = [symbol for symbol in (iq_symbols + mt5_symbols) if symbol]
        print(f"Utilizando Ativos padrões: {symbols}")
        error = f"IA: Erro ao buscar os Ativos: {e}"
        print(error)

    # Salvando os símbolos em um arquivo JSON
    try:
        # Define o diretório onde o arquivo JSON será salvo
        json_directory = 'json'  # Caminho relativo ou absoluto
        if not os.path.exists(json_directory):
            os.makedirs(json_directory)

        # Salva os símbolos no arquivo
        with open(os.path.join(json_directory, 'symbols.json'), 'w') as json_file:
            json.dump(validated_symbols, json_file, indent=4)

        print(f"Ativos salvos no arquivo: {os.path.join(json_directory, 'symbols.json')}")
    except Exception as file_error:
        error = f"IA: Erro ao salvar arquivo JSON: {file_error}"
        print(error)

def main():
    Iq = connect_to_iqoption()
    
    if not Iq:
        raise Exception("Falha na conexão com o IQ Option.")
    get_symbols()
    scheduler = BackgroundScheduler()
    scheduler.add_job(get_symbols, IntervalTrigger(minutes=10))
    scheduler.start()
    print("Iniciando captura de Candles")

    max_threads = 1  # Ajuste o número de threads para 4
    

    with ThreadPoolExecutor(max_threads) as executor:
        while True:
            try:
                futures = []
                timeframes = timeframes_conf  # Em minutos

                # Processar símbolos prioritários
                priority_symbols = get_symbols_with_null_result()
                for symbol in priority_symbols:
                    if symbol is None or symbol == "":
                        continue
                    for timeframe_minutes in timeframes:
                        conn = connect_to_database()
                        cursor = conn.cursor()
                        
                        # Obter o último timestamp do banco de dados
                        cursor.execute(
                            "SELECT MAX(time) FROM candle_history WHERE symbol = %s AND timeframe = %s",
                            (symbol, timeframe_mapping.get(timeframe_minutes, str(timeframe_minutes)))
                        )
                        last_timestamp = cursor.fetchone()[0]
                        
                        # Se não houver timestamp no banco, calcular o início com base no número de candles e período
                        if last_timestamp is None:
                            # Calcular o período inicial baseado no horário atual
                            end_time = datetime.now()
                            start_time = end_time - timedelta(minutes=timeframe_minutes * num_candles)
                            last_timestamp = start_time.strftime('%Y-%m-%d %H:%M:%S')  # Formatar para o banco de dados

                        futures.append(
                            executor.submit(
                                process_symbol_timeframe, Iq, conn, symbol, timeframe_minutes, last_timestamp
                            )
                        )
                symbols = load_symbols()
                # Processar símbolos restantes
                for symbol in symbols:
                    if symbol is None or symbol == "":
                        continue
                    for timeframe_minutes in timeframes:
                        conn = connect_to_database()
                        cursor = conn.cursor()
                        
                        # Obter o último timestamp do banco de dados
                        cursor.execute(
                            "SELECT MAX(time) FROM candle_history WHERE symbol = %s AND timeframe = %s",
                            (symbol, timeframe_mapping.get(timeframe_minutes, str(timeframe_minutes)))
                        )
                        last_timestamp = cursor.fetchone()[0]
                        
                        # Se não houver timestamp no banco, calcular o início com base no número de candles e período
                        if last_timestamp is None:
                            # Calcular o período inicial baseado no horário atual
                            end_time = datetime.now()
                            start_time = end_time - timedelta(minutes=timeframe_minutes * num_candles)
                            last_timestamp = start_time.strftime('%Y-%m-%d %H:%M:%S')  # Formatar para o banco de dados

                        futures.append(
                            executor.submit(
                                process_symbol_timeframe, Iq, conn, symbol, timeframe_minutes, last_timestamp
                            )
                        )
                open_symbols = iq_symbols + mt5_symbols
                # Processar símbolos restantes
                for symbol in open_symbols:
                    if symbol is None or symbol == "":
                        continue
                    for timeframe_minutes in timeframes:
                        conn = connect_to_database()
                        cursor = conn.cursor()
                        
                        # Obter o último timestamp do banco de dados
                        cursor.execute(
                            "SELECT MAX(time) FROM candle_history WHERE symbol = %s AND timeframe = %s",
                            (symbol, timeframe_mapping.get(timeframe_minutes, str(timeframe_minutes)))
                        )
                        last_timestamp = cursor.fetchone()[0]
                        
                        # Se não houver timestamp no banco, calcular o início com base no número de candles e período
                        if last_timestamp is None:
                            # Calcular o período inicial baseado no horário atual
                            end_time = datetime.now()
                            start_time = end_time - timedelta(minutes=timeframe_minutes * num_candles)
                            last_timestamp = start_time.strftime('%Y-%m-%d %H:%M:%S')  # Formatar para o banco de dados

                        futures.append(
                            executor.submit(
                                process_symbol_timeframe, Iq, conn, symbol, timeframe_minutes, last_timestamp
                            )
                        )

                
            except Exception as e:
                    print(f"Erro durante a execução paralela: {e}")


            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    print(f"Erro durante a execução paralela: {e}")

if __name__ == "__main__":
    main()