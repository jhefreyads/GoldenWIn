import telebot
from iqoptionapi.stable_api import IQ_Option
import time
from datetime import datetime, timedelta
from configparser import ConfigParser
import schedule
from db_connection import get_connection
import json
from decimal import Decimal
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger


config = ConfigParser()
config.read('config.ini')
TOKEN = config.get('Telegram', 'TOKEN')
CHAT_ID_M5 = int(config.get('Telegram', 'CHAT_ID_M5'))
CHAT_ID_M5_OTC = int(config.get('Telegram', 'CHAT_ID_M5_OTC'))
CHAT_ID_M1 = int(config.get('Telegram', 'CHAT_ID_M1'))
CHAT_ID_M1_OTC = int(config.get('Telegram', 'CHAT_ID_M1_OTC'))
CHAT_ID_M15 = int(config.get('Telegram', 'CHAT_ID_M15'))
CHAT_ID_M15_OTC = int(config.get('Telegram', 'CHAT_ID_M15_OTC'))
CHAT_ID_FREE = int(config.get('Telegram', 'CHAT_ID_FREE'))
iq_symbols = config.get('Candles', 'iq_symbols').split(', ')
mt5_symbols = config.get('Candles', 'mt5_symbols').split(', ')

valid_symbols = iq_symbols + mt5_symbols

chat_ids = [CHAT_ID_M1, CHAT_ID_M5, CHAT_ID_M15, CHAT_ID_M1_OTC, CHAT_ID_M5_OTC, CHAT_ID_M15_OTC, CHAT_ID_FREE]

scheduler = BackgroundScheduler()

bot = telebot.TeleBot(TOKEN)

def connect_to_database():
    conn = get_connection()
    return conn

conn = connect_to_database() 


def send_to_front(user_id, message_text):
    print(message_text)


def send_info_to_user(user_id, chat_id, message_text):
    sent_message = bot.send_message(chat_id, message_text)
    send_to_front(user_id, message_text)

    # Armazena o ID da mensagem e o texto como uma string
    message_data = f"{sent_message.message_id}|{message_text}"  # Usa "|" como separador
    return message_data, message_data


def edit_telegram_message(user_id, chat_id, message_text, message_id=None, response_id=None):
    try:
        if response_id:
            # Para response_id, obtém o texto original do response_id
            original_message_text = response_id.split('|', 1)[1]
            updated_message = f"{original_message_text}\n----------\n{message_text}"
            bot.delete_message(chat_id, response_id.split('|', 1)[0])
            sent_message = bot.send_message(chat_id, updated_message)
            send_to_front(user_id, message_text)
            message_data = f"{sent_message.message_id}|{original_message_text}" 
            return message_data
        elif message_id:
            # Para message_id, usa apenas o ID para editar a mensagem
            message_id_str = message_id.split('|', 1)[0]  # Usa apenas o ID
            bot.delete_message(chat_id, message_id_str)
            sent_message = bot.send_message(chat_id, message_text)   
            message_data = f"{sent_message.message_id}|{message_text}" 
            send_to_front(user_id, message_text)
            return message_data, message_data 
   
        
    except Exception as e:
        print(f"Erro ao editar mensagem no Telegram: {e}")





def get_timeframe_in_seconds(timeframe):
    # Mapeamento de timeframes para segundos
    timeframes = {
        "M1": 60,       # 1 minuto = 60 segundos
        "M5": 300,      # 5 minutos = 5 * 60 segundos
        "M15": 900,     # 15 minutos = 15 * 60 segundos
        "M30": 1800,    # 30 minutos = 30 * 60 segundos
        "H1": 3600      # 1 hora = 60 * 60 segundos
    }
    
    # Retorna o valor em segundos correspondente ao timeframe
    return timeframes.get(timeframe, None)  # Retorna None se o timeframe não existir

def get_timeframe_in_minutes(timeframe):
    # Mapeamento de timeframes para segundos
    timeframes = {
        "M1": 1,       # 1 minuto = 60 segundos
        "M5": 5,      # 5 minutos = 5 * 60 segundos
        "M15": 15,     # 15 minutos = 15 * 60 segundos
        "M30": 30,    # 30 minutos = 30 * 60 segundos
        "H1": 60      # 1 hora = 60 * 60 segundos
    }
    
    # Retorna o valor em segundos correspondente ao timeframe
    return timeframes.get(timeframe, None)  # Retorna None se o timeframe não existir

