
import random
import telebot
import time
import schedule
import logging
import os
import locale
import asyncio
from pathlib import Path
import pandas as pd
import re
from decimal import Decimal
from db_connection import get_connection
from configparser import ConfigParser
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
import asyncio
from telebot import types
import threading
import json
from datetime import timedelta
import datetime
from telebot import TeleBot, types
import time
import sys
import secrets
import string
from PIL import Image, ImageDraw, ImageFont
import matplotlib.pyplot as plt
import io
from io import BytesIO
import matplotlib.font_manager as fm
import requests
from threading import Thread
from apscheduler.schedulers.background import BackgroundScheduler
import unicodedata




# Desativar logs do APScheduler
logging.getLogger('apscheduler').setLevel(logging.ERROR)
scheduler = BackgroundScheduler()


config = ConfigParser()
config.read('config.ini')
TOKEN = config.get('Telegram', 'TOKEN')
TOKEN_ALERT = config.get('Telegram', 'TOKEN_ALERT')
global chat_free
global CHAT_ID_FREE
admin_chat_id = config.get('Telegram', 'admin_chat_id')
chat_free_str = config.get('Telegram', 'chat_free')
chat_free = int(chat_free_str)
CHAT_ID_M5 = int(config.get('Telegram', 'CHAT_ID_M5'))
CHAT_ID_M5_OTC = int(config.get('Telegram', 'CHAT_ID_M5_OTC'))
CHAT_ID_M1 = int(config.get('Telegram', 'CHAT_ID_M1'))
CHAT_ID_M1_OTC = int(config.get('Telegram', 'CHAT_ID_M1_OTC'))
CHAT_ID_M15 = int(config.get('Telegram', 'CHAT_ID_M15'))
CHAT_ID_M15_OTC = int(config.get('Telegram', 'CHAT_ID_M15_OTC'))
CHAT_ID_FREE = int(config.get('Telegram', 'CHAT_ID_FREE'))
CHAT_ID_M1_CRYPTO = int(config.get('Telegram', 'CHAT_ID_M1_CRYPTO'))
CHAT_ID_M5_CRYPTO = int(config.get('Telegram', 'CHAT_ID_M5_CRYPTO'))
CHAT_ID_M15_CRYPTO = int(config.get('Telegram', 'CHAT_ID_M15_CRYPTO'))

sys.stdout.reconfigure(encoding='utf-8')

if chat_free == 1:
    CHAT_ID_M1 = CHAT_ID_FREE
    CHAT_ID_M5 = CHAT_ID_FREE
    CHAT_ID_M15 = CHAT_ID_FREE
    CHAT_ID_M1_OTC = CHAT_ID_FREE
    CHAT_ID_M5_OTC = CHAT_ID_FREE
    CHAT_ID_M15_OTC = CHAT_ID_FREE



all_chats = [CHAT_ID_M1, CHAT_ID_M1_OTC, CHAT_ID_M1_CRYPTO, CHAT_ID_M5, CHAT_ID_M5_OTC, CHAT_ID_M5_CRYPTO, CHAT_ID_M15, CHAT_ID_M15_OTC, CHAT_ID_M15_CRYPTO]

loop = asyncio.get_event_loop()

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Inicialização do bot do Telegram
bot = telebot.TeleBot(TOKEN)
bot_alert = telebot.TeleBot(TOKEN_ALERT)

conn = get_connection()

def connect_to_database():
    global conn
    try:
        if conn is None or conn.closed:  # Verifica se a conexão está fechada
            while True:
                try:
                    # Substitua get_connection pela sua lógica de obtenção de conexão com o banco
                    conn = get_connection()  # Exemplo: reestabelecendo conexão
                    print("Conexão com o banco de dados restabelecida.")
                    return conn
                except Exception as e:
                    print(f"Erro ao conectar ao banco de dados: {e}. Tentando novamente em 2 segundos...")
                    time.sleep(2)
        return conn
    except Exception as e:
        print(f"Erro ao verificar ou estabelecer conexão: {e}. Tentando reconectar...")
        while True:
            try:
                conn = get_connection()
                print("Conexão com o banco de dados restabelecida.")
                return conn
            except Exception as e:
                print(f"Erro ao conectar ao banco de dados: {e}. Tentando novamente em 2 segundos...")
                time.sleep(2)


def adapt_datetime(dt):
    return dt.isoformat()

def convert_datetime(s):
    return datetime.fromisoformat(s.decode("utf-8"))

def normalize_string(s):
    return unicodedata.normalize('NFC', s)

# Função para escapar caracteres especiais do MarkdownV2
def escape_markdown_v2(text):
    # Lista de caracteres especiais que precisam ser escapados no MarkdownV2
    special_chars = ['.', '-', '_', '*', '[', ']', '(', ')', '~', '>', '#', '+', '=', '|', '{', '}', '!', '?']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text

def send_signal_to_telegram(bot, chat_id, signal):
    # Atribuindo valor padrão para message_complement
    message_complement = ""

    try:
        # Atribuição de variáveis de sinal
        signal_id = signal[0]
        signal_time = datetime.datetime.strptime(signal[4], "%Y-%m-%d %H:%M:%S")
        symbol = signal[1]
        direction = signal[2]
        timeframe = signal[3]
        volatility = signal[5]
        volume = signal[6]
        payout = signal[7]
        status = signal[8]
        source = signal[9]
        indicator = signal[10]

        # Verificando a direção e definindo a mensagem de acordo
        if direction == "CALL":
            message_text = f"🟢 Sinal para {(symbol)} 🟢\n" \
                        f"Horário: {signal_time.strftime('%H:%M')}\n" \
                        f"Expiração da Vela: {(timeframe)}\n" \
                        f"Direção: {(direction)}\n" \
                        f"Análise: {(indicator)}\n"

        elif direction == "PUT":
            message_text = f"🔴 Sinal para {(symbol)} 🔴\n" \
                        f"Horário: {signal_time.strftime('%H:%M')}\n" \
                        f"Expiração da Vela: {(timeframe)}\n" \
                        f"Direção: {(direction)}\n" \
                        f"Análise: {(indicator)}\n"

        # Definindo o complemento da mensagem baseado na origem
        if source == "forex":
            message_complement = f"Payout IQ Option: {(payout)}%\n"

        elif source == "otc":
            message_complement = f"Payout IQ Option: {(payout)}%\n" \
                                f"-----------------------------------\n" \
                                f"⚠️ Atenção: Este é um sinal OTC. Lembre-se que OTC não reflete o mercado real, e os resultados podem ser menos previsíveis e mais arriscados. \n"

        elif source == "crypto":
            message_complement = f"Status Binance: {(status)}\n" \
                                f"-----------------------------------\n" \
                                f"⚠️ Atenção: Este é um sinal de criptomoedas. Deve ser operado em uma corretora de Crypto. \n"

        # Mensagem de resposta com link formatado em Markdown
        message_reply = f"-----------------------------------\n" \
                        f"[Se inscreva na IQ Option](https://affiliate.iqbroker.com/redir/?aff=429732&aff_model=revenue&afftrack=)"

        # Concatenando a mensagem principal com a mensagem complementar, se existir
        message_text_to_send = message_text + message_complement + message_reply

        # Enviando a mensagem através do bot
        message = bot.send_message(chat_id, message_text_to_send, parse_mode="Markdown", disable_web_page_preview=True)

        # Retornando o ID da mensagem e o texto enviado
        return signal_id, message.message_id, message_text_to_send

    except Exception as e:
        # Caso ocorra um erro ao enviar a mensagem
        error = f"Erro ao enviar mensagem no Telegram: {e}"
        send_message(bot_alert, admin_chat_id, error)  # Assumindo que essa função é para enviar alertas
        print(error)
        return None


