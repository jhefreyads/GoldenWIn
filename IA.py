import numpy as np
import random
import pandas as pd
from sqlalchemy import create_engine
from sklearn.preprocessing import MinMaxScaler
from sklearn.model_selection import train_test_split
import pickle
from calendario import check_news_for_symbol
import ativos_iq
from db_connection import get_engine, get_connection
from configparser import ConfigParser
import ta
import warnings
import os
import time
from datetime import datetime, timedelta
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2' 
warnings.filterwarnings("ignore")
import tensorflow as tf
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


# Carregar símbolos e timeframes da configuração
binance_symbols = config.get('Candles', 'binance_symbols').split(', ')
iq_symbols = config.get('Candles', 'iq_symbols').split(', ')
mt5_symbols = config.get('Candles', 'mt5_symbols').split(', ')
admin_chat_id = config.get('Telegram', 'admin_chat_id')
TOKEN_ALERT = config.get('Telegram', 'TOKEN_ALERT')
bot_alert = telebot.TeleBot(TOKEN_ALERT)
sinais_free = config.getint('Scripts', 'Sinais_free')
timeframes_conf_str = config.get('Candles', 'timeframes')
timeframes_number = [int(x.strip()) for x in timeframes_conf_str.split(',')]
timeframe_mapping = {1: 'M1', 5: 'M5', 15: 'M15'}
timeframe_mapping2 = {
    'M1': 1,
    'M5': 5,
    'M15': 15
}
timeframes = [timeframe_mapping[tf] for tf in timeframes_number if tf in timeframe_mapping]


def get_symbols():
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


def load_recent_data_with_indicators(symbol, timeframe, num_candles=50):
    try:
        cursor = conn.cursor()
    except Exception as e:
        error = f"IA: Erro ao abrir o cursor: {e}"
        send_message(bot_alert, admin_chat_id, error)
        print(error)
        return None
    
    try:
        # Use parâmetros para evitar SQL injection
        query = """
            SELECT time, open, close, high, low, tick_volume 
            FROM candle_history 
            WHERE symbol = %s AND timeframe = %s 
            ORDER BY time DESC 
            LIMIT %s
        """
        candles_data = pd.read_sql(query, conn, params=(symbol, timeframe, num_candles))
    except Exception as e:
        error = f"IA: Erro ao buscar os dados de velas: {e}"
        send_message(bot_alert, admin_chat_id, error)
        print(error)
        return None

    try:
        current_price_query = """
            SELECT current_price 
            FROM trading_data 
            WHERE symbol = %s AND timeframe = %s 
            ORDER BY open_time DESC 
            LIMIT 1
        """
        current_price_data = pd.read_sql(current_price_query, conn, params=(symbol, timeframe))
    except Exception as e:
        error = f"IA: Erro ao buscar o preço atual: {e}"
        send_message(bot_alert, admin_chat_id, error)
        print(error)
        return None

    try:
        if not current_price_data.empty:
            candles_data.at[0, 'close'] = float(current_price_data['current_price'].iloc[0])
    except Exception as e:
        error = f"IA: Erro ao atualizar o preço de fechamento: {e}"
        send_message(bot_alert, admin_chat_id, error)
        print(error)
        return None

    try:
        candles_data = add_technical_indicators(candles_data)  # Usando a função do código anterior
    except Exception as e:
        error = f"IA: Erro ao adicionar os indicadores técnicos: {e}"
        send_message(bot_alert, admin_chat_id, error)
        print(error)
        return None
    
    try:
        cursor.close()  # Fecha o cursor
    except Exception as e:
        error = f"IA: Erro ao fechar o cursor: {e}"
        send_message(bot_alert, admin_chat_id, error)
        print(error)

    return candles_data