def get_auto_users(group_chat_id):
    connect_to_database()
    cursor = conn.cursor()
    group_chat = None

    if group_chat_id == CHAT_ID_FREE:
        group_chat = "FREE"
    elif group_chat_id == CHAT_ID_M1:
        group_chat = "M1"
    elif group_chat_id == CHAT_ID_M5:
        group_chat = "M5"
    elif group_chat_id == CHAT_ID_M15:
        group_chat = "M15"
    elif group_chat_id == CHAT_ID_M1_OTC:
        group_chat = "M1_OTC"
    elif group_chat_id == CHAT_ID_M5_OTC:
        group_chat = "M5_OTC"
    elif group_chat_id == CHAT_ID_M15_OTC:
        group_chat = "M15_OTC"

    if group_chat is None:
        print("Grupo de chat inválido.")
        return []

    current_time = datetime.now().strftime('%H:%M')

    try:
        query = """
        SELECT id
        FROM users
        WHERE config->'iq_bot'->>'auto' = '1'
          AND config->'telegram'->'chat_ids' @> to_jsonb(%s::text[])
          AND config->'iq_bot'->>'hora_inicio' <= %s
          AND config->'iq_bot'->>'hora_fim' >= %s;
        """
        connect_to_database()
        cursor = conn.cursor()
        cursor.execute(query, ([group_chat], current_time, current_time))  # Passando group_chat e o horário atual
        result = cursor.fetchall()
        cursor.close()
        return [row[0] for row in result]  # Retorna uma lista de user_ids
    except Exception as e:
        print(f"Erro ao obter usuários automáticos: {e}")
        return []


def get_user_config(user_id):
    connect_to_database()
    try:
        # Define a consulta SQL
        query = """
        SELECT config, tele_user
        FROM users
        WHERE id = %s;
        """
        
        # Conecta ao banco de dados
        conn = connect_to_database()  # Presumindo que esta função retorna uma conexão
        cursor = conn.cursor()

        # Executa a consulta
        cursor.execute(query, (user_id,))
        result = cursor.fetchone()  # Obtenha uma única linha de resultado
        cursor.close()

        if result:
            config_json, chat_user_id = result  # Desempacotando o resultado
            
            # Verifica se a configuração é uma string JSON
            if isinstance(config_json, str):  # Se for uma string, converte para dicionário
                user_config = json.loads(config_json)
            elif isinstance(config_json, dict):  # Se já for um dicionário, usa diretamente
                user_config = config_json
            else:
                print("Formato de configuração inválido.")
                return None

            return user_config, chat_user_id
        else:
            print(f"Usuário {user_id} não encontrado")
            return None
            
    except Exception as e:
        print(f"Erro ao obter as configurações: {e}")
        return None


def get_user_totals(user_id):
    connect_to_database()
    # Obter a data de hoje no formato correto
    today = datetime.today().strftime('%Y-%m-%d')
    # Consultar resultados diários para o usuário e data de hoje
    query = """
    SELECT SUM(profit::numeric) AS total_profit
    FROM scheduled_signals
    WHERE DATE(signal_time) = %s AND user_id = %s;
    """
    connect_to_database()
    cursor = conn.cursor()
    cursor.execute(query, (today, user_id))
    daily_result = cursor.fetchone()
    cursor.close()

    # Verificar se daily_result é None ou se o valor retornado é None
    if daily_result is None or daily_result[0] is None:
        return 0
    
    return daily_result[0]