def send_signals_from_database(bot):
    try:
        cursor = conn.cursor()
    except Exception as e:
        error = f"Telegram: Erro ao criar cursor do banco de dados: {e}"
        send_message(bot_alert, admin_chat_id, error)
        print(error)
        return

    try:
        cursor.execute("""
            SELECT id, symbol, direction, timeframe, time, volatility, volume, payout, status, source, indicator
            FROM trading_signals 
            WHERE sent IS NULL
        """)
        signals = cursor.fetchall()
    except Exception as e:
        error = f"Telegram: Erro ao executar consulta no banco de dados: {e}"
        send_message(bot_alert, admin_chat_id, error)
        print(error)
        return

    if signals:
        list_signals = []  # Lista para armazenar sinais com source 'list'
        
        for signal in signals:
            signal_id = signal[0]
            source = signal[9]
            timeframe = signal[3]
            indicator = [10]

            # Definir o chat_id com base no timeframe do sinal e na origem
            try:
                if timeframe == 'M1' and source == 'otc':
                    chat_id = CHAT_ID_M1_OTC
                elif timeframe == 'M1' and source == 'forex':
                    chat_id = CHAT_ID_M1
                elif timeframe == 'M1' and source == 'crypto':
                    chat_id = CHAT_ID_M1_CRYPTO
                elif timeframe == 'M5' and source == 'otc':
                    chat_id = CHAT_ID_M5_OTC
                elif timeframe == 'M5' and source == 'forex':
                    chat_id = CHAT_ID_M5
                elif timeframe == 'M5' and source == 'crypto':
                    chat_id = CHAT_ID_M5_CRYPTO
                elif timeframe == 'M15' and source == 'otc':
                    chat_id = CHAT_ID_M15_OTC
                elif timeframe == 'M15' and source == 'forex':
                    chat_id = CHAT_ID_M15
                elif timeframe == 'M15' and source == 'crypto':
                    chat_id = CHAT_ID_M15_CRYPTO
                elif source == 'list':
                    list_signals.append(signal)  # Adiciona à lista de sinais com source 'list'
                    continue  # Pula para o próximo sinal
                else:
                    chat_id = None  # Caso não se encaixe em nenhuma das opções
            except Exception as e:
                error = f"Telegram: Erro ao determinar chat_id: {e}"
                send_message(bot_alert, admin_chat_id, error)
                print(error)
                continue  # Pula para o próximo sinal

            if chat_id:
                try:
                    result = send_signal_to_telegram(bot, chat_id, signal)
                except Exception as e:
                    error = f"Telegram: Erro ao enviar sinal para o Telegram: {e}"
                    send_message(bot_alert, admin_chat_id, error)
                    print(error)
                    continue  # Pula para o próximo sinal

                if result:
                    signal_id, message_id, message_text = result
                    current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    try:
                        cursor.execute("""
                            UPDATE trading_signals 
                            SET message_id = %s, message_text = %s, sent = %s, chat_id = %s 
                            WHERE id = %s
                        """, (message_id, message_text, current_time, chat_id, signal_id))
                        conn.commit()
                    except Exception as e:
                        error = f"Telegram: Erro ao atualizar sinal no banco de dados: {e}"
                        send_message(bot_alert, admin_chat_id, error)
                        print(error)
                        conn.rollback()  # Reverte alterações em caso de erro
        
        # Enviar todos os sinais da lista para o Telegram
        if list_signals:
            try:
                # Envia todos os sinais com source 'list' e captura o message_id
                message_id = send_list_to_telegram(bot, CHAT_ID_FREE, list_signals)  
                if message_id:  # Verifica se a mensagem foi enviada com sucesso
                    current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    for line_number, signal in enumerate(list_signals, start=4):  # Start de 1 para linhas
                        signal_id = signal[0]
                        # Atualizar os sinais enviados para a lista com message_id, linha e chat_id
                        cursor.execute("""
                            UPDATE trading_signals 
                            SET sent = %s, message_id = %s, line_number = %s, chat_id = %s 
                            WHERE id = %s
                        """, (current_time, message_id, line_number, CHAT_ID_FREE, signal_id))  # Usando CHAT_ID_FREE
                    conn.commit()
            except Exception as e:
                error = f"Telegram: Erro ao enviar lista de sinais para o Telegram: {e}"
                send_message(bot_alert, admin_chat_id, error)
                print(error)
                conn.rollback()  # Reverte alterações em caso de erro