def calculate_psar(data, initial_af=0.02, max_af=0.2):
    try:
        # Inicializando variáveis
        psar = np.zeros(len(data))
        trend = 1  # 1 para uptrend, -1 para downtrend
        af = initial_af
        ep = data['high'][0]  # Extreme Point
        psar[0] = data['low'][0]  # Inicializa o primeiro PSAR como o mínimo
    except Exception as e:
        error = f"IA: Erro ao inicializar variáveis do PSAR: {e}"
        send_message(bot_alert, admin_chat_id, error)
        print(error)
        return None

    try:
        for i in range(1, len(data)):
            psar[i] = psar[i - 1] + af * (ep - psar[i - 1])

            # Verifica a mudança de tendência
            if trend == 1:
                if data['low'][i] < psar[i]:
                    trend = -1
                    psar[i] = ep  # O novo PSAR é o EP
                    ep = data['low'][i]  # O EP agora é o mínimo
                    af = initial_af  # Reinicia o AF
                elif data['high'][i] > ep:
                    ep = data['high'][i]  # Atualiza o EP
                    af = min(af + initial_af, max_af)  # Aumenta o AF, com limite
            else:  # trend == -1
                if data['high'][i] > psar[i]:
                    trend = 1
                    psar[i] = ep  # O novo PSAR é o EP
                    ep = data['high'][i]  # O EP agora é o máximo
                    af = initial_af  # Reinicia o AF
                elif data['low'][i] < ep:
                    ep = data['low'][i]  # Atualiza o EP
                    af = min(af + initial_af, max_af)  # Aumenta o AF, com limite
    except Exception as e:
        error = f"IA: Erro ao calcular o PSAR: {e}"
        send_message(bot_alert, admin_chat_id, error)
        print(error)
        return None

    return psar