def get_result_message(user_id, result, profit, op_result, stop_win, stop_loss, api):
    connect_to_database()
    
    try:
        daily_result = float(get_user_totals(user_id)) + float(op_result)
    except Exception as e:
        print(f"falha ao ajustar dayli result {e}")

    try:
        balance = api.get_balance()
        if op_result > 0:
            if daily_result > 0:
                result_message = (
                    f'{result}\n'
                    f'💰 Lucro da operação: R${round(op_result, 2)}\n'
                    f'💸 Lucro acumulado: R${round(daily_result, 2)}\n'
                    f"💲 Balanço atual: R${balance:.2f}.\n"
                    f'📈 Stop Win: R${round(stop_win, 2)}\n'
                    f'📊 Continue assim! Mantenha o foco nas suas estratégias!'
                )
            elif daily_result < 0:
                result_message = (
                    f'{result}\n'
                    f'💰 Lucro da operação: R${round(op_result, 2)}\n'
                    f'💸 Prejuizo acumulado: R${round(daily_result, 2)}\n'
                    f"💲 Balanço atual: R${balance:.2f}.\n"
                    f'🔒 Stop Loss: R${round(stop_loss, 2)}\n'
                    f'⚠️ Foco na recuperação! Aprenda com cada operação.'
                )
            elif daily_result == 0:
                result_message = (
                    f'{result}\n'
                    f'💰 Lucro da operação: R${round(op_result, 2)}\n'
                    f'💸 Lucro acumulado: R${round(daily_result, 2)}\n'
                    f"💲 Balanço atual: R${balance:.2f}.\n"
                    f'📈 Stop Win: R${round(stop_win, 2)}\n'
                    f'🔒 Stop Loss: R${round(stop_loss, 2)}\n'
                    f'⚠️ Estamos no 0 x 0! Foco no lucro.'
                )    
            else:
                result_message = (
                    f'{result}\n'
                    f'💰 Lucro da operação: R${round(op_result, 2)}\n'
                    f'💸 Lucro acumulado: R${round(daily_result, 2)}\n'
                    f"💲 Balanço atual: R${balance:.2f}.\n"
                    f'📈 Stop Win: R${round(stop_win, 2)}\n'
                    f'🔒 Stop Loss: R${round(stop_loss, 2)}'
                )      
        elif op_result <= 0:
            if daily_result > 0:
                result_message = (
                    f'{result}\n'
                    f'💰 Prejuízo da operação: R${round(op_result, 2)}\n'
                    f'💸 Lucro acumulado: R${round(daily_result, 2)}\n'
                    f"💲 Balanço atual: R${balance:.2f}.\n"
                    f'📈 Stop Win: R${round(stop_win, 2)}\n'
                    f'🔒 Stop Loss: R${round(stop_loss, 2)}\n'
                    f'⚠️ Não desanime! Você ainda está no lucro! Cada operação é uma oportunidade de aprendizado.'
                )
            elif daily_result < 0:
                result_message = (
                    f'{result}\n'
                    f'💰 Prejuízo da operação: R${round(op_result, 2)}\n'
                    f'💸 Prejuízo acumulado: R${round(daily_result, 2)}\n'
                    f"💲 Balanço atual: R${balance:.2f}.\n"
                    f'🔒 Stop Loss: R${round(stop_loss, 2)}\n'
                    f"⚠️ É importante proteger seu capital. Considere revisar suas estratégias!\n"
                    f"💪 Não desanime! Cada operação é uma oportunidade de aprendizado."
                )
            elif daily_result == 0:
                result_message = (
                    f'{result}\n'
                    f'💰 Prejuízo da operação: R${round(op_result, 2)}\n'
                    f'💸 Lucro acumulado: R${round(daily_result, 2)}\n'
                    f"💲 Balanço atual: R${balance:.2f}.\n"
                    f'📈 Stop Win: R${round(stop_win, 2)}\n'
                    f'🔒 Stop Loss: R${round(stop_loss, 2)}\n'
                    f'⚠️ Estamos no 0 x 0! Foco no lucro.'
                )    
            else:
                result_message = (
                    f'{result}\n'
                    f'💰 Lucro da operação: R${round(op_result, 2)}\n'
                    f'💸 Lucro acumulado: R${round(daily_result, 2)}\n'
                    f"💲 Balanço atual: R${balance:.2f}.\n"
                    f'📈 Stop Win Atual: R${round(stop_win, 2)}\n'
                    f'🔒 Stop Loss Atual: R${round(stop_loss, 2)}'
                )    
        return result_message    
    except Exception as e:
        print(f"Falha ao determinar mensagem {e}")

