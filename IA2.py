import numpy as np
import random
import pandas as pd
from sqlalchemy import create_engine
import pickle
from calendario import check_news_for_symbol
import ativos_iq
from db_connection import get_engine, get_connection
from configparser import ConfigParser
import ta
import warnings
import talib
import pandas as pd
import os
import time
from datetime import datetime, timedelta
import telebot
from telegrambot import send_message
import json
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import pandas_market_calendars as mcal




def connect_to_database():
    while True:
        try:
            global conn
            conn = get_connection()
            return conn
        except Exception as e:
            print(f"Erro ao conectar ao banco de dados: {e}. Tentando novamente em 2 segundos...")
            time.sleep(2)


# Carregar configuração do arquivo config.ini
config = ConfigParser()
config.read('config.ini')
scheduler = BackgroundScheduler()
# Variável global para armazenar sinais emitidos
emitted_signals = {}


# Carregar símbolos e timeframes da configuração
binance_symbols = config.get('Candles', 'binance_symbols').split(', ')
iq_symbols = config.get('Candles', 'iq_symbols').split(', ')
mt5_symbols = config.get('Candles', 'mt5_symbols').split(', ')
admin_chat_id = config.get('Telegram', 'admin_chat_id')
TOKEN_ALERT = config.get('Telegram', 'TOKEN_ALERT')
bot_alert = telebot.TeleBot(TOKEN_ALERT)
sinais_free = config.getint('Scripts', 'Sinais_free')
timeframes_conf_str = config.get('Candles', 'timeframes_ia')  # Exemplo: '1, 5, 15'
timeframes_number = [int(x.strip()) for x in timeframes_conf_str.split(',')]
timeframe_mapping = {1: 'M1', 5: 'M5', 15: 'M15'}
timeframe_mapping2 = {
    'M1': 1,
    'M5': 5,
    'M15': 15
}
timeframes = [timeframe_mapping[tf] for tf in timeframes_number if tf in timeframe_mapping]


def load_symbols_from_json():
    try:
        # Caminho do arquivo JSON
        json_file_path = os.path.join('json', 'symbols.json')
        
        if os.path.exists(json_file_path):
            with open(json_file_path, 'r') as json_file:
                symbols = json.load(json_file)
            return symbols
        else:
            print("Arquivo JSON não encontrado, retornando lista vazia.")
            return []
    except Exception as file_error:
        error = f"Erro ao carregar arquivo JSON: {file_error}"
        send_message(bot_alert, admin_chat_id, error)
        print(error)
        return []


def load_recent_data(symbol, timeframe, num_candles=200):
    try:
        cursor = conn.cursor()

        # Consulta dados históricos
        query_candles = """
            SELECT time, open, close, high, low, tick_volume 
            FROM candle_history 
            WHERE symbol = %s AND timeframe = %s 
            ORDER BY time DESC 
            LIMIT %s
        """
        cursor.execute(query_candles, (symbol, timeframe, num_candles))
        candles_data = cursor.fetchall()
        candles_data_df = pd.DataFrame(candles_data, columns=['time', 'open', 'close', 'high', 'low', 'tick_volume'])

        # Consulta dados mais recentes do trading_data
        query_trading_data = """
            SELECT open_price, current_price, open_time, high_price, low_price 
            FROM trading_data 
            WHERE symbol = %s AND timeframe = %s 
            ORDER BY open_time DESC 
            LIMIT 1
        """
        cursor.execute(query_trading_data, (symbol, timeframe))
        recent_trading_data = cursor.fetchone()

        
        if recent_trading_data:
            try:
                recent_data = {
                    'time': recent_trading_data[2],
                    'open': recent_trading_data[0],
                    'close': recent_trading_data[1],
                    'high': recent_trading_data[3],
                    'low': recent_trading_data[4],
                    'tick_volume': None
                }
        
                # Concatena com os dados históricos
                candles_data_df = pd.concat([pd.DataFrame([recent_data]), candles_data_df], ignore_index=True)
            except Exception as e:
                print(f"Erro ao processar dados recentes: {e}")

        return candles_data_df

    except Exception as e:
        error = f"Erro ao buscar os dados de velas: {e}"
        send_message(bot_alert, admin_chat_id, error)
        print(error)
        return None




        