def add_technical_indicators(data, multiplier=1):
    try:
        # Médias Móveis
        data['SMA'] = ta.trend.sma_indicator(data['close'], window=5 * multiplier)
        data['EMA'] = ta.trend.ema_indicator(data['close'], window=5 * multiplier)
    except Exception as e:
        error = f"IA: Erro ao calcular SMA ou EMA: {e}"
        send_message(bot_alert, admin_chat_id, error)
        print(error)
        return None

    try:
        # Indicadores de Momento
        data['RSI'] = ta.momentum.rsi(data['close'], window=3 * multiplier)
        data['MACD'] = ta.trend.macd(data['close'], window_slow=5 * multiplier, window_fast=2 * multiplier)
        data['MACD_signal'] = ta.trend.macd_signal(data['close'], window_slow=5 * multiplier, window_fast=2 * multiplier, window_sign=1.5 * multiplier)
    except Exception as e:
        error = f"IA: Erro ao calcular RSI, MACD ou MACD_signal: {e}"
        send_message(bot_alert, admin_chat_id, error)
        print(error)
        return None

    try:
        # Bandas de Bollinger
        bb = ta.volatility.BollingerBands(data['close'], window=7 * multiplier, window_dev=2 * multiplier)
        data['BB_upper_new'] = bb.bollinger_hband()
        data['BB_lower_new'] = bb.bollinger_lband()
    except Exception as e:
        error = f"IA: Erro ao calcular Bandas de Bollinger: {e}"
        send_message(bot_alert, admin_chat_id, error)
        print(error)
        return None

    try:
        # Indicadores de Volume
        data['Volume_MA'] = data['tick_volume'].rolling(window=5).mean()
        data['OBV'] = (np.sign(data['close'].diff()) * data['tick_volume']).cumsum()
    except Exception as e:
        error = f"IA: Erro ao calcular Volume_MA ou OBV: {e}"
        send_message(bot_alert, admin_chat_id, error)
        print(error)
        return None

    try:
        # Indicadores de Tendência
        data['ADX'] = ta.trend.adx(data['high'], data['low'], data['close'], window=14)
        data['PSAR'] = calculate_psar(data)  # Chama a função personalizada para calcular PSAR
    except Exception as e:
        error = f"IA: Erro ao calcular ADX ou PSAR: {e}"
        send_message(bot_alert, admin_chat_id, error)
        print(error)
        return None

    try:
        # CCI e Williams %R
        data['CCI'] = ta.trend.cci(data['high'], data['low'], data['close'], window=14 * multiplier)
        data['Williams_R'] = ta.momentum.williams_r(data['high'], data['low'], data['close'], lbp=10 * multiplier)
    except Exception as e:
        error = f"IA: Erro ao calcular CCI ou Williams_R: {e}"
        send_message(bot_alert, admin_chat_id, error)
        print(error)
        return None

    try:
        # Momentum
        data['Momentum'] = ((data['close'] - data['close'].shift(14)) / data['close'].shift(14)) * 100
    except Exception as e:
        error = f"IA: Erro ao calcular Momentum: {e}"
        send_message(bot_alert, admin_chat_id, error)
        print(error)
        return None

    try:
        # Estocástico
        data['Stoch_K'] = ta.momentum.stoch(data['high'], data['low'], data['close'], window=9 * multiplier, smooth_window=3 * multiplier)
        data['Stoch_D'] = ta.momentum.stoch_signal(data['high'], data['low'], data['close'], window=9 * multiplier, smooth_window=3 * multiplier)
    except Exception as e:
        error = f"IA: Erro ao calcular Stoch_K ou Stoch_D: {e}"
        send_message(bot_alert, admin_chat_id, error)
        print(error)
        return None

    try:
        # Média das Médias
        ma_columns = ['SMA', 'EMA']  # Inclua as médias que você deseja calcular a média
        data['MA_average'] = data[ma_columns].mean(axis=1)
    except Exception as e:
        error = f"IA: Erro ao calcular MA_average: {e}"
        send_message(bot_alert, admin_chat_id, error)
        print(error)
        return None

    try:
        # Padrões de Velas
        data['Bullish_Engulfing'] = ((data['close'] > data['open']) & (data['open'].shift(1) > data['close'].shift(1)) & (data['close'] > data['open'].shift(1)))
        data['Bearish_Engulfing'] = ((data['close'] < data['open']) & (data['open'].shift(1) < data['close'].shift(1)) & (data['close'] < data['open'].shift(1)))
        data['Hammer'] = (data['close'] > data['open']) & ((data['high'] - data['close']) < 2 * (data['close'] - data['low'])) & ((data['high'] - data['open']) > 2 * (data['open'] - data['low']))
        data['Doji'] = abs(data['close'] - data['open']) <= 0.1 * (data['high'] - data['low'])
    except Exception as e:
        error = f"IA: Erro ao calcular padrões de velas: {e}"
        send_message(bot_alert, admin_chat_id, error)
        print(error)
        return None

    try:
        # Trate possíveis NaNs
        data.fillna(0, inplace=True)
    except Exception as e:
        error = f"IA: Erro ao tratar NaNs: {e}"
        send_message(bot_alert, admin_chat_id, error)
        print(error)
        return None

    return data



def preprocess_recent_data_with_indicators(data, scaler):
    try:
        data = data.dropna()  # Remover NaNs após adicionar indicadores
    except Exception as e:
        error = f"IA: Erro ao remover NaNs: {e}"
        send_message(bot_alert, admin_chat_id, error)
        print(error)
        return None

    try:
        data['price_diff'] = data['close'] - data['open']
    except Exception as e:
        error = f"IA: Erro ao calcular price_diff: {e}"
        send_message(bot_alert, admin_chat_id, error)
        print(error)
        return None

    try:
        data['week_day'] = pd.to_datetime(data['time']).dt.weekday
        data['hour'] = pd.to_datetime(data['time']).dt.hour
    except Exception as e:
        error = f"IA: Erro ao extrair week_day ou hour: {e}"
        send_message(bot_alert, admin_chat_id, error)
        print(error)
        return None

    try:
        features = data[['price_diff', 'week_day', 'hour', 'open', 'close', 'high', 'low', 'tick_volume',
                         'SMA', 'EMA', 'RSI', 'MACD', 'MACD_signal',  # Novos indicadores
                         'BB_upper_new', 'BB_lower_new', 'CCI', 'Williams_R', 'Momentum', 
                         'Stoch_K', 'Stoch_D', 'MA_average', 'Volume_MA', 'OBV', 'ADX', 'PSAR',
                         'Bullish_Engulfing', 'Bearish_Engulfing', 'Hammer', 'Doji']]
    except Exception as e:
        error = f"IA: Erro ao selecionar features: {e}"
        send_message(bot_alert, admin_chat_id, error)
        print(error)
        return None

    try:
        features_scaled = scaler.transform(features.fillna(0))
    except Exception as e:
        error = f"IA: Erro ao escalar as features: {e}"
        send_message(bot_alert, admin_chat_id, error)
        print(error)
        return None

    return features_scaled


