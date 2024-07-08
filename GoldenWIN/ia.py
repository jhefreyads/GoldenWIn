import multiprocessing
import multiprocessing.process
import logging
import mysql.connector
from mysql.connector import Error
from configparser import ConfigParser
import pandas as pd
import ta
import time
import os
from datetime import datetime, timedelta
import warnings
import numpy as np
from calendario import check_news_for_symbol
import ativos_iq



# Configuração de logging
log_dir = "logs"
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

logging.basicConfig(
    filename=os.path.join(log_dir, 'logs_ia.log'),
    level=logging.INFO,
    format='%(asctime)s %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M'
)

warnings.filterwarnings('ignore', category=RuntimeWarning)
warnings.filterwarnings('ignore', message="Series.fillna with 'method' is deprecated.*")
warnings.filterwarnings('ignore', message="pandas only supports SQLAlchemy connectable.*")


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

# Função para reconectar ao banco de dados se a conexão falhar
def reconnect_db():
    global conn
    while True:
        try:
            conn = mysql.connector.connect(**db_config)
            if conn.is_connected():
                logging.info("Reconectado ao banco de dados com sucesso.")
                return
        except Error as e:
            logging.error("Erro ao reconectar ao banco de dados: %s", e)

def ensure_connection():
    global conn
    if conn is None or not conn.is_connected():
        reconnect_db()

def load_data(symbol, timeframe):
    try:
        ensure_connection()
        cursor = conn.cursor()
        query = f"""
        SELECT * FROM candle_history
        WHERE symbol = '{symbol}' AND timeframe = '{timeframe}'
        ORDER BY time DESC
        """
        cursor.execute(query)
        rows = cursor.fetchall()
        df = pd.DataFrame(rows, columns=[desc[0] for desc in cursor.description])
        df['time'] = pd.to_datetime(df['time'])
        cursor.close()  # Certifique-se de fechar o cursor após a execução
        return df[::-1]
    except:
        return


def load_multiple_timeframes(symbol, timeframes):
    data = {}
    for timeframe in timeframes:
        data[timeframe] = load_data(symbol, timeframe)
    return data



def calculate_indicators(df, timeframe):
    try:
        timeframe_multipliers = {
            'M1': 1,
            'M5': 5,
            'M15': 15,
            'M30': 30,
            'H1': 60,
            'H4': 240,
            'D1': 1440
        }
        multiplier = timeframe_multipliers[timeframe]

        # Verifique se há dados suficientes para calcular os indicadores
        if len(df) < 500 * multiplier:
            logging.warning(f"Not enough data to calculate indicators for {timeframe}. Skipping.")
            return df

        df['PPO'] = ta.momentum.ppo(df['close'], window_slow=93*multiplier, window_fast=26)
        df['TRIX1'] = ta.trend.trix(df['close'], window=62*multiplier)
        df['CCI'] = ta.trend.cci(df['high'], df['low'], df['close'], window=30*multiplier)
        df['ATR'] = ta.volatility.average_true_range(df['high'], df['low'], df['close'], window=21*multiplier)
        df['ROC'] = ta.momentum.roc(df['close'], window=21*multiplier)
        df['WILLR'] = ta.momentum.williams_r(df['high'], df['low'], df['close'], lbp=22*multiplier)
        df['TRIX2'] = ta.trend.trix(df['close'], window=90*multiplier)

        return df

    except:
        return df

# Dicionário para armazenar as condições específicas para cada timeframe
timeframe_conditions = {
    'M5': {'same_direction_percentage': 75},  # Correção para 75%
    'M1': {'same_direction_percentage': 75},  # Correção para 75%
    # Adicione outras timeframes conforme necessário
}


# Variáveis para os pesos dos indicadores (valores padrão atribuídos)
weights = {
    'PPO': 1.0,
    'TRIX1': 1.0,
    'CCI': 1.0,
    'ATR': 1.0,
    'ROC': 1.0,
    'WILLR': 1.0,
    'TRIX2': 1.0,
}