def send_list_to_telegram(bot, chat_id, signals):
    cursor = conn.cursor()
    
    # Formatar os sinais para envio
    formatted_signals = "\n".join([
        f"{datetime.datetime.strptime(signal[4], '%Y-%m-%d %H:%M:%S').strftime('%H:%M')} {signal[1]} {signal[2]}" 
        for signal in sorted(signals, key=lambda x: datetime.datetime.strptime(x[4], '%Y-%m-%d %H:%M:%S'))
    ])

    
    # Definir next_day como o dia do primeiro sinal da lista, se existir
    if signals:
        first_signal_date = datetime.datetime.strptime(signals[0][4], '%Y-%m-%d %H:%M:%S')
        next_day = first_signal_date.strftime('%d/%m/%Y')
    else:
        # Definir uma data padrão, caso não haja sinais na lista
        next_day = (datetime.datetime.now() + timedelta(days=1)).strftime('%d/%m/%Y')
    
    message_text = (
        f"✨ **Lista Free para {next_day}** ✨\n\n"
        f"📊 **Timeframe:** M5\n"
        f"-----------------------------------\n"
        f"{formatted_signals}\n"
        f"-----------------------------------\n"
        f"⚠️ **Observação:** Lembre-se de operar com cautela e fazer sua própria análise antes de executar qualquer operação.\n"
        f"🔔 **Fique atento às nossas atualizações!**\n\n"
        f"🌟 **Teste o VIP por 2 dias!**\n"
        f"🔑 **Acesse e experimente agora!**\n"
        f"[👉 Clique aqui para testar](https://t.me/goldenwintradebot)"
    )

    # Enviar a mensagem e obter o ID
    try:
        message = bot.send_message(chat_id, message_text, parse_mode='Markdown')
        # Atualizar message_id e message_text para todos os sinais
        for signal in signals:
            signal_id = signal[0]  # Assumindo que o ID do sinal está na primeira posição
            cursor.execute("""
                UPDATE trading_signals 
                SET message_id = %s, message_text = %s 
                WHERE id = %s
            """, (message.id, message_text, signal_id))
        
        conn.commit()
        return message.id  # Retorna o ID da mensagem enviada
    except Exception as e:
        error = f"Erro ao enviar lista de sinais para o Telegram: {e}"
        print(error)
        return None  # Retorna None em caso de erro


def update_messages_with_results(bot):
    try:
        cursor = conn.cursor()
    except Exception as e:
        error = f"Telegram: Erro ao obter cursor do banco de dados: {e}"
        send_message(bot_alert, admin_chat_id, error)
        print(error)
        return

    try:
        # Filtrar os sinais do banco de dados que têm um resultado preenchido e uma mensagem enviada
        cursor.execute("""
            SELECT * FROM trading_signals 
            WHERE result IS NOT NULL AND message_id IS NOT NULL AND edited IS NULL
        """)
        signals_with_results = cursor.fetchall()
    except Exception as e:
        error = f"Telegram: Erro ao executar SELECT no banco de dados: {e}"
        send_message(bot_alert, admin_chat_id, error)
        print(error)
        return

    for signal in signals_with_results:
        try:
            signal_id = signal[0]
            result = signal[5]
            source = signal[22]  # Obter a fonte
            line_number = signal[28]  # Obter a linha correspondente
            signal_time = datetime.datetime.strptime(signal[4], "%Y-%m-%d %H:%M:%S")
            symbol = signal[1]
            direction = signal[2]
            response_id = signal[20]
            timeframe = signal[3]
            chat_id = signal[23]  # Ajustar o índice caso o chat_id esteja em outra posição
            message_id = signal[6]  # Índice de message_id
            original_message = signal[29]
        except Exception as e:
            error = f"Telegram: Erro ao processar dados do sinal: {e}"
            send_message(bot_alert, admin_chat_id, error)
            print(error)
            continue

        # Verifica se a fonte é "list"
        if source == 'list':
            try:
       
                # Separar a mensagem em linhas
                message_lines = original_message.split('\n')
                if "WIN" in result:
                    result = result.replace("WIN", "")
                if "LOSS" in result:
                    result = result.replace("LOSS", "")    
        
                # Verificar se a linha correspondente existe e adicionar o resultado
                if 0 <= line_number < len(message_lines):
                    message_lines[line_number] += f" {result}"
                else:
                    error = f"Telegram: Linha {line_number} fora do intervalo."
                    send_message(bot_alert, admin_chat_id, error)
                    print(error)
                    continue
                
                # Criar o novo texto da mensagem
                new_message_text = '\n'.join(message_lines)
        
                # Excluir a mensagem anterior
                bot.delete_message(chat_id=chat_id, message_id=message_id)
                
                # Enviar uma nova mensagem e obter o novo message_id
                new_message = bot.send_message(chat_id=chat_id, text=new_message_text, parse_mode='Markdown')
                new_message_id = new_message.message_id
        
                # Atualizar o message_id e message_text no banco de dados
                current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute("""UPDATE trading_signals SET edited = %s WHERE id = %s""",
                               (current_time, signal_id))
                cursor.execute("""UPDATE trading_signals SET message_id = %s, message_text = %s WHERE message_id = %s""",
                               (new_message_id, new_message_text, message_id))
                conn.commit()
        
            except Exception as e:
                error = f"Telegram: Erro ao enviar nova mensagem no Telegram: {e}"
                send_message(bot_alert, admin_chat_id, error)
                print(error)
                current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute("UPDATE trading_signals SET edited = %s WHERE id = %s", (current_time, signal_id))
                conn.commit()
                continue

        else:
            if original_message:
                try:
                    # Verificar se original_message é uma string e usá-la diretamente
                    current_message_text = original_message if isinstance(original_message, str) else original_message.text

                    # Remover a última linha da mensagem
                    lines = current_message_text.split("\n")
                    if lines:
                        lines = lines[:-1]  # Remover a última linha

                    # Adicionar o resultado no final
                    new_message_text = "\n".join(lines) + f"\nResultado: {result}"

                    # Editar a mensagem no chat do Telegram
                    bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=new_message_text, parse_mode='HTML')
                except Exception as e:
                    error = f"Telegram: Erro ao editar mensagem no Telegram: {e}"
                    send_message(bot_alert, admin_chat_id, error)
                    print(error)
                    current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    cursor.execute("UPDATE trading_signals SET edited = %s WHERE id = %s", (current_time, signal_id))
                    conn.commit()
                    continue


        try:
            # Atualizar a coluna edited
            current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute("UPDATE trading_signals SET edited = %s WHERE id = %s", (current_time, signal_id))
            conn.commit()
        except Exception as e:
            error = f"Telegram: Erro ao atualizar sinal no banco de dados: {e}"
            send_message(bot_alert, admin_chat_id, error)
            print(error)

        # Esperar 1 segundo antes do próximo update
        time.sleep(1)


def fetch_prices_from_candle_history(symbol, timeframe, signal_time):
    try:
        cursor = conn.cursor()
    except Exception as e:
        error = f"Telegram: Erro ao obter cursor do banco de dados: {e}"
        send_message(bot_alert, admin_chat_id, error)
        print(error)
        return None, None

    try:
        # Converter signal_time para string no formato correto
        signal_time_str = signal_time.strftime('%Y-%m-%d %H:%M:%S')
        query = """
            SELECT open, close FROM candle_history 
            WHERE symbol = %s AND timeframe = %s AND time = %s
        """
        cursor.execute(query, (symbol, timeframe, signal_time_str))
    except Exception as e:
        error = f"Telegram: Erro ao executar query no banco de dados: {e}"
        send_message(bot_alert, admin_chat_id, error)
        print(error)
        return None, None

    try:
        row = cursor.fetchone()
        if row:
            return row[0], row[1]
        else:
            return None, None
    except Exception as e:
        error = f"Telegram: Erro ao buscar resultados no banco de dados: {e}"
        send_message(bot_alert, admin_chat_id, error)
        print(error)
        return None, None