def get_high_low_levels(symbol, timeframe, num_candles=40):
    timeframe_map = {
        'M1': 'H1',  # Suporte/Resistência de 15 min para M1
        'M5': 'H1',  # Suporte/Resistência de 30 min para M5
        'M15': 'H1'   # Suporte/Resistência de 1H para M15
    }
    higher_timeframe = timeframe_map[timeframe]
    
    try:
        # Query para buscar os candles no banco de dados
        query = """
            SELECT time, high, low 
            FROM candle_history 
            WHERE symbol = %s AND timeframe = %s 
            ORDER BY time DESC 
            LIMIT %s
        """
        
        # Executando a consulta com conn.cursor()
        cursor = conn.cursor()
        cursor.execute(query, (symbol, higher_timeframe, num_candles))
        
        # Obtendo os dados da consulta
        rows = cursor.fetchall()
        
        # Fechando o cursor
        cursor.close()
        
        # Transformando os dados em um DataFrame
        columns = ['time', 'high', 'low']
        data = pd.DataFrame(rows, columns=columns)
        
        # Convertendo as colunas 'high' e 'low' para numérico
        data['high'] = pd.to_numeric(data['high'], errors='coerce')
        data['low'] = pd.to_numeric(data['low'], errors='coerce')
        
        # Encontrar os 3 maiores topos e 3 maiores fundos
        top_highs = data.nlargest(3, 'high')
        top_lows = data.nsmallest(3, 'low')

        # Organizando os dados no formato desejado
        high_low_list = [
            f"high: {row['high']:.5f}; low: {row['low']:.5f}"
            for _, row in pd.concat([top_highs, top_lows]).iterrows()
        ]
        
        return high_low_list
    except Exception as e:
        error = f"Erro ao buscar dados para {symbol} no timeframe {timeframe}: {e}"
        send_message(bot_alert, admin_chat_id, error)
        print(error)
        return None

def calculate_rsi(symbol, timeframe, period=14):
    """
    Calcula o Índice de Força Relativa (RSI).
    """
    try:
        data = load_recent_data(symbol, timeframe)
        if data is None or len(data) < period:
            return None  # Dados insuficientes

        close_diff = data['close'].diff()  # Diferença de fechamento
        gain = close_diff.clip(lower=0)  # Apenas ganhos
        loss = -close_diff.clip(upper=0)  # Apenas perdas

        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return rsi.iloc[-1]  # Último valor calculado como número
    except Exception as e:
        print(f"Erro ao calcular RSI para {symbol} no timeframe {timeframe}: {e}")
        return None


def calculate_macd(symbol, timeframe, fast_period=12, slow_period=26, signal_period=9):
    """
    Calcula o MACD (Moving Average Convergence Divergence).
    """
    try:
        data = load_recent_data(symbol, timeframe)
        if data is None or len(data) < max(fast_period, slow_period):
            return None  # Dados insuficientes

        ema_fast = data['close'].ewm(span=fast_period, adjust=False).mean()
        ema_slow = data['close'].ewm(span=slow_period, adjust=False).mean()
        macd_line = ema_fast - ema_slow  # Linha MACD
        signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()  # Linha de sinal

        # Retorna tanto a linha MACD quanto a linha de sinal
        return macd_line.iloc[-1], signal_line.iloc[-1]  # Últimos valores
    except Exception as e:
        print(f"Erro ao calcular MACD para {symbol} no timeframe {timeframe}: {e}")
        return None



def calculate_bollinger_bands(symbol, timeframe, period=20, std_dev=2):
    """
    Calcula as Bandas de Bollinger.
    """
    try:
        data = load_recent_data(symbol, timeframe)
        if data is None or len(data) < period:
            return None  # Dados insuficientes

        sma = data['close'].rolling(window=period).mean()  # Média móvel
        std = data['close'].rolling(window=period).std()  # Desvio padrão

        upper_band = sma + (std_dev * std)  # Banda superior
        lower_band = sma - (std_dev * std)  # Banda inferior

        # Verifica se as bandas superior e inferior são válidas (não nulas)
        if upper_band.iloc[-1] is None or lower_band.iloc[-1] is None:
            print(f"Bandas de Bollinger inválidas para {symbol} no timeframe {timeframe}")
            return None

        # Retorna as bandas superior e inferior como números
        return upper_band.iloc[-1], lower_band.iloc[-1]  # Últimos valores numéricos
    except Exception as e:
        print(f"Erro ao calcular Bandas de Bollinger para {symbol} no timeframe {timeframe}: {e}")
        return None




def calculate_moving_average(symbol, timeframe, period=20, method="SMA"):
    """
    Calcula a Média Móvel Simples (SMA) ou Exponencial (EMA).
    """
    try:
        data = load_recent_data(symbol, timeframe)
        if data is None or len(data) < period:
            return None  # Dados insuficientes

        if method.upper() == "EMA":
            moving_average = data['close'].ewm(span=period, adjust=False).mean()
        else:  # Default para SMA
            moving_average = data['close'].rolling(window=period).mean()

        return moving_average.iloc[-1]  # Último valor como número
    except Exception as e:
        print(f"Erro ao calcular Média Móvel para {symbol} no timeframe {timeframe}: {e}")
        return None