# Inicialize a variável previous_signal
previous_signal = 'HOLD'

def generate_signal(multi_df, timeframes):
    try:
        global previous_signal  # Declarar a variável como global

        signals = {'CALL': 0, 'PUT': 0}
        indicators = []

        for timeframe in timeframes:
            if timeframe not in multi_df:
                continue

            df = multi_df[timeframe]
            if df.empty:
                continue

        
            # Verifique o PPO
            if df['PPO'].iloc[-1] > 0:
                signals['CALL'] += 1
                indicators.append(f"{timeframe} PPO: CALL (PPO: {df['PPO'].iloc[-1]} > 0)")
            elif df['PPO'].iloc[-1] < 0:
                signals['PUT'] += 1
                indicators.append(f"{timeframe} PPO: PUT (PPO: {df['PPO'].iloc[-1]} < 0)")

            # Verifique o TRIX1
            if df['TRIX1'].iloc[-1] > 0:
                signals['CALL'] += 1
                indicators.append(f"{timeframe} TRIX1: CALL (TRIX1: {df['TRIX1'].iloc[-1]} > 0)")
            elif df['TRIX1'].iloc[-1] < 0:
                signals['PUT'] += 1
                indicators.append(f"{timeframe} TRIX1: PUT (TRIX1: {df['TRIX1'].iloc[-1]} < 0)")

            # Verifique o CCI
            if df['CCI'].iloc[-1] > 100:
                signals['CALL'] += 1
                indicators.append(f"{timeframe} CCI: CALL (CCI: {df['CCI'].iloc[-1]} > 100)")
            elif df['CCI'].iloc[-1] < -100:
                signals['PUT'] += 1
                indicators.append(f"{timeframe} CCI: PUT (CCI: {df['CCI'].iloc[-1]} < -100)")

            # Verifique o ATR
            if df['ATR'].iloc[-1] > df['ATR'].mean():
                signals['CALL'] += 1
                indicators.append(f"{timeframe} ATR: CALL (ATR: {df['ATR'].iloc[-1]} > {df['ATR'].mean()})")
            elif df['ATR'].iloc[-1] < df['ATR'].mean():
                signals['PUT'] += 1
                indicators.append(f"{timeframe} ATR: PUT (ATR: {df['ATR'].iloc[-1]} < {df['ATR'].mean()})")

            # Verifique o ROC
            if df['ROC'].iloc[-1] > 0:
                signals['CALL'] += 1
                indicators.append(f"{timeframe} ROC: CALL (ROC: {df['ROC'].iloc[-1]} > 0)")
            elif df['ROC'].iloc[-1] < 0:
                signals['PUT'] += 1
                indicators.append(f"{timeframe} ROC: PUT (ROC: {df['ROC'].iloc[-1]} < 0)")

            # Verifique o Williams %R (WILLR)
            if df['WILLR'].iloc[-1] < -80:
                signals['CALL'] += 1
                indicators.append(f"{timeframe} WILLR: CALL (WILLR: {df['WILLR'].iloc[-1]} < -80)")
            elif df['WILLR'].iloc[-1] > -20:
                signals['PUT'] += 1
                indicators.append(f"{timeframe} WILLR: PUT (WILLR: {df['WILLR'].iloc[-1]} > -20)")

            # Verifique o TRIX2
            if df['TRIX2'].iloc[-1] > 0:
                signals['CALL'] += 1
                indicators.append(f"{timeframe} TRIX2: CALL (TRIX2: {df['TRIX2'].iloc[-1]} > 0)")
            elif df['TRIX2'].iloc[-1] < 0:
                signals['PUT'] += 1
                indicators.append(f"{timeframe} TRIX2: PUT (TRIX2: {df['TRIX2'].iloc[-1]} < 0)")

        # Calcular a porcentagem de indicadores com a mesma direção
        total_weight = sum(signals.values())
        if total_weight == 0:
            return 'HOLD'

        same_direction_percentage = (max(signals.values()) / total_weight) * 100

        # Obter as condições específicas para o timeframe atual
        conditions = timeframe_conditions.get('M5', {'same_direction_percentage': 80})

        # Condição adicional para emitir o sinal
        if same_direction_percentage >= conditions['same_direction_percentage']:
            signal = max(signals, key=signals.get)  # Obter o sinal com o maior peso
            if signal != previous_signal:
                previous_signal = signal
                return signal
            else:
                return 'HOLD'
        else:
            previous_signal = 'HOLD'
            return 'HOLD'

    except:
        logging.error("Não foi possível calcular os indicadores")
        print("Não foi possível calcular os indicadores")
        return 'HOLD'