def preprocess_data(data):
    try:
        if data.empty:
            print("IA: Aviso: Nenhum dado encontrado para o símbolo e timeframe fornecidos.")
            return None, None, None
    except Exception as e:
        error = f"IA: Erro ao verificar se os dados estão vazios: {e}"
        send_message(bot_alert, admin_chat_id, error)
        print(error)
        return None, None, None

    try:
        data = add_technical_indicators(data)
    except Exception as e:
        error = f"IA: Erro ao adicionar indicadores técnicos: {e}"
        send_message(bot_alert, admin_chat_id, error)
        print(error)
        return None, None, None

    try:
        data = data.dropna()  # Remover valores NaN
    except Exception as e:
        error = f"IA: Erro ao remover valores NaN: {e}"
        send_message(bot_alert, admin_chat_id, error)
        print(error)
        return None, None, None

    try:
        data = data.copy()  # Garantir que estamos trabalhando com uma cópia do DataFrame
        data['price_diff'] = data['close'] - data['open']
        data['week_day'] = pd.to_datetime(data['time']).dt.weekday
        data['hour'] = pd.to_datetime(data['time']).dt.hour
    except Exception as e:
        error = f"IA: Erro ao adicionar variáveis de tempo ou calcular price_diff: {e}"
        send_message(bot_alert, admin_chat_id, error)
        print(error)
        return None, None, None

    try:
        features = data[['price_diff', 'week_day', 'hour', 'open', 'close', 'high', 'low', 'tick_volume',
                         'SMA', 'EMA', 'RSI', 'MACD', 'MACD_signal',  # Novos indicadores
                         'BB_upper_new', 'BB_lower_new', 'CCI', 'Williams_R', 'Momentum', 
                         'Stoch_K', 'Stoch_D', 'MA_average', 'Volume_MA', 'OBV', 'ADX', 'PSAR',
                         'Bullish_Engulfing', 'Bearish_Engulfing', 'Hammer', 'Doji']]  # Adicionando padrões de velas
    except Exception as e:
        error = f"IA: Erro ao selecionar as features: {e}"
        send_message(bot_alert, admin_chat_id, error)
        print(error)
        return None, None, None

    try:
        labels = np.where(data['close'] > data['open'], 1, 0)  # 1 para alta, 0 para baixa
    except Exception as e:
        error = f"IA: Erro ao gerar os labels: {e}"
        send_message(bot_alert, admin_chat_id, error)
        print(error)
        return None, None, None

    try:
        if features.empty:
            print("IA: Aviso: As features estão vazias após o processamento.")
            return None, None, None
    except Exception as e:
        error = f"IA: Erro ao verificar se as features estão vazias: {e}"
        send_message(bot_alert, admin_chat_id, error)
        print(error)
        return None, None, None

    try:
        scaler = MinMaxScaler()
        features_scaled = scaler.fit_transform(features)
    except Exception as e:
        error = f"IA: Erro ao escalar as features: {e}"
        send_message(bot_alert, admin_chat_id, error)
        print(error)
        return None, None, None

    return features_scaled, labels, scaler