def validate_indicators(data, symbol, timeframe):
    try:
        # Calculando os indicadores
        rsi = calculate_rsi(symbol, timeframe)
        macd = calculate_macd(symbol, timeframe)
        bollinger_bands = calculate_bollinger_bands(symbol, timeframe)
        moving_average = calculate_moving_average(symbol, timeframe)

        # Validação dos indicadores técnicos (exemplo simples)
        # Indicador de compra (CALL) ou venda (PUT) com base no RSI
        if rsi < 30:
            indicator_signal = "CALL"
        elif rsi > 70:
            indicator_signal = "PUT"
        else:
            indicator_signal = "NEUTRAL"


        # Validação com o MACD
        macd_signal = "CALL" if macd[0] > macd[1] else "PUT"  # Comparar a linha MACD com a linha de sinal


        # Verificação com as Bandas de Bollinger
        if bollinger_bands is not None:
            upper_band, lower_band = bollinger_bands  # Atribui os valores das bandas superior e inferior

            # Acessa o último valor de fechamento
            last_close = data['close'].iloc[-1]

            if last_close < lower_band:  # Preço abaixo da banda inferior
                bollinger_signal = "CALL"
            elif last_close > upper_band:  # Preço acima da banda superior
                bollinger_signal = "PUT"
            else:
                bollinger_signal = "NEUTRAL"

        else:
            print("Não foi possível calcular as Bandas de Bollinger.")

        # Validando a média móvel
        if moving_average is not None:
            # Acessa o último preço de fechamento
            last_close = data['close'].iloc[-1]

            # Comparação do preço com a média móvel
            if last_close < moving_average:  # Preço abaixo da média
                moving_average_signal = "CALL"
            else:
                moving_average_signal = "PUT"

        else:
            print("Não foi possível calcular a média móvel.")

        # Retorna os sinais combinados
        return indicator_signal, macd_signal, bollinger_signal, moving_average_signal
    
    except Exception as e:
        print(f"Erro ao validar os indicadores para {symbol} no timeframe {timeframe}: {e}")
        return "NONE"


def emit_signal(data, symbol, timeframe):
    try:
        global emitted_signals
        signal = "HOLD"
        source = None
        indicator = ""

        try:
            # Determina a fonte (OTC, Forex, Crypto)
            if symbol in iq_symbols:
                source = 'otc'
            elif symbol in mt5_symbols:
                source = 'forex'
            elif symbol in binance_symbols:
                source = 'crypto'
        except Exception as e:
            print(f"Erro ao determinar a fonte para o símbolo {symbol}: {e}")
            return "NONE"
        
        try:
            # Identificar a tendência usando médias móveis
            tendencia = identify_trend(data, short_period=20, long_period=50)  # alta, baixa ou lateral
        except Exception as e:
            print(f"Erro ao identificar a tendência para {symbol}: {e}")
            return "NONE"



        try:
            fibonacci = calculate_fibonacci_signal(data)
            if fibonacci == "CALL":
                signal = "CALL"
                indicator = f"Fibonacci proximo ao suporte" 
            elif fibonacci == "PUT":
                signal = "PUT"
                indicator = f"Fibonacci proximo a resistência"    
        except Exception as e:
            print(f"Erro ao identificar a fibonacci para {symbol}: {e}")
            return "NONE"          

        try:
            # Envio do sinal
            if signal != 'HOLD':
                minutes = int(timeframe[1:])
                now = datetime.now()
                next_time = now + timedelta(minutes=minutes - (now.minute % minutes), seconds=-now.second, microseconds=-now.microsecond)
                next_candle_time = next_time.strftime('%Y-%m-%d %H:%M:%S')

                # Se necessário, converte o horário do próximo candle para datetime
                if isinstance(next_candle_time, str):
                    next_candle_time = datetime.strptime(next_candle_time, "%Y-%m-%d %H:%M:%S")
                
                if next_candle_time > now:
                    unique_key = f"{symbol}_{timeframe}_{signal}_{next_candle_time}"
                    
                    if unique_key in emitted_signals:
                        return  # Não emite o mesmo sinal novamente
                    
                    emitted_signals[unique_key] = True
                    
                    # Calcula a volatilidade e volume para o próximo candle
                    volatility = calculate_volatility(symbol, timeframe, next_candle_time)
                    volume = get_volume(symbol, timeframe, next_candle_time)
                    
                    # Insere o sinal no banco de dados
                    insert_trading_signal(symbol, timeframe, next_candle_time, signal, source, "1", volatility, volume, indicator)
        except Exception as e:
            print(f"Erro ao enviar o sinal para {symbol}: {e}")
            return "NONE"

    except ValueError as e:
        print(f"Erro geral ao emitir sinal: {e}")
        return "NONE"


