from datetime import datetime, timedelta
import telebot
import time
import schedule
import logging
import os
import asyncio
import pandas as pd
import re
import ativos_iq
from decimal import Decimal
import mysql.connector
from mysql.connector import Error
from configparser import ConfigParser

validacao_ativo = 0
validacao_payout = 0
validacao_volatilidade = 0
validacao_volume = 0

TOKEN = '7163916777:AAEiYa0zMBMmp4xs1LFj_cEkrYpKsvnAGhI'
CHAT_ID_M5 = '-1002099533041'
CHAT_ID_M1 = '-4171341081'

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

loop = asyncio.get_event_loop()

# Configuração de logging
log_dir = "logs"
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

logging.basicConfig(
    filename=os.path.join(log_dir, 'logs_telegram.log'),
    level=logging.INFO,
    format='%(asctime)s %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M'
)


# Adaptador para converter datetime em string para armazenamento
def adapt_datetime(dt):
    return dt.isoformat()

# Conversor para converter string do banco de dados em datetime
def convert_datetime(s):
    return datetime.fromisoformat(s.decode("utf-8"))


def asset_parse(asset):
    if asset is None:
        asset = ["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD", "NZDUSD", "EURGBP", "EURJPY", "GBPJPY", "EURAUD", "EURCHF", "GBPCHF", "AUDJPY", "NZDJPY", "AUDNZD", "GBPAUD"]
  
    if "OTC" in asset:
        return asset
    else:
        # Supondo que o ativo tenha exatamente 6 caracteres, onde os primeiros 3 são a primeira moeda e os últimos 3 são a segunda moeda
        asset = asset.replace("/", "")
        return asset



async def get_open_assets_with_payout():
    open_assets_with_payout = []

    try:
        ensure_connection()
        cursor = conn.cursor()

        # Fetch data from trading_signals table
        cursor.execute("SELECT symbol, payout, status FROM trading_signals")
        payment_data = cursor.fetchall()

        for data in payment_data:
            symbol = data[0]
            payout = data[1]
            status = data[2]

            # Adjust asset format if needed (using your asset_parse function)
            asset_query = asset_parse(symbol)

            if status == 'open':
                if re.match(r'^[A-Z]{3}[A-Z]{3}$', asset_query) or re.match(r'^[A-Z]{3}[A-Z]{3} \(OTC\)$', asset_query):
                    open_assets_with_payout.append((asset_query, payout))

    except Exception as e:
        print("Error fetching open assets with payout:", e)

    return open_assets_with_payout


def fetch_open_assets():
    open_assets_with_payout = asyncio.run(get_open_assets_with_payout())
    open_assets = [asset for asset, _ in open_assets_with_payout]
    return open_assets

def fetch_assets_payout():
    open_assets_with_payout = asyncio.run(get_open_assets_with_payout())
    payouts = [payout for _, payout in open_assets_with_payout]
    return payouts

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


# Inicialização do bot do Telegram
bot = telebot.TeleBot(TOKEN)