# Função para obter a lista de símbolos e timeframes do banco de dados
def get_symbols_and_timeframes():
    try:
        # Conectar ao MariaDB
        if conn is None:
            reconnect_db()

        # Tenta obter os símbolos dos ativos abertos
        logging.info("Buscando Ativos")
        symbols = ativos_iq.get_open_assets()
        logging.info(f"Ativos encontrados")
        logging.info(symbols)
        logging.info("Analisando Mercado")
    except Exception as e:
        # Em caso de erro, retorna uma lista padrão de símbolos
        logging.error(f"Erro ao buscar os Ativos: {e}")
        symbols = ["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD", "NZDUSD", "EURGBP", "EURJPY", "GBPJPY", "EURAUD", "EURCHF", "GBPCHF", "AUDJPY", "NZDJPY", "AUDNZD", "GBPAUD", "EURUSD-OTC", "GBPUSD-OTC", "USDJPY-OTC", "USDCHF-OTC", "AUDUSD-OTC", "USDCAD-OTC", "NZDUSD-OTC", "EURGBP-OTC", "EURJPY-OTC", "GBPJPY-OTC", "EURAUD-OTC", "EURCHF-OTC", "GBPCHF-OTC", "AUDJPY-OTC", "NZDJPY-OTC", "AUDNZD-OTC", "GBPAUD-OTC"]
        logging.info(f"Utilizando Ativos padrões")
        logging.info(symbols)

    try:
        if conn is None:
            reconnect_db()

        query = "SELECT DISTINCT timeframe FROM candle_history"
        cursor = conn.cursor()
        cursor.execute(query)
        timeframes = [timeframe[0] for timeframe in cursor.fetchall()]
        cursor.close()
    except Error as e:
        logging.error(f"Erro ao buscar os timeframes: {e}")
        timeframes = []

    return symbols, timeframes

  # Importe a função get_payout do módulo ativos_iq

def insert_trading_signal(symbol, timeframe, time, direction):
    cursor = conn.cursor()

    formatted_time = time.strftime("%Y-%m-%d %H:%M:%S")
    
    if check_news_for_symbol(symbol, formatted_time) is None:
        is_otc = symbol.endswith("-OTC")
        original_symbol = symbol
        if is_otc:
            symbol = symbol[:-4]

        currency1 = symbol[:3]
        currency2 = symbol[3:]
        payout = ativos_iq.get_payout(original_symbol)

        cursor.execute(
            "SELECT COUNT(*) FROM trading_signals WHERE (symbol LIKE %s OR symbol LIKE %s) AND timeframe = %s AND time = %s", 
            ('%' + currency1 + '%', '%' + currency2 + '%', timeframe, formatted_time)
        )
        existing_signal_count = cursor.fetchone()[0]
        existing_symbols = cursor.fetchall()

        if existing_signal_count == 0:
            sql = """INSERT INTO trading_signals (symbol, timeframe, time, direction, payout, sent, edited, status) VALUES (%s, %s, %s, %s, %s, NULL, NULL, "Aberto")"""
            cursor.execute(sql, (original_symbol, timeframe, formatted_time, direction, payout))
            conn.commit()
            logging.info(f"Sinal inserido com sucesso: {original_symbol}, {timeframe}, {formatted_time}, {direction}, {payout}")
        else:
            repeated_currencies = []
            for existing_symbol in existing_symbols:
                existing_symbol = existing_symbol[0]
                if currency1 in existing_symbol or currency2 in existing_symbol:
                    repeated_currencies.append(existing_symbol)

            repeated_currencies_str = ', '.join(repeated_currencies)
            logging.error(f"Uma das moedas já possui sinal: {repeated_currencies_str}")
   
    else:
        logging.error("Uma das moedas possui notícia")