def calculate_fibonacci_signal(data, lookback=200):
    """
    Calcula os níveis de Fibonacci e retorna um sinal de CALL, PUT ou HOLD.
    
    Args:
        data (pd.DataFrame): Dados do mercado com colunas ['high', 'low', 'close'].
        lookback (int): Número de candles para considerar no cálculo (padrão: 20).
    
    Returns:
        str: "CALL", "PUT" ou "HOLD" com base nos níveis de Fibonacci.
    """
    try:
        # Pega os últimos `lookback` candles
        recent_data = data[-lookback:]

        # Calcula o ponto máximo e mínimo
        high = recent_data['high'].max()
        low = recent_data['low'].min()

        # Calcula os níveis de Fibonacci
        levels = {
            "0.0%": high,
            "23.6%": high - (high - low) * 0.236,
            "38.2%": high - (high - low) * 0.382,
            "50.0%": high - (high - low) * 0.500,
            "61.8%": high - (high - low) * 0.618,
            "76.4%": high - (high - low) * 0.764,
            "100.0%": low,
        }

        # Determina o preço atual
        current_price = recent_data['close'].iloc[-1]

        # Identifica suporte e resistência próximos
        support = None
        resistance = None

        for level_name, price in levels.items():
            if price < current_price and (support is None or price > support):
                support = price  # Próximo suporte
            elif price > current_price and (resistance is None or price < resistance):
                resistance = price  # Próxima resistência

        # Gera o sinal
        if support and (current_price - support) / (high - low) <= 0.02:  # Próximo do suporte
            return "CALL"
        elif resistance and (resistance - current_price) / (high - low) <= 0.02:  # Próximo da resistência
            return "PUT"
        else:
            return "HOLD"

    except Exception as e:
        print(f"Erro ao calcular o sinal baseado em Fibonacci: {e}")
        return "HOLD"




def identify_trend(data, short_period=6, long_period=14):
    short_ma = data['close'][-short_period:].mean()
    long_ma = data['close'][-long_period:].mean()

    if short_ma > long_ma:
        return "alta"
    elif short_ma < long_ma:
        return "baixa"
    else:
        return "lateral"

def detect_pullback(data, tendencia):
    maximo = data['high'][-20:].max()
    minimo = data['low'][-20:].min()
    fechamento_atual = data['close'].iloc[-1]

    if tendencia == "alta":
        fib_levels = [maximo - (maximo - minimo) * lvl for lvl in [0.382, 0.5, 0.618]]
        return fechamento_atual <= max(fib_levels)
    elif tendencia == "baixa":
        fib_levels = [minimo + (maximo - minimo) * lvl for lvl in [0.382, 0.5, 0.618]]
        return fechamento_atual >= min(fib_levels)
    return False

def confirm_pullback(data, pattern, tendencia):
    if tendencia == "alta" and pattern in ["Bullish Hammer", "Morning Star", "Piercing Line"]:
        return True
    elif tendencia == "baixa" and pattern in ["Shooting Star", "Dark Cloud Cover", "Evening Star"]:
        return True
    return False