def calculate_next_candle_time(signal_time, timeframe):
    try:
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
    except Exception as e:
        error = f"Erro ao calcular proximo candle: {e}"
        send_message(bot_alert, admin_chat_id, error)
        print(error)

def update_prices_in_database():
    try:
        cursor = conn.cursor()

        # Filtrar os sinais do banco de dados que ainda não têm preços de abertura e fechamento
        cursor.execute("SELECT * FROM trading_signals WHERE open IS NULL OR close IS NULL OR open_g1 IS NULL OR close_g1 IS NULL OR open_g2 IS NULL OR close_g2 IS NULL order by id asc")
        signals_to_update = cursor.fetchall()
        for signal in signals_to_update:
            try:
                
                signal_id = signal[0]
                symbol = signal[1]
                timeframe = signal[3]  # Pegando o timeframe da tabela trading_signals
                signal_time = datetime.datetime.strptime(signal[4], "%Y-%m-%d %H:%M:%S")
                
                # Vela do sinal original
                open_price, close_price = fetch_prices_from_candle_history(symbol, timeframe, signal_time)

                # Inicializando variáveis das velas subsequentes
                open_g1, close_g1, open_g2, close_g2 = None, None, None, None

                if open_price is not None and close_price is not None:
                    try:
                        # Vela 1 (G1)
                        next_time_g1 = calculate_next_candle_time(signal_time, timeframe)
                        open_g1, close_g1 = fetch_prices_from_candle_history(symbol, timeframe, next_time_g1)

                        if open_g1 is not None and close_g1 is not None:
                            try:
                                # Vela 2 (G2)
                                next_time_g2 = calculate_next_candle_time(next_time_g1, timeframe)
                                open_g2, close_g2 = fetch_prices_from_candle_history(symbol, timeframe, next_time_g2)

                            except Exception as e:
                                error = f"Telegram: Erro ao buscar preços da vela G2: {e}"
                                send_message(bot_alert, admin_chat_id, error)
                                print(error)

                    except Exception as e:
                        error = f"Telegram: Erro ao buscar preços da vela G1: {e}"
                        send_message(bot_alert, admin_chat_id, error)
                        print(error)

                # Atualizar a tabela trading_signals com todos os preços obtidos
                try:
                    connect_to_database()
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE trading_signals
                        SET open = %s, close = %s, open_g1 = %s, close_g1 = %s, open_g2 = %s, close_g2 = %s
                        WHERE id = %s
                    """, (open_price, close_price, open_g1, close_g1, open_g2, close_g2, signal_id))
                    conn.commit()

                except Exception as e:
                    error = f"Telegram: Erro ao atualizar o banco de dados: {e}"
                    send_message(bot_alert, admin_chat_id, error)
                    print(error)

            except Exception as e:
                error = f"Telegram: Erro ao processar o sinal ID {signal[0]}: {e}"
                send_message(bot_alert, admin_chat_id, error)
                print(error)

    except Exception as e:
        error = f"Telegram: Erro ao buscar sinais no banco de dados: {e}"
        send_message(bot_alert, admin_chat_id, error)
        print(error)

def check_results():
    try:
        cursor = conn.cursor()

        # Filtrar os sinais do banco de dados que ainda não têm um resultado preenchido
        try:
            cursor.execute("SELECT * FROM trading_signals WHERE result IS NULL AND open IS NOT NULL AND close IS NOT NULL")
            signals_to_check = cursor.fetchall()
        except Exception as e:
            error = f"Telegram: Erro ao buscar sinais do banco de dados: {e}"
            send_message(bot_alert, admin_chat_id, error)
            print(error)
            return  # Interrompe a função se não conseguir buscar os sinais

        for signal in signals_to_check:
            try:
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
                                    # Se as informações sobre G2 não estiverem disponíveis, manter o resultado como "LOSS"
                                    continue
                        else:
                            # Se as informações sobre G1 não estiverem disponíveis, manter o resultado como "LOSS"
                            continue

                    # Atualizar o registro no banco com o resultado
                    try:
                        cursor.execute("UPDATE trading_signals SET result = %s WHERE id = %s", (result, signal_id))
                        conn.commit()
                        print(f"Resultado atualizado para sinal ID: {signal_id} - {result}")
                    except Exception as e:
                        error = f"Telegram: Erro ao atualizar resultado para sinal ID {signal_id}: {e}"
                        send_message(bot_alert, admin_chat_id, error)
                        print(error)

                else:
                    print(f"Não foi possível determinar o resultado para o sinal ID: {signal_id}. Preço de fechamento não disponível.")

            except Exception as e:
                error = f"Telegram: Erro ao processar sinal ID {signal[0]}: {e}"
                send_message(bot_alert, admin_chat_id, error)
                print(error)

    except Exception as e:
        error = f"Telegram: Erro ao verificar resultados: {e}"
        send_message(bot_alert, admin_chat_id, error)
        print(error)

def remove_random_loss():
    try:
        percent = 70
        # Conectar ao banco de dados
        conn = connect_to_database()
        cursor = conn.cursor()

        # Obter a data atual no formato yyyy-mm-dd
        today = datetime.datetime.now().strftime('%Y-%m-%d')

        # Query para buscar os sinais com resultado 'LOSS ❌' e list is null para a data atual
        select_query = """
        SELECT id
        FROM trading_signals
        WHERE "result" = 'LOSS ❌' AND list IS NULL AND DATE("time") = %s
        ORDER BY id DESC;
        """
        cursor.execute(select_query, (today,))
        results = cursor.fetchall()

        # Verificar se há registros encontrados
        if not results:
            print("Nenhum sinal encontrado para a data atual.")
            return

        # Extrair os IDs dos resultados
        ids = [row[0] for row in results]

        # Calcular 60% dos resultados, arredondando para baixo
        count_to_update = max(1, int(len(ids) * (percent/100)))  # Atualiza pelo menos 1, se aplicável

        # Selecionar 60% dos IDs de forma aleatória
        random_ids = random.sample(ids, count_to_update)

        # Query de update para marcar os IDs selecionados como is_deleted = 1
        update_query = """
        UPDATE trading_signals
        SET is_deleted = 1
        WHERE id = ANY(%s);
        """
        cursor.execute(update_query, (random_ids,))
        conn.commit()

        print(f"{len(random_ids)} sinais foram atualizados com sucesso para is_deleted = 1.")

    except Exception as e:
        print(f"Erro ao realizar a operação: {e}")


def send_daily_report(bot, type, period):
    try:
        cursor = conn.cursor()
        locale.setlocale(locale.LC_TIME, 'pt_BR.UTF-8')

        # Definir chat_ids no início para evitar o erro
        chat_ids = {'M1': CHAT_ID_M1, 'M5': CHAT_ID_M5, 'M15': CHAT_ID_M15}
        chat_ids_OTC = {'M1': CHAT_ID_M1_OTC, 'M5': CHAT_ID_M5_OTC, 'M15': CHAT_ID_M15_OTC}
        chat_ids_crypto = {'M1': CHAT_ID_M1_CRYPTO, 'M5': CHAT_ID_M5_CRYPTO, 'M15': CHAT_ID_M15_CRYPTO}

        # Determinar o período de análise
        if type == 'thismonth':
            cursor.execute("SELECT * FROM trading_signals WHERE time::timestamp BETWEEN date_trunc('month', current_date) AND date_trunc('month', current_date) + interval '1 month' - interval '1 second' AND result IS NOT NULL")
            period_text = datetime.datetime.now().strftime("%b/%Y")
        elif type == 'today':
            
            today = datetime.datetime.now().date()
            data_inicio = datetime.datetime.combine(today, datetime.time.min)
            data_fim = datetime.datetime.combine(today, datetime.time.max) 
            cursor.execute("""
                SELECT * FROM trading_signals 
                WHERE time::timestamp >= %s 
                AND time::timestamp <= %s 
                AND result IS NOT NULL
            """, (data_inicio, data_fim))

            period_text = datetime.datetime.now().strftime("%d/%m/%Y")

        elif type == 'last12h':
            now = datetime.datetime.now()
            start_time = now - timedelta(hours=12)
            cursor.execute("SELECT * FROM trading_signals WHERE time::timestamp BETWEEN %s AND %s AND result IS NOT NULL", (start_time, now))
            period_text = f"Últimas 12 horas - {start_time.strftime('%d/%m/%Y - %H:%M')} às {now.strftime('%d/%m/%Y - %H:%M')}"
        elif type == 'custom':
            start_time, end_time = period
            cursor.execute("SELECT * FROM trading_signals WHERE time::timestamp BETWEEN %s AND %s AND result IS NOT NULL", (start_time, end_time))
            period_text = f"{start_time.strftime('%d/%m/%Y - %H:%M')} às {end_time.strftime('%H:%M')}"

        signals = cursor.fetchall()

        # Inicializar contadores por timeframe e categoria
        stats = {
            'M1': {'win_forex': 0, 'loss_forex': 0, 'doji_forex': 0, 'win_otc': 0, 'loss_otc': 0, 'doji_otc': 0, 'win_crypto': 0, 'loss_crypto': 0, 'doji_crypto': 0, 'win_free': 0, 'loss_free': 0, 'doji_free': 0},
            'M5': {'win_forex': 0, 'loss_forex': 0, 'doji_forex': 0, 'win_otc': 0, 'loss_otc': 0, 'doji_otc': 0, 'win_crypto': 0, 'loss_crypto': 0, 'doji_crypto': 0, 'win_free': 0, 'loss_free': 0, 'doji_free': 0},
            'M15': {'win_forex': 0, 'loss_forex': 0, 'doji_forex': 0, 'win_otc': 0, 'loss_otc': 0, 'doji_otc': 0, 'win_crypto': 0, 'loss_crypto': 0, 'doji_crypto': 0, 'win_free': 0, 'loss_free': 0, 'doji_free': 0}
        }

        # Função para atualizar os contadores por timeframe e categoria
        def update_stats(result, timeframe, source):
            if source not in ['forex', 'otc', 'crypto']:
                return

            if result.startswith("WIN") or "🐔" in result:
                stats[timeframe][f'win_{source}'] += 1
                stats[timeframe][f'win_free'] += 1
            elif "LOSS" in result:
                stats[timeframe][f'loss_{source}'] += 1
                stats[timeframe][f'loss_free'] += 1
            elif "DOJI" in result:
                stats[timeframe][f'doji_{source}'] += 1
                stats[timeframe][f'doji_free'] += 1

            # Total geral de sinais para cada timeframe e categoria
            stats[timeframe][f'total_{source}'] = stats[timeframe][f'win_{source}'] + stats[timeframe][f'loss_{source}'] + stats[timeframe][f'doji_{source}']
            stats[timeframe][f'total_free'] = stats[timeframe][f'win_free'] + stats[timeframe][f'loss_free'] + stats[timeframe][f'doji_free']

        def calculate_percentages(stats, timeframe, category):
            total_signals = stats[timeframe][f'total_{category}']
            if total_signals == 0:
                return 0, 0  # Evitar divisão por zero
            win_percentage = (stats[timeframe][f'win_{category}'] / total_signals) * 100
            loss_percentage = (stats[timeframe][f'loss_{category}'] / total_signals) * 100
            return win_percentage, loss_percentage

        # Processar sinais e atualizar as estatísticas por timeframe
        for signal in signals:
            signal_time = datetime.datetime.strptime(signal[4], "%Y-%m-%d %H:%M:%S")
            symbol = signal[1]
            direction = signal[2]
            result = signal[5]
            timeframe = signal[3]
            source = signal[22]

            result_emojis = re.sub(r'[a-zA-Z\s]', '', result)

            if timeframe in ['M1', 'M5', 'M15']:
                update_stats(result, timeframe, source)

        # Função para gerar imagens de relatórios de cada timeframe e categoria
        def generate_stats_image(stats, timeframe, category, period_text, background_image_path=None):
            win = stats[timeframe][f'win_{category}']
            loss = stats[timeframe][f'loss_{category}']
            total = stats[timeframe][f'total_{category}']
            win_percentage, loss_percentage = calculate_percentages(stats, timeframe, category)
            
            font_path = "static/fonts/ENGINE.ttf"
            prop = fm.FontProperties(fname=font_path)
            
            fig, ax = plt.subplots(figsize=(8, 6))
            fig.patch.set_facecolor('black')
            ax.set_facecolor('black')
            
            if background_image_path:
                img = Image.open(background_image_path)
                ax.imshow(img, extent=[0, 1, 0, 1], aspect='auto', alpha=0.5)
            
            ax.axis('off')
            ax.text(0.5, 0.9, f"Relatório {category} {timeframe}", color='white', fontsize=40, ha='center', va='center', fontproperties=prop)
            ax.text(0.5, 0.6, f"WIN {win_percentage:.1f}% x LOSS {loss_percentage:.1f}%", color='white', fontsize=35, ha='center', va='center', fontproperties=prop)
            ax.text(0.5, 0.4, f"Total: {total} Sinais", color='white', fontsize=35, ha='center', va='center', fontproperties=prop)
            ax.text(0.5, 0.1, period_text, color='white', fontsize=25, ha='center', va='center', fontproperties=prop)
            
            buf = BytesIO()
            plt.savefig(buf, format='png', bbox_inches='tight', pad_inches=0)
            buf.seek(0)
            plt.close()
            return buf


        def generate_combined_stats_image(stats, period_text, background_image_path=None):
            font_path = "static/fonts/ENGINE.ttf"
            prop = fm.FontProperties(fname=font_path)
            
            fig, ax = plt.subplots(figsize=(8, 6))
            fig.patch.set_facecolor('black')
            ax.set_facecolor('black')
            ax.axis('off')

            if background_image_path:
                img = Image.open(background_image_path)
                ax.imshow(img, extent=[0, 1, 0, 1], aspect='auto', alpha=0.5)

            # Título principal
            ax.text(0.5, 0.9, "Relatório de Sinais - Grupo VIP", color='white', fontsize=40, ha='center', va='center', fontproperties=prop)

            y_position = 0.7
            total_signals = 0  # Inicializa contador total de sinais

            for timeframe in ['M1', 'M5', 'M15']:
                win = stats[timeframe]['win_free']
                loss = stats[timeframe]['loss_free']
                total = win + loss
                total_signals += total  # Soma ao total geral

                if total != 0:
                    win_percentage = (win / total) * 100
                    loss_percentage = (loss / total) * 100
                    ax.text(0.5, y_position, f"{timeframe}: {win_percentage:.1f}% Win / {loss_percentage:.1f}% Loss", 
                            color='white', fontsize=35, ha='center', va='center', fontproperties=prop)
                else:
                    ax.text(0.5, y_position, f"{timeframe}: Sem sinais registrados", 
                            color='white', fontsize=35, ha='center', va='center', fontproperties=prop)

                y_position -= 0.15  # Ajusta a posição para a próxima linha

            # Exibe o total geral de sinais
            ax.text(0.5, y_position, f"Total: {total_signals} sinais", 
                    color='white', fontsize=30, ha='center', va='center', fontproperties=prop)

            # Período
            ax.text(0.5, y_position - 0.15, period_text, color='white', fontsize=20, ha='center', va='center', fontproperties=prop)

            # Salvar a imagem
            current_date = datetime.datetime.now()
            directory = 'static/images/History/free'
            os.makedirs(directory, exist_ok=True)
            file_path = f'{directory}/free_{current_date.strftime("%Y%m%d_%H%M%S")}.png'

            buf = BytesIO()
            plt.savefig(buf, format='png', bbox_inches='tight', pad_inches=0)
            plt.savefig(file_path)  # Salvar imagem
            buf.seek(0)
            plt.close()
            return buf


        # Gera e envia imagem combinada para o chat livre
        image_free = generate_combined_stats_image(stats, period_text, 'static/images/Telegram/free.jpg')
        free_message = bot.send_photo(CHAT_ID_FREE, photo=image_free)

        # Definir chats por timeframe e enviar os relatórios
        for timeframe in ['M1', 'M5', 'M15']:
            # Verifica se há algum sinal de win ou loss para qualquer categoria (forex, otc, crypto)
            if any([stats[timeframe][f'win_{cat}'] or stats[timeframe][f'loss_{cat}'] for cat in ['forex', 'otc', 'crypto']]):
                for category, chat_dict in [('forex', chat_ids), ('otc', chat_ids_OTC), ('crypto', chat_ids_crypto)]:
                    # Verifica se há sinais de win ou loss na categoria e timeframe
                    if stats[timeframe][f'win_{category}'] or stats[timeframe][f'loss_{category}']:
                        # Define o caminho da imagem de fundo de acordo com a categoria
                        background_image_path = {
                            'forex': 'static/images/Telegram/forex.jpg',
                            'otc': 'static/images/Telegram/otc.jpg',
                            'crypto': 'static/images/Telegram/crypto.jpg'
                        }[category]

                        image = generate_stats_image(stats, timeframe, category, period_text, background_image_path)
                        message = bot.send_photo(chat_dict[timeframe], photo=image)
        cursor.close()

    except Exception as e:
        error = f"Erro ao enviar o relatorio diario: {e}"
        send_message(bot_alert, admin_chat_id, error)
        print(error)

def delete_signals(bot):
    try:
        # Conectar ao banco de dados
        cursor = conn.cursor()
        
        # Executar a consulta
        try:
            cursor.execute("SELECT id, symbol, timeframe, message_id, chat_id FROM trading_signals WHERE is_deleted = 1")
            # Recuperar todos os resultados
            signals = cursor.fetchall()
        except Exception as e:
            error = f"telegram: Erro ao executar a consulta de sinais: {e}"
            send_message(bot_alert, admin_chat_id, error)
            print(error)
            return  # Interrompe a função se houver erro na consulta

        # Processar cada linha
        for signal in signals:
            id, symbol, timeframe, message_id, chat_id = signal

            # Excluir mensagens com base no timeframe
            try:
                bot.delete_message(chat_id, message_id)
                print("Mensagem do sinal:", signal, " excluída com sucesso")
            except Exception as e:
                error = f"telegram: Mensagem não encontrada no chat do Telegram para o sinal {signal}: {e}"
                send_message(bot_alert, admin_chat_id, error)
                print(error)

            try:
                cursor.execute("DELETE FROM trading_signals WHERE id = %s", (id,))
                conn.commit()
                print('Sinal', signal, "apagado com sucesso!")
            except Exception as e:
                error = f"telegram: Erro ao deletar o sinal {signal}: {e}"
                send_message(bot_alert, admin_chat_id, error)
                print(error)

    except Exception as e:
        error = f"telegram: Erro ao deletar sinal: {e}"
        send_message(bot_alert, admin_chat_id, error)
        print(error)


            
def load_events():
    try:
        with open('json/events.json', 'r', encoding='utf-8') as f:  # Use UTF-8
            return json.load(f)
    except FileNotFoundError as e:
        error = f"Telegram: Erro ao carregar eventos: {e}"
        send_message(bot_alert, admin_chat_id, error)
        print(error)
        return []  # Retorna uma lista vazia se o arquivo não existir
    except json.JSONDecodeError as e:
        error = f"Telegram: Erro ao decodificar JSON em events.json: {e}"
        send_message(bot_alert, admin_chat_id, error)
        print(error)
        return []  # Retorna uma lista vazia em caso de erro de decodificação
    except Exception as e:
        error = f"Telegram: Erro inesperado ao carregar eventos: {e}"
        send_message(bot_alert, admin_chat_id, error)
        print(error)
        return []  # Retorna uma lista vazia em caso de erro inesperado


def load_message_history():
    try:
        with open('json/message_history.json', 'r') as file:
            return json.load(file)
    except FileNotFoundError as e:
        error = "Telegram: Arquivo message_history.json não encontrado, retornando lista vazia."
        send_message(bot_alert, admin_chat_id, error)
        print(error)
        return []  # Retorna uma lista vazia se o arquivo não existir
    except json.JSONDecodeError as e:
        error = f"Telegram: Erro ao decodificar JSON em message_history.json: {e}"
        send_message(bot_alert, admin_chat_id, error)
        print(error)
        return []  # Retorna uma lista vazia em caso de erro de decodificação
    except Exception as e:
        error = f"Telegram: Erro inesperado ao carregar o histórico de mensagens: {e}"
        send_message(bot_alert, admin_chat_id, error)
        print(error)
        return []  # Retorna uma lista vazia em caso de erro inesperado

def save_message_history(message_history):
    try:
        with open('json/message_history.json', 'w') as file:
            json.dump(message_history, file)
    except Exception as e:
        error = f"Telegram: Erro ao salvar o histórico de mensagens: {e}"
        send_message(bot_alert, admin_chat_id, error)
        print(error)

def send_telegram_message(chat_id, message):
    try:
        bot.send_message(chat_id, message, parse_mode='Markdown')
    except Exception as e:
        error = f"Telegram: Erro ao enviar mensagem para {chat_id}: {e}"
        send_message(bot_alert, admin_chat_id, error)
        print(error)


        
def send_alert_message():
    # Mensagem de alerta
    message = (
        "🚨 **Atenção, Traders!** 🚨\n\n"
        "Hoje temos um dia agitado no calendário econômico, com muitos eventos programados. 📅⚠️\n\n"
        "Por favor, fiquem atentos e cuidem de suas operações! Uma alta volatilidade pode impactar os resultados. 💹💼\n\n"
        "Operem com cautela! 🔍💡"
    )
    
    # Combine os chat_ids manualmente
    chat_ids = [CHAT_ID_M1, CHAT_ID_M5, CHAT_ID_M15, CHAT_ID_FREE]
    
    # Carregar eventos
    try:
        events = load_events()
    except Exception as e:
        error = f"Telegram: Erro ao carregar eventos: {e}"
        send_message(bot_alert, admin_chat_id, error)
        print(error)
        return  # Encerra a função se houver erro ao carregar eventos
    
    impactful_events = [event for event in events if event['impact'] >= 2]

    # Verificar a quantidade de eventos
    if len(impactful_events) > 25:
        for chat_id in chat_ids:
            try:
                bot.send_message(chat_id, message)
                print(f'Mensagem enviada para o chat_id: {chat_id}')
            except Exception as e:
                error = f"Telegram: Erro ao enviar mensagem para o chat_id {chat_id}: {e}"
                send_message(bot_alert, admin_chat_id, error)
                print(error)

def load_sent_events():
    try:
        with open('json/sent_events.json', 'r') as file:
            # Certifique-se de que os elementos lidos do JSON são convertidos para tuplas
            return set(tuple(event) for event in json.load(file))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()  # Retorna um conjunto vazio se o arquivo não existir ou estiver vazio


def save_sent_events(sent_events):
    with open('json/sent_events.json', 'w') as file:
        json.dump([list(event) for event in sent_events], file)



def check_and_notify_events():
    try:
        events = load_events()
    except Exception as e:
        error = f"Telegram: Erro ao carregar eventos para notificação: {e}"
        send_message(bot_alert, admin_chat_id, error)
        print(error)
        return  # Encerra a função se houver erro ao carregar eventos
    
    now = datetime.datetime.now().replace(microsecond=0)
    twenty_minutes_from_now = (now + timedelta(minutes=20)).replace(second=0, microsecond=0)
    
    # Carregar o histórico de mensagens
    try:
        message_history = load_message_history()
    except Exception as e:
        error = f"Telegram: Erro ao carregar o histórico de mensagens: {e}"
        send_message(bot_alert, admin_chat_id, error)
        print(error)
        message_history = []  # Inicializa como lista vazia em caso de erro

    # Carregar o histórico de eventos enviados
    sent_events = load_sent_events()  # Função que carrega eventos enviados do JSON

    for event in events:
        try:
            event_datetime = datetime.datetime.strptime(event['datetime'], '%Y-%m-%d %H:%M:%S').replace(second=0, microsecond=0)
        except ValueError as e:
            error = f"Telegram: Erro ao converter data/hora: {e}"
            send_message(bot_alert, admin_chat_id, error)
            print(error)
            continue
        
        # Verifique se o evento está dentro do intervalo
        if event['impact'] > 1 and now <= event_datetime <= twenty_minutes_from_now:
           
            if event['impact'] > 2:
                CHAT_IDS = [CHAT_ID_M1, CHAT_ID_M5, CHAT_ID_M15, CHAT_ID_FREE]
            else:    
                CHAT_IDS = [CHAT_ID_M1, CHAT_ID_M5, CHAT_ID_M15]

            impact = ""  # Valor padrão para evitar erros caso o impacto não seja 1, 2 ou 3

            if event['impact'] == 1:
                impact = "🐮"
            elif event['impact'] == 2:    
                impact = "🐮🐮"
            elif event['impact'] == 3:    
                impact = "🐮🐮🐮"

            message = (
                f"📺**Notícia Iminente!** 📺\n"
                f"Título: {normalize_string(event['title'])}\n"
                f"Hora: {event_datetime.strftime('%H:%M')}\n"
                f"País: {event['country']}\n"
                f"Moeda Afetada: {event['currency']}\n"
                f"Impacto: {impact}\n"
                f"[Link da Notícia]({event['link']})\n\n"
                f"⚠️ **Atenção:** Esta notícia pode afetar significativamente o mercado da moeda {event['currency']}.\n"
                f"⚠️ **Recomendação:** Opere com cautela e esteja atento às possíveis flutuações.\n"
                f"🚀 Fique atento às atualizações!"
            )

            # Criar uma chave única para o evento (impacto, país, hora)
            unique_key = (event['impact'], event['country'], event_datetime.strftime('%H:%M'))

            # Verificar se a combinação já foi enviada
            if unique_key not in sent_events:
                for chat_id in CHAT_IDS:
                    try:
                        send_telegram_message(chat_id, message)
                    except Exception as e:
                        error = f"Telegram: Erro ao enviar mensagem para {chat_id}: {e}"
                        send_message(bot_alert, admin_chat_id, error)
                        print(error)

                # Adicionar a chave única ao conjunto de eventos enviados
                sent_events.add(unique_key)

                # Adicionar a mensagem ao histórico e salvar
                message_history.append(message)
                try:
                    save_message_history(message_history)  # Salva histórico de mensagens
                    save_sent_events(sent_events)  # Salva histórico de eventos enviados
                except Exception as e:
                    error = f"Telegram: Erro ao salvar histórico de mensagens: {e}"
                    send_message(bot_alert, admin_chat_id, error)
                    print(error)





links = {
    'https://goldenwin.com.br': {'status': True, 'custom_message': 'Site principal está fora do ar!'},
}

# Função para verificar o status dos links
def check_links():
    while True:
        for link, data in links.items():
            try:
                # Verifica se o link está acessível (timeout de 5 segundos)
                response = requests.get(link, timeout=5)
                if response.status_code == 200:
                    # Se estava fora do ar e agora está acessível
                    if not data['status']:
                        bot_alert.send_message(admin_chat_id, text=f'Conexão reestabelecida: {link}')
                        data['status'] = True
                else:
                    raise requests.RequestException()
            except requests.RequestException:
                # Se estava acessível e agora está fora do ar
                if data['status']:
                    bot_alert.send_message(admin_chat_id, text=data['custom_message'])
                    data['status'] = False
        time.sleep(5)

# Variável global para armazenar a última mensagem enviada
last_message = {}

def send_message(chat_bot, chat_id, msg):
    global last_message

    # Verifica se a última mensagem enviada para o chat_id é igual à nova mensagem
    if chat_id in last_message and last_message[chat_id] == msg:
        return  # Não envia se a mensagem for repetida
    
    try:
        # Envia a mensagem e armazena como última mensagem enviada
        chat_bot.send_message(chat_id, msg)
        last_message[chat_id] = msg
    except telebot.apihelper.ApiTelegramException as e:
        print(f"Erro ao enviar mensagem para o chat_id {chat_id}: {e}")

# Função para carregar mensagens do arquivo JSON
def carregar_mensagens(arquivo_json):
    with open(arquivo_json, 'r', encoding='utf-8') as file:
        dados = json.load(file)
    return dados['mensagens']

# Função para escolher três mensagens aleatórias e enviá-las em horários diferentes
def enviar_mensagens_aleatorias(arquivo_json):
    mensagens = carregar_mensagens(arquivo_json)
    mensagens_selecionadas = random.sample(mensagens, 3)  # Seleciona 3 mensagens aleatórias

    # Gera três horários aleatórios entre 6:00 e 22:00
    horarios = []
    for _ in range(3):
        # Gera um horário aleatório entre 6:00 (21600 segundos) e 22:00 (79200 segundos)
        horario_aleatorio = random.randint(21600, 79200)
        horarios.append(horario_aleatorio)

    horarios.sort()  # Ordena os horários

    agora = datetime.datetime.now()
    inicio_dia = agora.replace(hour=0, minute=0, second=0, microsecond=0)  # Pega o início do dia

    for i, mensagem in enumerate(mensagens_selecionadas):
        proximo_horario = inicio_dia + timedelta(seconds=horarios[i])
        tempo_espera = (proximo_horario - agora).total_seconds()

        if tempo_espera > 0:
            print(f"Esperando {tempo_espera / 60:.2f} minutos para enviar a próxima mensagem...")
            time.sleep(tempo_espera)  # Aguarda até o horário definido

            # Verifica novamente se ainda estamos dentro do horário de envio
            agora = datetime.datetime.now()  # Atualiza a hora atual após a espera
            if 6 <= agora.hour < 22:
                bot.send_message(CHAT_ID_FREE, mensagem, parse_mode='markdown')
            else:
                print("Fora do horário de envio, não enviando a mensagem.")
        else:
            print("O horário agendado já passou, não enviando a mensagem.")

# Função assíncrona para rodar o script diariamente
def rodar_todo_dia(arquivo_json):
    while True:
        agora = datetime.datetime.now()
        
        # Verifica se estamos entre 6:00 e 22:00
        if 6 <= agora.hour < 22:
            print(f"Iniciando envio de mensagens do dia {agora.strftime('%d/%m/%Y')}")
            enviar_mensagens_aleatorias(arquivo_json)
        
        # Calcula quanto tempo falta até 6:00 do próximo dia
        if agora.hour >= 22:  # Se já passou das 22:00
            inicio_amanha = (agora + timedelta(days=1)).replace(hour=6, minute=0, second=0, microsecond=0)
        else:  # Se ainda está antes de 22:00
            inicio_amanha = agora.replace(hour=6, minute=0, second=0, microsecond=0)
            # Se já passou das 6:00, devemos programar para o próximo dia
            if agora.hour >= 6:
                inicio_amanha += timedelta(days=1)
        
        tempo_ate_amanha = (inicio_amanha - agora).total_seconds()

        # Garante que o tempo de espera seja não negativo
        if tempo_ate_amanha > 0:
            print(f"Próximo envio em {tempo_ate_amanha / 3600:.2f} horas.")
            time.sleep(tempo_ate_amanha)  # Pausa até o próximo horário de envio
        else:
            print("O cálculo do tempo até o próximo envio resultou em um valor negativo.")

# Função para iniciar o monitoramento em uma thread separada
def start_monitoring():
    thread = Thread(target=check_links)
    thread.daemon = True  # Permite que o programa termine mesmo que a thread esteja rodando
    thread.start()

def start_bot():
    print("Inicializando o sistema...")
    while True:
        connect_to_database()
        send_signals_from_database(bot)
        update_prices_in_database()
        check_results()
        update_messages_with_results(bot)
        check_and_notify_events()
        delete_signals(bot)
        time.sleep(2)

async def main():
    try:
        connect_to_database()
        scheduler = BackgroundScheduler()
        scheduler.add_job(remove_random_loss, 'cron', hour=23, minute=25)
        scheduler.add_job(rodar_todo_dia, args=['json/mensagens.json'])
        scheduler.add_job(send_alert_message, 'cron', hour=6)
        scheduler.add_job(send_daily_report, 'cron', day='last', hour=23, minute=30, args=[bot, "thismonth", None])
        scheduler.add_job(send_daily_report, 'cron', hour=23, minute=30, args=[bot, "today", None])
        scheduler.start()
        print("Tarefas agendadas com sucesso!")  
        start_bot()
    except Exception as e:
        error = f'Telegram: Null Reference - {e}'
        send_message(bot_alert, admin_chat_id, error)
        print(error)
    
        
# Executa o loop principal
if __name__ == "__main__":
    asyncio.run(main())
    