def send_signal_to_telegram(bot, chat_id, signal):
    print("Validando sinal")

    signal_id = signal[0]
    signal_time = datetime.strptime(signal[4], "%Y-%m-%d %H:%M:%S")
    symbol = signal[1]
    direction = signal[2]
    timeframe = signal[3]
    volatility = signal[5]
    volume = signal[6]
    payout = signal[7]
    status = signal[8]

    # Extrai o número de minutos do timeframe
    timeframe_minutes = int(timeframe[1:])  # Remove o "M" e converte para inteiro

    # Calcula o horário de gale adicionando o tempo de expiração da vela ao horário original
    gale1_time = signal_time + timedelta(minutes=timeframe_minutes)
    gale2_time = signal_time + timedelta(minutes=2*timeframe_minutes)

    # Buscar informações sobre se o ativo está aberto e o payout atual
    open_assets = fetch_open_assets()
    payouts = fetch_assets_payout()

    # Verificar se o símbolo do sinal está presente na lista de ativos abertos
    if symbol in open_assets:
        print(signal_time.strftime('%H:%M'), symbol, direction, timeframe)

        asset_status = "Ativo aberto"
        # Encontrar o índice do símbolo na lista de ativos abertos para obter o payout correspondente
        asset_index = open_assets.index(symbol)
        current_payout = payouts[asset_index]

    # Se o ativo estiver fechado, retornar uma mensagem ou outro valor
    if validacao_ativo == 1:
        if status != "Aberto":
            print("Ativo fechado")
            return None

    if validacao_payout == 1:
        if payout < 70:
            print("Payout baixo", payout)
            return None
   
    # Verificando a direção e definindo a mensagem de acordo
    if direction == "CALL":
        message_text = f"🟢 Sinal para {symbol} 🟢\n" \
                    f"Horário: {signal_time.strftime('%H:%M')}\n" \
                    f"Expiração da Vela: {timeframe}\n" \
                    f"Direção: {direction}\n" \
                    f"Status IQ Option: {status}\n" \
                    f"Payout: {payout}%\n" \
                    f"---------------------------------------\n" \
                    f"Caso ocorra loss, entrar com gale na proxima vela\n"

    elif direction == "PUT":
        message_text = f"🔴 Sinal para {symbol} 🔴\n" \
                    f"Horário: {signal_time.strftime('%H:%M')}\n" \
                    f"Expiração da Vela: {timeframe}\n" \
                    f"Direção: {direction}\n" \
                    f"Status IQ Option: {status}\n" \
                    f"Payout: {payout}%\n" \
                    f"---------------------------------------\n" \
                    f"Caso ocorra loss, entrar com gale na proxima vela\n"

    try:
        # Enviando a mensagem para o chat do Telegram e retornando o ID da mensagem
        message = bot.send_message(chat_id, message_text)
        return signal_id, message.message_id
    except Exception as e:
        print("Erro ao enviar mensagem no Telegram:", e)
        return None

def send_signals_from_database(bot, CHAT_ID_M5, CHAT_ID_M1):
    try:
        ensure_connection()
        cursor = conn.cursor()

        # Aqui você pode adicionar funções auxiliares como 'ensure_connection' e outras necessárias

        cursor.execute("SELECT id, symbol, direction, timeframe, time, volatility, volume, payout, status FROM trading_signals WHERE sent IS NULL")
        signals = cursor.fetchall()

        if signals:
            open_assets = fetch_open_assets()

            for signal in signals:
                signal_id = signal[0]

                if open_assets is None:
                    print("Nenhum ativo aberto encontrado. Ignorando sinal.")
                    continue

                # Definir o chat_id com base no timeframe do sinal
                chat_id = CHAT_ID_M5 if signal[3] == 'M5' else CHAT_ID_M1

                result = send_signal_to_telegram(bot, chat_id, signal)

                if result is None:
                    cursor.execute("DELETE FROM trading_signals WHERE id = %s", (signal_id,))
                    print("Excluindo o sinal")
                else:
                    signal_id, message_id = result
                    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    cursor.execute("UPDATE trading_signals SET message_id = %s, sent = %s WHERE id = %s", (message_id, current_time, signal_id))

                conn.commit()

    except Exception as e:
        logging.error(f"Erro ao enviar sinais do banco de dados: {e}")

    finally:
        cursor.close()


# Função para responder a uma mensagem no chat do Telegram
def edit_message_in_telegram(bot, chat_id, message_id, new_text):
    try:
        # Enviar a nova mensagem como resposta
        message = bot.send_message(chat_id=chat_id, text=new_text, reply_to_message_id=message_id)
        return True
    except Exception as e:
        print("Erro ao enviar mensagem no Telegram:", e)
        return False