def identify_candle_pattern(data):
    """
    Identifica padrões de candles no dataframe.
    Retorna o nome do padrão ou 'NONE' se nenhum for identificado.
    """
    try:
        # Obtendo os dados da última vela
        open_price = float(data['open'].iloc[-1])
        close_price = float(data['close'].iloc[-1])
        high_price = float(data['high'].iloc[-1])
        low_price = float(data['low'].iloc[-1])

        # Dados da vela anterior
        prev_open = float(data['open'].iloc[-2])
        prev_close = float(data['close'].iloc[-2])
        prev_high = float(data['high'].iloc[-2])
        prev_low = float(data['low'].iloc[-2])

        # Dados da vela anterior a anterior
        prev2_open = float(data['open'].iloc[-3])
        prev2_close = float(data['close'].iloc[-3])

        # Cálculos auxiliares
        body = abs(close_price - open_price)
        upper_shadow = high_price - max(open_price, close_price)
        lower_shadow = min(open_price, close_price) - low_price
        prev_body = abs(prev_close - prev_open)
        prev2_body = abs(prev2_close - prev2_open)

        # Padrões de alta
        if (
            body < (high_price - low_price) * 0.3  # Corpo pequeno
            and lower_shadow > body * 2  # Sombra inferior longa
            and upper_shadow < body * 0.5  # Sombra superior curta
            and close_price > open_price  # Alta
        ):
            return "Bullish Hammer"
        elif (
            body < (high_price - low_price) * 0.3
            and upper_shadow > body * 2
            and lower_shadow < body * 0.5
            and close_price > open_price
        ):
            return "Inverted Hammer"
        elif (
            body > prev_body * 1.5  # Corpo maior que o anterior
            and close_price > prev_open  # Engolfando o corpo anterior
            and open_price < prev_close
        ):
            return "Bullish Engulfing"
        elif (
            body > prev_body * 1.5
            and close_price < prev_open
            and open_price > prev_close
        ):
            return "Engulfing Bearish"
        elif (
            upper_shadow > body * 2
            and lower_shadow < body * 0.5
            and close_price < open_price
        ):
            return "Shooting Star"
        elif (
            body < (high_price - low_price) * 0.3
            and close_price > prev_close
            and open_price < prev_open
            and high_price == max(high_price, prev_high)
            and low_price == min(low_price, prev_low)
        ):
            return "Harami Bullish"
        elif (
            body < (high_price - low_price) * 0.3
            and close_price < prev_close
            and open_price > prev_open
            and high_price == max(high_price, prev_high)
            and low_price == min(low_price, prev_low)
        ):
            return "Harami Bearish"  # Alterado para Harami Bearish
        elif (
            close_price > open_price  # Três velas consecutivas de alta
            and prev_close > prev_open
            and prev2_close > prev2_open
        ):
            return "Three White Soldiers"
        elif (
            data['close'].iloc[-3] > data['open'].iloc[-3]  # Três velas de baixa consecutivas
            and data['close'].iloc[-2] < data['open'].iloc[-2]
            and close_price < open_price
            and data['close'].iloc[-3] > data['close'].iloc[-2] > close_price
        ):
            return "Three Black Crows"
        elif (
            prev_close > prev_open
            and close_price < open_price
            and close_price < prev_low
            and open_price > prev_high
        ):
            return "Three Outside Down"
        elif (
            lower_shadow > upper_shadow * 2
            and body > (high_price - low_price) * 0.6
            and close_price > open_price
        ):
            return "Belt Hold Bullish"
        elif (
            close_price > prev_high
            and open_price > prev_close
            and high_price == max(high_price, prev_high)
            and low_price == min(low_price, prev_low)
        ):
            return "Morning Star"
        elif (
            close_price < open_price
            and prev_close > prev_open
            and close_price < prev_open
            and open_price > prev_close
        ):
            return "Dark Cloud Cover"
        elif (
            body > prev_body * 1.5
            and close_price < prev_open
            and open_price > prev_close
        ):
            return "Kicking Bearish"
        elif (
            body > prev_body * 1.5
            and close_price > prev_open
            and open_price < prev_close
        ):
            return "Kicking Bullish"
        elif (
            body < (high_price - low_price) * 0.1
            and upper_shadow < body * 0.1
            and lower_shadow > body * 2
        ):
            return "Dragonfly Doji"
        elif (
            body < (high_price - low_price) * 0.1
            and upper_shadow > body * 2
            and lower_shadow < body * 0.1
        ):
            return "Gravestone Doji"
        elif (
            close_price > open_price  # Marubozu Bullish
            and high_price == close_price
            and low_price == open_price
        ):
            return "Marubozu Bullish"
        elif (
            close_price < open_price  # Marubozu Bearish
            and high_price == open_price
            and low_price == close_price
        ):
            return "Marubozu Bearish"
        else:
            return "NONE"
    except ValueError as e:
        print(f"Erro ao identificar padrão de candle: {e}")
        return "NONE"