def trade_with_signal(user_id, message_id, response_id, signal_time, symbol, direction, timeframe):
    connect_to_database()
    attempt = 0 
    try:
        # Exemplo de leitura das configurações de um usuário
        config, chat_id = get_user_config(user_id)  # Passando a conexão 'conn' também
        if config:
            # Acessa a seção 'iq_bot' e suas configurações
            iq_login = config.get("iq_bot").get("iq_login")
            iq_password = config.get("iq_bot").get("iq_password")
            amount = float(config.get("iq_bot").get("amount"))  # Certifique-se de que seja float
            gale = int(config.get("iq_bot").get("gale"))  # Certifique-se de que seja int
            multiplier = float(config.get("iq_bot").get("multiplier"))  # Certifique-se de que seja float
            balance_type = config.get("iq_bot").get("balance_type")
            stop_win = float(config.get("iq_bot").get("stop_win", 0))  # Valor de Stop Win
            stop_loss = float(config.get("iq_bot").get("stop_loss", 0))  # Valor de Stop Loss
        else:
            return "404, Config", 0

        timeframe_minutes = get_timeframe_in_minutes(timeframe)
        api = IQ_Option(iq_login, iq_password)
        api.connect()
        api.change_balance(balance_type)
        user_stop = False
        user_stop = check_user_stop(user_id, api, stop_win, stop_loss, amount, gale, multiplier, chat_id)
        if user_stop:
            return
        balance = api.get_balance()
        profit = 0.0
        op_result = 0.0
        execute_message = (
            f"🚀 Operação em Andamento\n"
            f"⏰ Horário: {signal_time}\n"
            f"📈 Ativo: {symbol}\n"
            f"🔼 Direção: {direction}\n"
            f"💰 Valor: R${amount}\n"
            f"⏳ Expiração: {timeframe}\n"
            f"📊 Aguarde os resultados."
        )
        status, order_id = api.buy_digital_spot_v2(symbol, amount, direction, timeframe_minutes)
        
        message_id, response_id = edit_telegram_message(user_id, chat_id, execute_message, message_id, None)       
        if status:
            profit = check_result(api, order_id)  # Chama a função para verificar o resultado
            try:
                op_result += profit
            except Exception as e:
                print(f"Erro ao adicionar profit: {str(e)}")    
            # Após a execução da operação, verifique o resultado
            if profit > 0:
                result = "✅ WIN ✅"
                result_message = get_result_message(user_id, result, profit, op_result, stop_win, stop_loss, api)                                    
                response_id = edit_telegram_message(user_id, chat_id, result_message, None, response_id)
                return result, op_result
            
            elif profit == amount:
                result = "💤 DOJI 💤"
                result_message = get_result_message(user_id, result, profit, op_result, stop_win, stop_loss, api)                                                    
                response_id = edit_telegram_message(user_id, chat_id, result_message, None, response_id)
                return result, op_result

            elif profit < 0:
                result = "🔻 LOSS 🔻"
                if gale > 0:
                    attempt += 1
                    amount_g1 = amount * multiplier
                    status_g1, order_id_g1 = api.buy_digital_spot_v2(symbol, amount_g1, direction, timeframe_minutes)
                    result_message_g1 = (
                        f"⚠️ {result}! Iniciando Gale {attempt} com valor de R${amount_g1:.2f}."
                    )
                    response_id = edit_telegram_message(user_id, chat_id, result_message_g1, None, response_id)

                    # Resultado do Gale 1
                    if status_g1:
                        daily_result_msg = get_user_totals(user_id)
                        profit_g1 = check_result(api, order_id_g1)  # Chama a função para verificar o resultado
                        try:
                            op_result += profit_g1
                        except Exception as e:
                            print(f"Erro ao adicionar profit: {str(e)}")   
                        if profit_g1 > 0:
                            result = "✅ WIN G1 ✅"
                            result_message = get_result_message(user_id, result, profit, op_result, stop_win, stop_loss, api)                                    
                            response_id = edit_telegram_message(user_id, chat_id, result_message, None, response_id)
                            return result, op_result 
                        else:
                            result = "🔻 LOSS G1 🔻"
                            if gale > 1:
                                attempt += 1
                                amount_g2 = amount_g1 * multiplier
                                status_g2, order_id_g2 = api.buy_digital_spot_v2(symbol, amount_g2, direction, timeframe_minutes)
                                result_g2_message = (
                                    f"⚠️ {result}! Iniciando Gale {attempt} com valor de R${amount_g2:.2f}."
                                )
                                response_id = edit_telegram_message(user_id, chat_id, result_g2_message, None, response_id)
                                if status_g2:
                                    profit_g2 = check_result(api, order_id_g2)  # Chama a função para verificar o resultado
                                    try:
                                        op_result += profit_g2
                                    except Exception as e:
                                        print(f"Erro ao adicionar profit: {str(e)}")
                                    if profit_g2 > 0:
                                        result = "✅ WIN G2 ✅"
                                        result_message = get_result_message(user_id, result, profit, op_result, stop_win, stop_loss, api)                                    
                                        response_id = edit_telegram_message(user_id, chat_id, result_message, None, response_id)
                                        return result, op_result  
                                    else:
                                        result = "🔻 LOSS G2 🔻"
                                        result_message = get_result_message(user_id, result, profit, op_result, stop_win, stop_loss, api)                                    
                                        response_id = edit_telegram_message(user_id, chat_id, result_message, None, response_id)
                                        return result, op_result 
                                else:
                                    result_message = get_result_message(user_id, result, profit, op_result, stop_win, stop_loss, api)                                    
                                    response_id = edit_telegram_message(user_id, chat_id, result_message, None, response_id)
                                    return result, op_result  
                            else:
                                result_message = get_result_message(user_id, result, profit, op_result, stop_win, stop_loss, api)                                    
                                response_id = edit_telegram_message(user_id, chat_id, result_message, None, response_id)
                                return result, op_result        
            else:
                result = " Falha "
                fail_message = "❌ Falha ao executar a operação."
                return result, 0
        else:
            return "Config not found", 0
    except Exception as e:
        print(f"Error: {str(e)}")