# Função para atualizar mensagens com resultados
def update_messages_with_results(bot, CHAT_ID_M5, CHAT_ID_M1):
    try:
        ensure_connection()
        cursor = conn.cursor()

        # Filtrar os sinais do banco de dados que têm um resultado preenchido e uma mensagem enviada
        cursor.execute("SELECT * FROM trading_signals WHERE result IS NOT NULL AND message_id IS NOT NULL AND edited IS NULL")
        signals_with_results = cursor.fetchall()

        for signal in signals_with_results:
            signal_id = signal[0]
            result = signal[5]
            message_id = signal[6]
            signal_time = datetime.strptime(signal[4], "%Y-%m-%d %H:%M:%S")
            symbol = signal[1]
            direction = signal[2]
            timeframe = signal[3]

            chat_id = CHAT_ID_M5 if timeframe == 'M5' else CHAT_ID_M1

            if message_id:
                # Formatando a mensagem com o resultado
                new_message_text = f"{result}"

                # Editar a mensagem no chat do Telegram
                if edit_message_in_telegram(bot, chat_id, message_id, new_message_text):
                    # Atualizar a coluna edited para indicar que a mensagem foi editada com sucesso
                    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    cursor.execute("UPDATE trading_signals SET edited = ? WHERE id = ?", (current_time, signal_id,))
                    conn.commit()


    except Exception as e:
        print("Erro ao atualizar mensagens com resultados:", e)

# Função para obter preços de abertura e fechamento da tabela candle_history
def fetch_prices_from_candle_history(symbol, timeframe, signal_time):
    ensure_connection()
    cursor = conn.cursor()

    # Converter signal_time para string no formato correto
    signal_time_str = signal_time.strftime('%Y-%m-%d %H:%M:%S')

    print(symbol, timeframe, signal_time_str)
    query = """
        SELECT open, close FROM candle_history 
        WHERE symbol = %s AND timeframe = %s AND time = %s
    """
    cursor.execute(query, (symbol, timeframe, signal_time_str))
    row = cursor.fetchone()
    if row:
        return row[0], row[1]
    else:
        return None, None



def calculate_next_candle_time(signal_time, timeframe):
    if timeframe.startswith('M'):  # minutos
        minutes = int(timeframe[1:])
        return signal_time + timedelta(minutes=minutes)
    elif timeframe.startswith('H'):  # horas
        hours = int(timeframe[1:])
        return signal_time + timedelta(hours=hours)
    elif timeframe.startswith('D'):  # dias
        days = int(timeframe[1:])
        return signal_time + timedelta(days=days)
    else:
        raise ValueError(f"Timeframe {timeframe} não suportado")

def calculate_previous_candle_time(signal_time, timeframe):
    if timeframe.startswith('M'):  # minutos
        minutes = int(timeframe[1:])
        return signal_time - timedelta(minutes=minutes)
    elif timeframe.startswith('H'):  # horas
        hours = int(timeframe[1:])
        return signal_time - timedelta(hours=hours)
    elif timeframe.startswith('D'):  # dias
        days = int(timeframe[1:])
        return signal_time - timedelta(days=days)
    else:
        raise ValueError(f"Timeframe {timeframe} não suportado")