def train_model(symbol, timeframe, features, labels):
    try:
        if features is None or labels is None:
            print(f"IA: Não foi possível treinar o modelo para {symbol} {timeframe} devido à falta de dados.")
            return None
    except Exception as e:
        error = f"IA: Erro ao verificar dados de entrada: {e}"
        send_message(bot_alert, admin_chat_id, error)
        print(error)
        return None

    try:
        X_train, X_test, y_train, y_test = train_test_split(features, labels, test_size=0.2, random_state=42)
    except Exception as e:
        error = f"IA: Erro ao dividir os dados em conjuntos de treino e teste: {e}"
        send_message(bot_alert, admin_chat_id, error)
        print(error)
        return None

    try:
        model = tf.keras.models.Sequential([
            tf.keras.layers.Input(shape=(X_train.shape[1],)),
            tf.keras.layers.Dense(4096, activation='relu'),
            tf.keras.layers.Dense(2048, activation='relu'),        
            tf.keras.layers.Dense(1024, activation='relu'),
            tf.keras.layers.Dense(512, activation='relu'),
            tf.keras.layers.Dense(256, activation='relu'),
            tf.keras.layers.Dense(128, activation='relu'),
            tf.keras.layers.Dense(64, activation='relu'),
            tf.keras.layers.Dense(1, activation='sigmoid')
        ])
    except Exception as e:
        error = f"IA: Erro ao criar o modelo: {e}"
        send_message(bot_alert, admin_chat_id, error)
        print(error)
        return None

    try:
        model.compile(optimizer='adam', 
                      loss='binary_crossentropy', 
                      metrics=['accuracy', 
                               tf.keras.metrics.Precision(), 
                               tf.keras.metrics.Recall(),
                               tf.keras.metrics.AUC(name='auc'),
                               tf.keras.metrics.BinaryAccuracy(name='binary_accuracy')])
    except Exception as e:
        error = f"IA: Erro ao compilar o modelo: {e}"
        send_message(bot_alert, admin_chat_id, error)
        print(error)
        return None

    try:
        history = model.fit(X_train, y_train, epochs=10, batch_size=1024, validation_data=(X_test, y_test))
    except Exception as e:
        error = f"IA: Erro ao treinar o modelo: {e}"
        send_message(bot_alert, admin_chat_id, error)
        print(error)
        return None

    try:
        model.save(f'IA/model_{symbol}_{timeframe}.keras')
        pd.DataFrame(history.history).to_csv(f'IA/history_{symbol}_{timeframe}.csv', index=False)
    except Exception as e:
        error = f"IA: Erro ao salvar o modelo ou o histórico: {e}"
        send_message(bot_alert, admin_chat_id, error)
        print(error)
        return None

    return model


# Função para calcular o horário da próxima vela
def get_next_candle_time(last_candle_time, timeframe):
    try:
        # Converter o tempo do último candle para datetime
        last_time = pd.to_datetime(last_candle_time)
    except Exception as e:
        error = f"IA: Erro ao converter o tempo do último candle: {e}"
        send_message(bot_alert, admin_chat_id, error)
        print(error)
        return None

    try:
        if timeframe == 'M1':
            next_time = last_time + timedelta(minutes=int(timeframe[1:])) + timedelta(minutes=int(timeframe[1:])) + timedelta(minutes=int(timeframe[1:]))
        else:
            next_time = last_time + timedelta(minutes=int(timeframe[1:])) + timedelta(minutes=int(timeframe[1:]))
    except Exception as e:
        error = f"IA: Erro ao calcular o próximo horário da vela: {e}"
        send_message(bot_alert, admin_chat_id, error)
        print(error)
        return None

    try:
        return next_time.strftime('%Y-%m-%d %H:%M:%S')
    except Exception as e:
        error = f"IA: Erro ao formatar o próximo horário da vela: {e}"
        send_message(bot_alert, admin_chat_id, error)
        print(error)
        return None
        