def check_result(api, order_id):
    while True:
        time.sleep(0.2)  # Espera 0.2 segundos
        profit, valor = api.check_win_digital_v2(order_id)
        if valor is not None:  # Se um valor válido foi retornado
            return float(valor)


def stop_sent_flag(user_id, user_stop_win, user_stop_loss, chat_id, message): 
    today = datetime.today().strftime('%Y-%m-%d')
    connect_to_database()  # Abre a conexão com o banco
    cursor = conn.cursor()
    
    try:
        query = """
        INSERT INTO user_stop (user_id, user_stop_win, user_stop_loss, date)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (user_id, date) 
        DO UPDATE SET user_stop_win = EXCLUDED.user_stop_win, 
                      user_stop_loss = EXCLUDED.user_stop_loss;
        """
        cursor.execute(query, (user_id, user_stop_win, user_stop_loss, today))
        conn.commit()  # Confirma a transação
        
        bot.send_message(chat_id, message)
    except Exception as e:
        print(f"Erro ao enviar a mensagem ou inserir/atualizar no banco: {e}")
    finally:
        cursor.close()  # Fecha o cursor
    return True


def listen_to_signals():
    
    try:
        connect_to_database()
        cursor = conn.cursor()
        now = datetime.now()  # Captura o horário atual
        query = """
            SELECT time, symbol, direction, timeframe, source 
            FROM trading_signals 
            WHERE result IS NULL AND TO_TIMESTAMP(time, 'YYYY-MM-DD HH24:MI:SS') > %s
        """
        
        # Passa 'now' como uma tupla
        cursor.execute(query, (now,))  # Nota: a vírgula aqui é importante para criar uma tupla
        signals_to_schedule = cursor.fetchall()  # Chama corretamente o método fetchall()
        
        # Verifique se a lista de sinais está vazia
        if not signals_to_schedule:
            return
        
        for signal_to_schedule in signals_to_schedule:
            if len(signal_to_schedule) != 5:  # Verifique se há 5 elementos a serem desempacotados
                print(f"Formato inesperado de sinal: {signal_to_schedule}")
                continue
            
            signal_time, symbol, direction, timeframe, source = signal_to_schedule
            group_chat_id = None
            
            if source == "otc":
                if timeframe == "M1":
                    group_chat_id = CHAT_ID_M1_OTC
                elif timeframe == "M5":
                    group_chat_id = CHAT_ID_M5_OTC    
                elif timeframe == "M15":
                    group_chat_id = CHAT_ID_M15_OTC  
                
            elif source == "forex":
                if timeframe == "M1":
                    group_chat_id = CHAT_ID_M1
                elif timeframe == "M5":
                    group_chat_id = CHAT_ID_M5   
                elif timeframe == "M15":
                    group_chat_id = CHAT_ID_M15  
            
            elif source == "list" and not symbol.endswith('-OTC'):
                if timeframe == "M1":
                    group_chat_id = CHAT_ID_M1
                elif timeframe == "M5":
                    group_chat_id = CHAT_ID_M5   
                elif timeframe == "M15":
                    group_chat_id = CHAT_ID_M15    
            
            elif source == "list" and symbol.endswith('-OTC'):
                if timeframe == "M1":
                    group_chat_id = CHAT_ID_M1_OTC
                elif timeframe == "M5":
                    group_chat_id = CHAT_ID_M5_OTC   
                elif timeframe == "M15":
                    group_chat_id = CHAT_ID_M15_OTC    
            
            else:
                return

            if group_chat_id:
                schedule_signal_for_all_users(signal_time, symbol, direction, timeframe, group_chat_id, source)
            else:
                print(f"Timeframe {timeframe} não reconhecido para o sinal {symbol}")
            cursor.close()    
    except Exception as e:
        print(f"Não foi possível localizar os sinais no banco de dados: {e}")