# Função para atualizar a tabela trading_signals com os preços de abertura e fechamento
def update_prices_in_database():
    try:
        ensure_connection()
        cursor = conn.cursor()

        # Filtrar os sinais do banco de dados que ainda não têm preços de abertura e fechamento
        cursor.execute("SELECT * FROM trading_signals WHERE open IS NULL OR close IS NULL OR open_g1 IS NULL OR close_g1 IS NULL OR open_g2 IS NULL OR close_g2 IS NULL")
        signals_to_update = cursor.fetchall()

        for signal in signals_to_update:
            signal_id = signal[0]
            symbol = signal[1]
            timeframe = signal[3]  # Pegando o timeframe da tabela trading_signals
            signal_time = datetime.strptime(signal[4], "%Y-%m-%d %H:%M:%S")
            # Vela do sinal original
            open_price, close_price = fetch_prices_from_candle_history(symbol, timeframe, signal_time)

            # Inicializando variáveis das velas subsequentes
            open_g1, close_g1, open_g2, close_g2 = None, None, None, None

            if open_price is not None and close_price is not None:
                # Vela 1 (G1)
                next_time_g1 = calculate_next_candle_time(signal_time, timeframe)
                open_g1, close_g1 = fetch_prices_from_candle_history(symbol, timeframe, next_time_g1)

                # Vela 2 (G2)
                if open_g1 is not None and close_g1 is not None:
                    next_time_g2 = calculate_next_candle_time(next_time_g1, timeframe)
                    open_g2, close_g2 = fetch_prices_from_candle_history(symbol, timeframe, next_time_g2)
                    # Atualizar a tabela trading_signals com todos os preços obtidos
                    print(open_price, close_price, open_g1, close_g1, open_g2, close_g2, signal_id)
                    cursor.execute("""
                        UPDATE trading_signals
                        SET open = %s, close = %s, open_g1 = %s, close_g1 = %s, open_g2 = %s, close_g2 = %s
                        WHERE id = %s
                    """, (open_price, close_price, open_g1, close_g1, open_g2, close_g2, signal_id))
                    conn.commit()


    except Exception as e:
        print("Erro ao atualizar preços no banco de dados:", e)



# Função para verificar os resultados e adicionar na coluna Result como WIN, WIN G1, WIN G2, etc. ou LOSS
def check_results():
    try:
        ensure_connection()
        cursor = conn.cursor()

        # Filtrar os sinais do banco de dados que ainda não têm um resultado preenchido
        cursor.execute("SELECT * FROM trading_signals WHERE result IS NULL AND open IS NOT NULL AND close IS NOT NULL")

        signals_to_check = cursor.fetchall()

        for signal in signals_to_check:
            signal_id = signal[0]
            direction = signal[2]
            open_price = signal[9]
            close_price = signal[10]

           
            # Determinar o resultado baseado na direção do sinal e nos preços de abertura e fechamento
            if open_price is not None and close_price is not None:
                if direction == 'CALL' and close_price > open_price:
                    result = "WIN ✅"
                elif direction == 'PUT' and close_price < open_price:
                    result = "WIN ✅"
                elif direction == 'PUT' and close_price == open_price:
                    result = "DOJI"
                else:
                    result = "LOSS"

                # Se o resultado inicial for LOSS, verifique G1 e G2 se as informações estiverem disponíveis
                if result == "LOSS":
                    open_g1 = signal[11]
                    close_g1 = signal[12]
                    open_g2 = signal[13]
                    close_g2 = signal[14]

                    if open_g1 is not None and close_g1 is not None:
                        if direction == 'CALL' and close_g1 > open_g1:
                            result = "WIN ✅🐔"
                        elif direction == 'PUT' and close_g1 < open_g1:
                            result = "WIN ✅🐔"
                        else:
                            if open_g2 is not None and close_g2 is not None:
                                if direction == 'CALL' and close_g2 > open_g2:
                                    result = "WIN ✅🐔🐔"
                                elif direction == 'PUT' and close_g2 < open_g2:
                                    result = "WIN ✅🐔🐔"
                                else:
                                    result = "LOSS ❌"
                            else:
                                # Se as informações sobre G1 ou G2 não estiverem disponíveis, mantenha o resultado como "LOSS"
                                continue
                    else:
                        # Se as informações sobre G1 ou G2 não estiverem disponíveis, mantenha o resultado como "LOSS"
                        continue

                # Atualizar o registro no banco com o resultado
                cursor.execute("UPDATE trading_signals SET result = ? WHERE id = ?", (result, signal_id))
                conn.commit()
                print(f"Resultado atualizado para sinal ID: {signal_id} - {result}")

            else:
                print(f"Não foi possível determinar o resultado para o sinal ID: {signal_id}. Preço de fechamento não disponível.")


    except Exception as e:
        print("Erro ao verificar resultados:", e)