def calculate_volatility(symbol, timeframe, signal_time, periods=30):
    try:
        # Certifique-se de que signal_time é um objeto datetime
        if isinstance(signal_time, str):
            signal_time = pd.to_datetime(signal_time)

        cursor = conn.cursor()

        # Obter os preços de open, high, low e close dos últimos 'periods' períodos + 1 (para o cálculo do true range)
        query = """
            SELECT time, open, high, low, close FROM candle_history 
            WHERE symbol = %s AND timeframe = %s AND time <= %s
            ORDER BY time DESC LIMIT %s
        """
        cursor.execute(query, (symbol, timeframe, signal_time.strftime('%Y-%m-%d %H:%M:%S'), periods + 1))
        rows = cursor.fetchall()
        
        if len(rows) < periods + 1:
            print(f"IA: Não há dados suficientes para calcular a volatilidade para {symbol} no timeframe {timeframe}.")
            return None

        # Converter os dados para um DataFrame para facilitar o cálculo
        df = pd.DataFrame(rows, columns=['time', 'open', 'high', 'low', 'close'])
        df['time'] = pd.to_datetime(df['time'])  # Certifique-se de que a coluna de tempo está no formato datetime
        df = df.sort_values(by='time').reset_index(drop=True)

        # Calcular o True Range (TR)
        df['previous_close'] = df['close'].shift(1)
        df['tr1'] = df['high'] - df['low']
        df['tr2'] = (df['high'] - df['previous_close']).abs()
        df['tr3'] = (df['low'] - df['previous_close']).abs()
        df['true_range'] = df[['tr1', 'tr2', 'tr3']].max(axis=1)

        # Calcular o Average True Range (ATR)
        df['atr'] = df['true_range'].rolling(window=periods).mean()

        # A volatilidade será o valor do ATR no último período
        volatility = df['atr'].iloc[-1]

        return volatility
    
    except Exception as e:
        error = f"IA: Erro ao calcular a volatilidade para {symbol} no timeframe {timeframe}: {e}"
        send_message(bot_alert, admin_chat_id, error)
        print(error)
        return None