def schedule_signal_for_all_users(signal_time, symbol, direction, timeframe, group_chat_id, source):
    user_ids = get_auto_users(group_chat_id)
    for user_id in user_ids:
        schedule_signal(user_id, signal_time, symbol, direction, timeframe, source)

def check_user_stop(user_id, api, stop_win, stop_loss, amount, gale, multiplier, chat_id):
    connect_to_database()
    today = datetime.today().strftime('%Y-%m-%d')
    cursor = conn.cursor()
    user_stop = False
    # Consulta para verificar o status de user_stop
    query = """
        SELECT user_stop_win, user_stop_loss 
        FROM user_stop
        WHERE user_id = %s AND DATE(date) = %s
    """   
    cursor.execute(query, (user_id, today))
    user_stop_data = cursor.fetchone()  # Pega apenas uma linha

    if user_stop_data is not None:
        user_stop_win, user_stop_loss = user_stop_data
    else:
        user_stop_win, user_stop_loss = False, False  # Se não houver registro para hoje, assume ambos como False
    
    daily_result = float(get_user_totals(user_id))
    balance = float(api.get_balance())  # Certifique-se de que o saldo seja float
    
    message = None
    if user_stop_win or user_stop_loss:
        return True

    else:    
        # Validações de Stop Loss
        if stop_loss not in (None, 0):
            if (daily_result - amount) < stop_loss * -1 and gale == 0:
                message = (
                    f"🚨 **Atenção!** 🚨\n"
                    f"O seu Stop Loss de R${stop_loss:.2f} será ultrapassado na próxima entrada.\n"
                    f"⚠️ Continuar com a operação pode resultar em perdas maiores do que o planejado.\n"
                    f"💔 Perdas acumuladas: R${daily_result:.2f}.\n"
                    f"💸 Balanço atual: R${balance:.2f}.\n"
                    f"❌ Desagendamos todos os sinais para proteger seu capital. Considere revisar suas estratégias.\n"
                    f"💪 Não desanime! Cada operação é uma oportunidade de aprendizado. Descanse e retorne amanhã."
                )
                user_stop_loss = True
                
            elif gale >= 1 and (daily_result - amount * (multiplier ** gale)) < stop_loss * -1:
                message = (
                    f"🚨 **Atenção!** 🚨\n"
                    f"O seu Stop Loss de R${stop_loss:.2f} será ultrapassado se o sinal atingir o Gale {gale}.\n"
                    f"⚠️ Continuar com a operação pode resultar em perdas maiores do que o planejado.\n"
                    f"💔 Estimativa para Gale {gale}: R${amount * (multiplier ** gale):.2f}.\n"
                    f"💸 Balanço atual: R${balance:.2f}.\n"
                    f"❌ Desagendamos todos os sinais para proteger seu capital. Revise suas estratégias.\n"
                    f"💪 Não desanime! Cada operação é uma oportunidade de aprendizado. Descanse e retorne amanhã."
                )
                user_stop_loss = True 

        # Validações de Stop Win
        if stop_win not in (None, 0):
            if daily_result > stop_win:
                message = (
                    f"🎉 **Parabéns!** 🎉\n"
                    f"Seu Stop Win de R${stop_win:.2f} foi atingido!\n"
                    f"💰 Lucro total acumulado: R${daily_result:.2f}.\n"
                    f"💸 Balanço atual: R${balance:.2f}.\n"
                    f"👏 Excelente trabalho! Continue assim e mantenha o foco nas suas estratégias! \n"
                    f"⚠️ Desagendamos todos os sinais para proteger seu lucro. Descanse e retorne amanhã."
                )
                user_stop_win = True

        # Envia a mensagem se houver alguma e os stops forem ativados
        if message and (user_stop_win or user_stop_loss):
            user_stop = stop_sent_flag(user_id, user_stop_win, user_stop_loss, chat_id, message)    
        return user_stop
        