# Função para enviar o relatório diário
def send_daily_report(bot, chat_id, period):
    try:
        ensure_connection()
        cursor = conn.cursor()

        # Calcular o intervalo de tempo das últimas 6 horas
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        start_time = (datetime.now() - timedelta(hours=6)).strftime('%Y-%m-%d %H:%M:%S')

        # Consultar os sinais das últimas 6 horas que têm resultados diferentes de None
        cursor.execute("SELECT * FROM trading_signals WHERE datetime(time) BETWEEN ? AND ? AND result IS NOT NULL", (start_time, now))
        signals = cursor.fetchall()


        
        # Adicionando print para depuração
        print("Sinais encontrados:", signals)

        win_count = 0
        wing1_count = 0
        wing2_count = 0
        loss_count = 0
        doji_count = 0

        period_messages = {
            "madrugada": "Relatório dos sinais da madrugada:\n",
            "manha": "Relatório dos sinais da manhã:\n",
            "tarde": "Relatório dos sinais da tarde:\n",
            "noite": "Relatório dos sinais da noite:\n"
        }

        message_lines = [period_messages[period]]

        if not signals:
            message_lines.append("Nenhum sinal encontrado no período especificado.")
        else:
            for signal in signals:
                signal_time = datetime.strptime(signal[4], "%Y-%m-%d %H:%M:%S")
                symbol = signal[1]
                direction = signal[2]
                timeframe = signal[3]
                result = signal[5]

                message_lines.append(f"{signal_time.strftime('%H:%M')} {symbol} {direction} {timeframe} - {result}")

                if "WIN ✅" == result:
                    win_count += 1
                elif "WIN ✅🐔" == result:
                    wing1_count += 1
                elif "WIN ✅🐔🐔" == result:
                    wing2_count += 1
                elif "LOSS" in result:
                    loss_count += 1
                elif "DOJI" in result:
                    doji_count += 1

            total_signals = win_count + wing1_count + wing2_count + loss_count
            wincount_count = win_count + wing1_count + wing2_count
            win_percentage = (wincount_count / total_signals) * 100 if total_signals > 0 else 0
            win_percentage_nogale = (win_count / total_signals) * 100 if total_signals > 0 else 0

            message_lines.append("\nContagem de Resultados:")
            message_lines.append(f"WIN: {win_count}")
            message_lines.append(f"WIN 🐔: {wing1_count}")
            message_lines.append(f"WIN 🐔🐔: {wing2_count}")
            message_lines.append(f"LOSS: {loss_count}")
            message_lines.append(f"DOJI: {doji_count}")
            message_lines.append(f"Porcentagem de acerto: {win_percentage:.2f}%")
            message_lines.append(f"Porcentagem de acerto sem gale: {win_percentage_nogale:.2f}%")

        report_message = "\n".join(message_lines)

        # Enviar a mensagem do relatório para o chat do Telegram
        bot.send_message(chat_id, report_message)


    except Exception as e:
        print("Erro ao enviar relatório diário:", e)

schedule.every().day.at("08:00").do(send_signals_from_database,  bot, CHAT_ID_M5, CHAT_ID_M1)
schedule.every().day.at("12:00").do(send_signals_from_database,  bot, CHAT_ID_M5, CHAT_ID_M1)
schedule.every().day.at("16:00").do(send_signals_from_database,  bot, CHAT_ID_M5, CHAT_ID_M1)
schedule.every().day.at("20:00").do(send_signals_from_database,  bot, CHAT_ID_M5, CHAT_ID_M1)
schedule.every().day.at("00:00").do(send_signals_from_database,  bot, CHAT_ID_M5, CHAT_ID_M1)