def get_volume(symbol, timeframe, signal_time_str):
    try:
        # Conectando aos bancos de dados
        cursor = conn.cursor()

        # Verificar se signal_time_str já é datetime, se for, não converte
        if isinstance(signal_time_str, str):
            try:
                # Converter a string signal_time para um objeto datetime
                signal_time = datetime.strptime(signal_time_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                error = "IA: Formato inválido de data. Use '%Y-%m-%d %H:%M:%S'"
                send_message(bot_alert, admin_chat_id, error)
                print(error)
                return None
        else:
            signal_time = signal_time_str  # Já é um objeto datetime, então só usa diretamente

        # Definindo o número de minutos a subtrair com base no timeframe
        if timeframe == 'M1':
            minutes_to_subtract = 2 * 1  # 2x 1 minuto
        elif timeframe == 'M5':
            minutes_to_subtract = 2 * 5  # 2x 5 minutos
        elif timeframe == 'M15':
            minutes_to_subtract = 2 * 15  # 2x 15 minutos
        else:
            error = f"IA: Timeframe inválido: {timeframe}."
            send_message(bot_alert, admin_chat_id, error)
            print(error)
            return None

        # Calculando o tempo anterior
        previous_time = signal_time - timedelta(minutes=minutes_to_subtract)
        previous_time_str = previous_time.strftime("%Y-%m-%d %H:%M:%S")

        # Consulta para obter o volume da vela no tempo anterior
        query_candles = """
        SELECT tick_volume FROM candle_history
        WHERE symbol = %s AND timeframe = %s AND time = %s
        """
        cursor.execute(query_candles, (symbol, timeframe, previous_time_str))
        result = cursor.fetchone()

        if result:
            tick_volume = result[0]
        else:
            # Se não encontrar a vela, definir o volume como None ou 0
            tick_volume = None  # ou 0, dependendo do comportamento desejado

        return tick_volume

    except Exception as e:
        error = f"IA: Erro ao obter o volume para {symbol} no timeframe {timeframe}: {e}"
        send_message(bot_alert, admin_chat_id, error)
        print(error)
        return None


def insert_trading_signal(symbol, timeframe, time, direction, source, confidence, volatility, volume, indicator):
    try:
        cursor = conn.cursor()
        # Supondo que `time` seja um objeto datetime
        formatted_time = time.strftime('%Y-%m-%d %H:%M:%S')

        
        try:
            if check_news_for_symbol(symbol, formatted_time) is None:
                is_otc = symbol.endswith("-OTC")
                original_symbol = symbol
                currency1 = "N/A"
                currency2 = "N/A"
                if not is_otc:
                    currency1 = symbol[:3]
                    currency2 = symbol[3:]
                now = datetime.now()
                try:
                    payout = ativos_iq.get_payout(original_symbol)
                except Exception as e:
                    error = f"IA: Erro ao buscar o payout: {e}"
                    send_message(bot_alert, admin_chat_id, error)
                    print(error)    
                    
                if payout is None:
                    return
                else:
                    payout = float(payout)
                if payout < 70:
                    return

                # Converta formatted_time para um objeto datetime
                formatted_time_dt = datetime.strptime(formatted_time, '%Y-%m-%d %H:%M:%S')

                # Mapeia o timeframe para um número inteiro
                timeframe_int = timeframe_mapping2.get(timeframe)
                if timeframe_int is None:
                    raise ValueError(f"Timeframe '{timeframe}' não reconhecido")
                if timeframe == "M1":
                    time_n_min_ago = formatted_time_dt - timedelta(minutes=5)
                else:
                    time_n_min_ago = formatted_time_dt - timedelta(minutes=(3*timeframe_int))
                
                time_n_min_ago_str = time_n_min_ago.strftime('%Y-%m-%d %H:%M:%S')
                time_loss_ago = formatted_time_dt - timedelta(minutes=60)
                time_loss_ago_str = time_loss_ago.strftime('%Y-%m-%d %H:%M:%S')
                
                try:

                    if is_otc:
                        # Verifica o número de sinais existentes
                        cursor.execute(
                            "SELECT COUNT(*) FROM trading_signals WHERE symbol = %s AND timeframe = %s AND time BETWEEN %s AND %s", 
                            (symbol, timeframe, time_n_min_ago_str, formatted_time)
                        )
                        existing_signal_count_result = cursor.fetchone()
                        existing_signal_count = existing_signal_count_result[0] if existing_signal_count_result else 0

                    else:
                        # Verifica o número de sinais existentes
                        cursor.execute(
                            "SELECT COUNT(*) FROM trading_signals WHERE (symbol LIKE %s OR symbol LIKE %s) AND timeframe = %s AND time BETWEEN %s AND %s", 
                            ('%' + currency1 + '%', '%' + currency2 + '%', timeframe, time_n_min_ago_str, formatted_time)
                        )
                        existing_signal_count_result = cursor.fetchone()
                        existing_signal_count = existing_signal_count_result[0] if existing_signal_count_result else 0
                        
                    # Verifica o número de perdas existentes
                    cursor.execute(
                        "SELECT COUNT(*) FROM trading_signals WHERE symbol = %s AND timeframe = %s AND time BETWEEN %s AND %s AND Result = 'LOSS ❌'", 
                        (symbol, timeframe, time_loss_ago_str, formatted_time)
                    )
                    existing_loss_count_result = cursor.fetchone()
                    existing_loss_count = existing_loss_count_result[0] if existing_loss_count_result else 0

                    if existing_signal_count == 0 and existing_loss_count == 0:
                        if direction not in ['CALL', 'PUT', 'HOLD']:
                            direction = 'HOLD'  # Define a direção padrão se o valor não for válido
                        
                        sql = """INSERT INTO trading_signals (symbol, timeframe, time, direction, payout, sent, edited, status, inserted, volatility, volume, source, confidence, indicator) 
                        VALUES (%s, %s, %s, %s, %s, NULL, NULL, 'Aberto', %s, %s, %s, %s, %s, %s)"""
                        
                        # Converte confidence para float
                        cursor.execute(sql, (original_symbol, timeframe, formatted_time, direction, payout, now, volatility, volume, source, float(confidence), indicator))
                        conn.commit()
                        print(f"Sinal emitido: {formatted_time} - {symbol} {direction} {timeframe}\n{indicator}")


                    else:
                        cursor.execute(
                            "SELECT symbol FROM trading_signals WHERE (symbol LIKE %s OR symbol LIKE %s) AND timeframe = %s AND time BETWEEN %s AND %s", 
                            ('%' + currency1 + '%', '%' + currency2 + '%', timeframe, time_n_min_ago_str, formatted_time)
                        )
                        existing_symbols = cursor.fetchall()

                        cursor.execute(
                            "SELECT symbol FROM trading_signals WHERE symbol = %s AND timeframe = %s AND time BETWEEN %s AND %s AND Result = 'LOSS ❌'", 
                            (symbol, timeframe, time_loss_ago_str, formatted_time)
                        )
                        existing_losses = cursor.fetchall()

                        if existing_symbols:
                            return
                        elif existing_losses:
                            return
 

                except Exception as e:
                    error = f"IA: Erro ao buscar os sinais: {e}"
                    send_message(bot_alert, admin_chat_id, error)
                    print(error)

            else:
                return
                
        except Exception as e:
            error = f"IA: Erro ao processar notícias: {e}"
            send_message(bot_alert, admin_chat_id, error)
            print(error)

    except Exception as e:
        error = f"IA: Erro ao inserir sinal: {e}"
        send_message(bot_alert, admin_chat_id, error)
        print(error)
        conn.rollback()

def gerar_sinais(ativos, num_sinais):
    try:
        sinais = []
        hora_inicial = datetime.strptime("01:00", "%H:%M")
        hora_final = datetime.strptime("15:00", "%H:%M")

        # Obter a data atual e adicionar um dia
        data_atual = datetime.now() + timedelta(days=1)
        
        minutos_possiveis = [f"{h:02}:{m:02}" for h in range(1, 16) for m in range(0, 60, 5) 
                            if h < 15 or (h == 15 and m == 0)]
        
        horarios_aleatorios = random.sample(minutos_possiveis, num_sinais)

        for horario in sorted(horarios_aleatorios):
            # Combinar a data com o horário gerado
            horario_completo = data_atual.replace(hour=int(horario.split(':')[0]), minute=int(horario.split(':')[1]), second=0)
            
            ativo = random.choice(ativos)
            direcao = random.choice(["CALL", "PUT"])
            
            # Formatar sinal com segundos
            sinal_formatado = f"{horario_completo.strftime('%Y-%m-%d %H:%M:%S')} {ativo} {direcao} M5"
            sinais.append((ativo, direcao, "M5", horario_completo.strftime('%Y-%m-%d %H:%M:%S'), None, None, 1, "list"))  # 'None' para colunas que não temos dados


        insert_signals_list(sinais)
    except Exception as e:
            error = f"IA: Erro ao gerar lista de sinais: {e}"
            send_message(bot_alert, admin_chat_id, error)
            print(error)    

def insert_signals_list(sinais):
    # Conectar ao banco de dados
    cursor = conn.cursor()
    
    # Comando SQL para inserir os dados
    query = """
    INSERT INTO trading_signals (symbol, direction, timeframe, time, result, message_id, list, source)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
    """
    
    try:
        # Executar inserção para cada sinal
        cursor.executemany(query, sinais)
        conn.commit()  # Confirmar a transação
    except Exception as e:
        error = f"IA: Erro ao incluir lista de sinais no banco de dados: {e}"
        send_message(bot_alert, admin_chat_id, error)
        print(error)  


def gerar_sinais_dinamico(mt5_symbols, iq_symbols, sinais_free):
    """
    Função que decide qual conjunto de símbolos utilizar (normal ou OTC) com base no status do mercado.
    
    Args:
        mt5_symbols (list): Lista de símbolos para o mercado normal (MT5).
        iq_symbols (list): Lista de símbolos para OTC.
        sinais_free (list): Sinais gratuitos a serem gerados.
    """
    # Obter o calendário do mercado (por exemplo, NYSE)
    market_calendar = mcal.get_calendar('NYSE')
    
    # Calcular o dia de referência (amanhã)
    tomorrow = datetime.now().date() + timedelta(days=1)
    
    # Verificar se o mercado estará aberto amanhã
    schedule = market_calendar.schedule(start_date=tomorrow, end_date=tomorrow)
    
    if schedule.empty:
        # Mercado estará fechado amanhã (usar OTC)
        print(f"Mercado fechado no dia {tomorrow}. Usando OTC (iq_symbols).")
        gerar_sinais(iq_symbols, sinais_free)
    else:
        # Mercado estará aberto amanhã (usar mercado normal)
        print(f"Mercado aberto no dia {tomorrow}. Usando mercado normal (mt5_symbols).")
        gerar_sinais(mt5_symbols, sinais_free)


def monitor_opportunities():
    while True:
        connect_to_database()
        
        # Atualizar os símbolos a partir do JSON sempre que o loop for executado
        all_symbols = load_symbols_from_json()
        
        for symbol in all_symbols:
            for timeframe in timeframes:
                mapped_timeframe = f'{timeframe}'
                try:
                    # Fazer previsão para o ativo
                    data = load_recent_data(symbol, timeframe)
                    emit_signal(data, symbol, timeframe)
                    
                except Exception as e:
                    print(f"Erro ao analisar {symbol} no timeframe {mapped_timeframe}: {e}")

        # Esperar um intervalo de tempo antes de rodar o loop novamente (ex: 1 segundo)
        time.sleep(1)

# Iniciar o monitoramento
gerar_sinais_dinamico(mt5_symbols, iq_symbols, sinais_free)
scheduler = BackgroundScheduler()

scheduler.add_job(gerar_sinais_dinamico, 'cron', day_of_week='fri,sat,sun,mon,tue,wed,thu', hour=23, minute=0, args=[mt5_symbols, iq_symbols, sinais_free])

# Agendar a tarefa de conexão com o banco de dados
scheduler.add_job(connect_to_database, IntervalTrigger(seconds=5))

# Agendar a tarefa de atualização dos símbolos a cada 5 minutos

scheduler.start()
monitor_opportunities()