def schedule_signal(user_id, signal_time, symbol, direction, timeframe, source):
    
    try:
        connect_to_database()
        cursor = conn.cursor()
        # Exemplo de leitura das configurações de um usuário
        config, chat_id = get_user_config(user_id)  # Passando a conexão 'conn' também
        if config:
            # Acessa a seção 'iq_bot' e suas configurações
            iq_login = config.get("iq_bot").get("iq_login")
            iq_password = config.get("iq_bot").get("iq_password")
            amount = float(config.get("iq_bot").get("amount"))  # Certifique-se de que seja float
            gale = int(config.get("iq_bot").get("gale"))  # Certifique-se de que seja int
            multiplier = float(config.get("iq_bot").get("multiplier"))  # Certifique-se de que seja float
            balance_type = config.get("iq_bot").get("balance_type")
            payout_min = float(config.get("iq_bot").get("payout_min"))  # Certifique-se de que seja float
            stop_win = float(config.get("iq_bot").get("stop_win", 0))  # Valor de Stop Win
            stop_loss = float(config.get("iq_bot").get("stop_loss", 0))  # Valor de Stop Loss
            list = int(config.get("iq_bot").get("list"))
            live = int(config.get("iq_bot").get("live"))
            auto = int(config.get("iq_bot").get("auto"))

        else:
            return "Configurações do bot não realizadas"
        
        if auto == 1:
            if source == 'list' and list != 1:
                return
            elif source in ('forex', 'otc') and live != 1:
                return

        # Verifica se o sinal já existe
        existing_signal_query = """
        SELECT COUNT(*) FROM scheduled_signals 
        WHERE user_id = %s AND signal_time = %s AND symbol = %s AND timeframe = %s
        """
        cursor.execute(existing_signal_query, (user_id, signal_time, symbol, timeframe))
        existing_signal_count = cursor.fetchone()[0]
        if existing_signal_count > 0:
            return "Sinal já existe"

        signal = user_id, signal_time, symbol, direction, timeframe
        api = IQ_Option(iq_login, iq_password)
        api.connect()
        user_stop = False
        if stop_loss not in (None, 0) or stop_win not in (None, 0):
            user_stop = check_user_stop(user_id, api, stop_win, stop_loss, amount, gale, multiplier, chat_id)
        if user_stop:
            return

            
          
        
        if source != 'list':
            payout = api.get_digital_payout(symbol)

            # Verifica se payout é numérico
            if isinstance(payout, (int, float)):
                if payout < payout_min:
                    return False, f"Payout abaixo do mínimo determinado, {payout}%"   
            else:
                return False, f"Ativo {symbol} fechado no momento"  

        # Verifica e ajusta o formato de signal_time
        if isinstance(signal_time, str) and len(signal_time) == 5:  # Formato HH:MM
            current_date = datetime.now().strftime('%Y-%m-%d')  # Obtém a data atual
            signal_time = f"{current_date} {signal_time}:00"  # Concatena com a data atual e adiciona os segundos
        else:
            # Tenta validar o formato completo
            try:
                signal_time = str(signal_time).strip()  # Converte para string e remove espaços em branco
                if ':' in signal_time and len(signal_time.split(':')) == 2:  # Formato HH:MM
                    signal_time += ":00"  # Adiciona os segundos
                elif len(signal_time) != 19:  # Se não for um formato completo, verifica se está em 'YYYY-MM-DD HH:MM'
                    raise ValueError("Formato inválido")
                # Tenta converter a string em um objeto datetime
                datetime.strptime(signal_time, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                print(f"Formato de signal_time inválido: {signal_time}")
                return False, "Formato de signal_time inválido"

        # Converte para objeto datetime
        signal_time_formated = datetime.strptime(signal_time, '%Y-%m-%d %H:%M:%S')
        schedule_message = f"🚀 Sinal confirmado! {symbol} {direction} {timeframe} marcado para {signal_time}. Prepare-se para a próxima oportunidade! 💥"
        message_id, response_id = send_info_to_user(user_id, chat_id, schedule_message)
        connect_to_database()
        cursor = conn.cursor()
        # Insere na tabela de agendamentos
        query = """
        INSERT INTO scheduled_signals (user_id, signal_time, symbol, direction, timeframe, message_id, response_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s);
        """
        
        cursor.execute(query, (user_id, signal_time_formated, symbol, direction, timeframe, str(message_id), str(response_id)))
        conn.commit()
        
    except Exception as e:
        print(f"Erro ao agendar sinal: {e}")


def load_pending_signals():
    connect_to_database()
    now = datetime.now()
    try:
        query = """
        SELECT id, user_id, signal_time, symbol, direction, timeframe, message_id, response_id, status
        FROM scheduled_signals
        WHERE status = 'pending' AND stop is NULL;
        """
        connect_to_database()
        cursor = conn.cursor()
        cursor.execute(query)  # Executa a consulta sem passar 'now' como argumento
        pending_signals = cursor.fetchall()
        cursor.close()
        # Validação dos sinais pendentes
        valid_signals = []
        for signal in pending_signals:
            # Verifica se todos os campos necessários estão presentes
            if len(signal) == 9:
                valid_signals.append(signal)
        
        return valid_signals

    except Exception as e:
        print(f"Erro ao carregar sinais pendentes: {e}")
        return []


def schedule_pending_signals():
    connect_to_database()
    pending_signals = load_pending_signals()
    now = datetime.now()
    for signal in pending_signals:

        if len(signal) != 9:
            return

        signal_id, user_id, signal_time, symbol, direction, timeframe, message_id, response_id, status = signal
        
        if signal_time < now and status == "pending":
            mark_signal_as_executed(signal_id, "late")
            return


        job_id = f"signal_{signal_id}_{user_id}"
        
        if not scheduler.get_job(job_id):
            trigger = DateTrigger(run_date=signal_time)
            scheduler.add_job(
                execute_schedule_signal,
                trigger=trigger,
                args=[signal_id, user_id, signal_time, symbol, direction, timeframe, message_id, response_id],
                id=job_id
            )
            print(f"Job {job_id} agendado para {signal_time}.")


        


def execute_schedule_signal(signal_id, user_id, signal_time, symbol, direction, timeframe, message_id, response_id):
    trade_executed, profit = trade_with_signal(user_id, message_id, response_id, signal_time, symbol, direction, timeframe)
    mark_signal_as_executed(signal_id, trade_executed, profit)


def mark_signal_as_executed(signal_id, trade_executed, profit=0):
    connect_to_database()
    try:
        query = """
        UPDATE scheduled_signals
        SET status = %s, executed_at = NOW(), profit = %s
        WHERE id = %s;
        """
        connect_to_database()
        cursor = conn.cursor()
        cursor.execute(query, (trade_executed, profit, signal_id,))
        conn.commit()
        cursor.close()
    except Exception as e:
        print(f"Erro ao marcar sinal como executado: {e}")
        conn.rollback()


def schedule_monitor():
    while True:
        connect_to_database()
        listen_to_signals()
        schedule_pending_signals()
        schedule.run_pending()
        time.sleep(0.2)

# Iniciar o bot e a verificação de sinais
if __name__ == "__main__":
    connect_to_database()
    scheduler = BackgroundScheduler()
    scheduler.start()
    schedule_monitor()