def get_volume():
    # Conectando aos bancos de dados
    ensure_connection()


    cursor = conn.cursor()


    # Consulta para obter os sinais de negociação
    query_signals = """
    SELECT symbol, timeframe, time FROM trading_signals
    """
    
    cursor.execute(query_signals)
    signals = cursor.fetchall()

    # Para cada sinal, calcular o tempo da vela 10 minutos antes
    for signal in signals:
        symbol, timeframe, signal_time_str = signal
        
        # Convertendo o tempo do sinal para um objeto datetime
        signal_time = datetime.strptime(signal_time_str, "%Y-%m-%d %H:%M:%S")
        
        # Calculando o tempo 10 minutos antes
        previous_time = signal_time - timedelta(minutes=10)
        previous_time_str = previous_time.strftime("%Y-%m-%d %H:%M:%S")

        # Consulta para obter o volume da vela 10 minutos antes
        query_candles = """
        SELECT tick_volume FROM candle_history
        WHERE symbol = ? AND timeframe = ? AND time = ?
        """
        
        cursor.execute(query_candles, (symbol, timeframe, previous_time_str))
        result = cursor.fetchone()

        if result:
            tick_volume = result[0]
        else:
            # Se não encontrar a vela, definir o volume como None ou 0
            tick_volume = None  # ou 0, dependendo do comportamento desejado

        # Atualizar o volume na tabela de sinais de negociação
        update_query = """
        UPDATE trading_signals
        SET volume = ?
        WHERE symbol = ? AND timeframe = ? AND time = ?
        """
        
        cursor.execute(update_query, (tick_volume, symbol, timeframe, signal_time_str))

    conn.commit()


def calculate_volatility(symbol, timeframe, signal_time, periods=30):
    ensure_connection()
    cursor = conn.cursor()

    # Obter os preços de open, high, low e close dos últimos 'periods' períodos + 1ssss (para o cálculo do true range)
    query = """
        SELECT time, open, high, low, close FROM candle_history 
        WHERE symbol = %s AND timeframe = %s AND time <= %s
        ORDER BY time DESC LIMIT %s
    """
    cursor.execute(query, (symbol, timeframe, signal_time.strftime('%Y-%m-%d %H:%M:%S'), periods + 1))
    rows = cursor.fetchall()
    

    if len(rows) < periods + 1:
        return None

    # Converter os dados para um DataFrame para facilitar o cálculo
    df = pd.DataFrame(rows, columns=['time', 'open', 'high', 'low', 'close'])
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
def update_volatility_in_database():
    try:
        ensure_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM trading_signals WHERE volatility IS NULL")
        signals_to_update = cursor.fetchall()

        for signal in signals_to_update:
            signal_id = signal[0]
            symbol = signal[1]
            timeframe = signal[3]
            signal_time = datetime.strptime(signal[4], "%Y-%m-%d %H:%M:%S")

            volatility = calculate_volatility(symbol, timeframe, signal_time)
            if volatility is not None:
                cursor.execute("UPDATE trading_signals SET volatility = %s WHERE id = %s", (volatility, signal_id))
                conn.commit()


    except Exception as e:
        print("Erro ao atualizar volatilidade no banco de dados:", e)



# Função para inicializar o sistema e verificar sinais sem resultados
def initialize_system():
    print("Inicializando o sistema e verificando sinais sem resultados...")
    update_prices_in_database()
    check_results()
    send_signals_from_database(bot, CHAT_ID_M5, CHAT_ID_M1)

# Inicializar o sistema e verificar sinais sem resultados
initialize_system()

# Loop para verificar e enviar novos sinais periodicamente, atualizar mensagens com resultados e executar tarefas agendadas
while True:
    ensure_connection()
    send_signals_from_database(bot, CHAT_ID_M5, CHAT_ID_M1)
    update_prices_in_database()
    update_volatility_in_database()  # Atualizar volatilidade no loop principal
    check_results()
    update_messages_with_results(bot, CHAT_ID_M5, CHAT_ID_M1)
    
    schedule.run_pending()  # Executa tarefas agendadas se for o horário
    time.sleep(1)  # Verifica novamente a cada 5 segundos