# Variável para armazenar o status do horário de negociação
trading_hours_status = None

# Função para verificar se o horário atual está dentro do intervalo permitido
def is_within_trading_hours():
    global trading_hours_status  # Declarar a variável como global
    current_time = datetime.now()
    new_status = None

    # Verifica se o dia da semana é entre segunda-feira (0) e sexta-feira (4)
    if 0 <= current_time.weekday() <= 4:
        # Segunda a Quinta: 18:30 às 17:00 do próximo dia
        start_time = current_time.replace(hour=18, minute=30, second=0, microsecond=0)
        end_time = current_time.replace(hour=23, minute=59, second=59, microsecond=999)
        if current_time.time() < start_time.time():  # Antes das 18:30 do mesmo dia
            start_time = start_time - timedelta(days=1)  # Ajusta para o dia anterior
        new_status = start_time <= current_time <= end_time
    elif current_time.weekday() == 5:  # Sexta-feira
        start_time = current_time.replace(hour=18, minute=30, second=0, microsecond=0)
        end_time = current_time.replace(hour=17, minute=0, second=0, microsecond=0)
        new_status = start_time <= current_time <= end_time
    elif current_time.weekday() == 6:  # Domingo
        start_time = current_time.replace(hour=18, minute=30, second=0, microsecond=0)
        new_status = current_time >= start_time

    # Verifica se houve mudança de status
    if new_status != trading_hours_status:
        trading_hours_status = new_status
        if trading_hours_status:
            print("\rDentro do horário de negociação.", end='', flush=True)
        else:
            print("\rFora do horário de negociação. Aguardando...", end='', flush=True)
    return trading_hours_status

def main():
    global conn
    reconnect_db()
    previous_signals = {}
    last_update_time = datetime.now()
    symbols, timeframes = get_symbols_and_timeframes()

    timeframes = [tf for tf in timeframes if tf in ['M1', 'M5']]

    while True:
        current_time = datetime.now()
        if (current_time - last_update_time).total_seconds() >= 1800:
            symbols, timeframes = get_symbols_and_timeframes()
            timeframes = [tf for tf in timeframes if tf in ['M1', 'M5']]
            last_update_time = current_time    

        for symbol in symbols:
            multi_df = load_multiple_timeframes(symbol, timeframes)
            multi_df = {tf: calculate_indicators(df, tf) for tf, df in multi_df.items() if not df.empty}

            if all(df.empty for df in multi_df.values()):
                continue

            for timeframe in timeframes:
                if timeframe not in multi_df:
                    continue
                
                signal = generate_signal(multi_df, [timeframe])
                if signal != 'HOLD' and ((symbol, timeframe) not in previous_signals or signal != previous_signals[(symbol, timeframe)]):
                    previous_signals[(symbol, timeframe)] = signal

                    if timeframe == 'M1':
                        next_candle_time = multi_df[timeframe]['time'].iloc[-1] + timedelta(minutes=1*3)
                    elif timeframe == 'M5':
                        next_candle_time = multi_df[timeframe]['time'].iloc[-1] + timedelta(minutes=3)
                        rounded_minute = next_candle_time.minute
                        if rounded_minute % 5 != 0:
                            next_candle_time += timedelta(minutes=5 - (rounded_minute % 5))

                    insert_trading_signal(symbol, timeframe, next_candle_time, signal)

            time.sleep(1)
        time.sleep(1)

if __name__ == "__main__":
    main()