def has_partial_alternation(data, n=5, min_alternations=3):
    """
    Verifica se nas últimas `n` velas há um mínimo de `min_alternations` alternâncias entre positivas e negativas.
    Retorna True se houver alternância suficiente, False caso contrário.
    """
    close_prices = data['close'].tail(n).values
    alternations = sum((close_prices[i] > close_prices[i - 1]) != (close_prices[i - 1] > close_prices[i - 2])
                       for i in range(2, n))
    return alternations >= min_alternations

def get_majority_direction(data, n=5):
    """
    Determina a direção predominante nas últimas `n` velas. 
    Retorna 'CALL' se a maioria for de alta, 'PUT' se a maioria for de baixa.
    """
    close_prices = data['close'].tail(n).values
    up_moves = sum(1 for i in range(1, n) if close_prices[i] > close_prices[i - 1])
    down_moves = n - 1 - up_moves
    return 'CALL' if up_moves > down_moves else 'PUT'

def predict_next_candle_with_indicators(symbol, timeframe):
    model_path = f'IA/model_{symbol}_{timeframe}.keras'
    scaler_path = f'IA/scaler_{symbol}_{timeframe}.pkl'

    try:
        # Carregar ou treinar o modelo e o scaler
        if not os.path.exists(model_path) or not os.path.exists(scaler_path):
            data = load_recent_data_with_indicators(symbol, timeframe, num_candles=5000)
            features, labels, scaler = preprocess_data(data)
            model = train_model(symbol, timeframe, features, labels)

            if model is not None:
                print(f"Modelo treinado e salvo para {symbol} no timeframe {timeframe}.")
            else:
                print(f"IA: Modelo não treinado para {symbol} no timeframe {timeframe}.")

            # Salvar o modelo e o scaler após o treinamento
            if model is not None:
                model.save(model_path)
                with open(scaler_path, 'wb') as file:
                    pickle.dump(scaler, file)

            return
    except Exception as e:
        error = f"IA: Erro ao carregar ou treinar o modelo e o scaler: {e}"
        send_message(bot_alert, admin_chat_id, error)
        print(error)
        return

    # Validar alternância parcial nas últimas velas antes de prosseguir
    try:
        data = load_recent_data_with_indicators(symbol, timeframe)
        if not has_partial_alternation(data, n=5, min_alternations=3):
            majority_direction = get_majority_direction(data, n=5)
        else:
            majority_direction = None
    except Exception as e:
        error = f"IA: Erro ao validar alternância parcial das últimas velas: {e}"
        send_message(bot_alert, admin_chat_id, error)
        print(error)
        return

    try:
        model = tf.keras.models.load_model(model_path)

        with open(scaler_path, 'rb') as f:
            scaler = pickle.load(f)
    except Exception as e:
        error = f"IA: Erro ao carregar o modelo ou o scaler: {e}"
        send_message(bot_alert, admin_chat_id, error)
        print(error)
        return

    try:
        features = preprocess_recent_data_with_indicators(data, scaler)

        predictions = model.predict(features)
        latest_prediction = predictions[-1][0]
    except Exception as e:
        error = f"IA: Erro ao processar dados ou fazer previsões: {e}"
        send_message(bot_alert, admin_chat_id, error)
        print(error)
        return

    try:
        confidence = max(latest_prediction, 1 - latest_prediction)
        confidence_threshold = 0.99

        mean_pred = np.mean(predictions)
        std_pred = np.std(predictions)
        lower_threshold = mean_pred - std_pred
        upper_threshold = mean_pred + std_pred

        print(f"Previsão: {latest_prediction}, Limiares -> PUT: <{lower_threshold}, CALL: >{upper_threshold}, Confiança: {confidence}")

        if latest_prediction < lower_threshold:
            direction = 'PUT'
        elif latest_prediction > upper_threshold:
            direction = 'CALL'
        else:
            direction = 'HOLD'

        if confidence < confidence_threshold or direction == 'HOLD':
            print(f"Sinal ignorado devido à baixa confiança ({confidence * 100:.2f}%) ou HOLD.")
            return

        # Verificação final com base na direção predominante em caso de falta de alternância
        if majority_direction and direction != majority_direction:
            print(f"Sinal ignorado pois a previsão ({direction}) não corresponde à direção predominante ({majority_direction}).")
            return
    except Exception as e:
        error = f"IA: Erro ao calcular confiança ou determinar direção: {e}"
        send_message(bot_alert, admin_chat_id, error)
        print(error)
        return

    try:
        minutes = int(timeframe[1:])
        now = datetime.now()
        if timeframe == "M1":
            next_time = now + timedelta(
                minutes=minutes - (now.minute % minutes) + 1,  # Adiciona mais 1 minuto
                seconds=-now.second,
                microseconds=-now.microsecond
            )
        else:       
            next_time = now + timedelta(minutes=minutes - (now.minute % minutes), seconds=-now.second, microseconds=-now.microsecond)
        
        
        next_candle_time = next_time.strftime('%Y-%m-%d %H:%M:%S')

        # Converte next_candle_time para datetime antes de comparar
        next_candle_time_dt = datetime.strptime(next_candle_time, "%Y-%m-%d %H:%M:%S")
        
        if next_candle_time_dt < now:
            return

        source = None
        if symbol in iq_symbols:
            source = 'otc'
        elif symbol in mt5_symbols:
            source = 'forex'
        elif symbol in binance_symbols:
            source = 'crypto'

        volatility = calculate_volatility(symbol, timeframe, next_candle_time)
        volume = get_volume(symbol, timeframe, next_candle_time)
        indicator = f"Confiança IA {confidence}"

        insert_trading_signal(symbol, timeframe, next_candle_time, direction, source, confidence, volatility, volume, indicator)
        print(f"{symbol}\t{direction}\t{timeframe}\t{next_candle_time}")

    except Exception as e:
        error = f"IA: Erro ao determinar parâmetros finais ou inserir sinal de trading: {e}"
        send_message(bot_alert, admin_chat_id, error)
        print(error)



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

        # Converter a string signal_time para um objeto datetime
        try:
            signal_time = datetime.strptime(signal_time_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            error = "IA: Formato inválido de data. Use '%Y-%m-%d %H:%M:%S'"
            send_message(bot_alert, admin_chat_id, error)
            print(error)
            return None

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
        formatted_time = time

        
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
                    print("Payout indisponível")
                else:
                    payout = float(payout)
                if payout < 70:
                    print("Payout abaixo de 70%")
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
    conn = connect_to_database()
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

    scheduler = BackgroundScheduler()
    scheduler.add_job(gerar_sinais_dinamico, 'cron', day_of_week='fri,sat,sun,mon,tue,wed,thu', hour=23, minute=0, args=[mt5_symbols, iq_symbols, sinais_free])

    scheduler.add_job(connect_to_database, IntervalTrigger(seconds=5))
    scheduler.start()
    all_symbols = get_symbols()
    last_update_time = datetime.now()

    while True:
        connect_to_database()
        current_time = datetime.now()
        if (current_time - last_update_time).total_seconds() >= 1800:
            all_symbols = get_symbols()
            last_update_time = current_time

        for symbol in all_symbols:
            for timeframe in timeframes:
                mapped_timeframe = f'{timeframe}'
                try:
                    # Fazer previsão para o ativo
                    predict_next_candle_with_indicators(symbol, mapped_timeframe)
                except Exception as e:
                    print(f"Erro ao analisar {symbol} no timeframe {mapped_timeframe}: {e}")

        # Esperar um intervalo de tempo antes de rodar o loop novamente (ex: 60 segundos)
        time.sleep(1)

# Iniciar o monitoramento
monitor_opportunities()

