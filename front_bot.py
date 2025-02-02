from waitress import serve
from flask_mail import Mail, Message
from flask import Flask, render_template, jsonify, request, send_file, abort, render_template_string
from flask_socketio import SocketIO
from flask_socketio import SocketIO, emit
import subprocess
import os
import jwt
from cryptography.fernet import Fernet
from flask import Flask, send_from_directory
import telebot
import re
import threading
import msgpack
import time
import pickle
import json
import logging 
from flask import Flask, request, jsonify, render_template_string, Response
from pywebpush import webpush, WebPushException, Vapid
import pandas as pd
from flask import send_from_directory, stream_with_context
from flask import redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
from flask import flash
from datetime import datetime, timedelta
from datetime import time as dt_time  # Importando o tipo time diretamente
from calendario import update_events
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
import base64
from flask import Flask, request, jsonify
from pywebpush import webpush, WebPushException, Vapid
import codecs
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization
import secrets
import string
from db_connection import get_connection, get_engine
from configparser import ConfigParser
import uuid
import platform
from webauthn import (
    generate_registration_options,
    verify_registration_response,
    generate_authentication_options,
    verify_authentication_response
)
import warnings
import configparser
import pandas as pd
import json
from flask_cors import CORS
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from collections import deque
import sys
import traceback
from sqlalchemy import MetaData, Table, select, func
from sqlalchemy.orm import sessionmaker
import psutil
from werkzeug.serving import run_simple
from sseclient import SSEClient
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse
import docker
from support_bot import bot, generate_invite_links, check_licenses, get_group_name, create_free_license
from telebot import TeleBot, types
from flask_cors import CORS
from flask import Flask, request, jsonify


# Configuração
config = ConfigParser()
config_path = os.path.join(os.path.dirname(__file__), 'config.ini')
config.read(config_path)
warnings.filterwarnings('ignore', category=UserWarning, module='pd')
auto_start_str = config.get('Scripts', 'auto_start')
auto_start = int(auto_start_str)
auto_reload_str = config.get('Scripts', 'layout_auto_update')
auto_reload = int(auto_reload_str)
sys.stdout.reconfigure(encoding='utf-8')
product_free = config.get('Produtos', 'free')
product_trade = config.get('Produtos', 'trade')
product_otc = config.get('Produtos', 'otc')
product_app = config.get('Produtos', 'app')
product_crypto = config.get('Produtos', 'crypto')
dias_180 = config.get('Produtos', '180dias')
dias_30 = config.get('Produtos', '30dias')
metadata = MetaData()
restart_scheduled = False
SCRIPT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'front_bot.py')
engine = get_engine()


if platform.system() == 'Windows':
    client_docker = None
    print('Windows sem Docker')
else:
    client_docker = docker.from_env()


try:
    client_docker.ping()
    print("Conexão com o Docker bem-sucedida!")
except Exception as e:
    print(f"Erro ao conectar ao Docker: {e}")

# Configurações do Twilio
TWILIO_ACCOUNT_SID = 'your_twilio_account_sid'
TWILIO_AUTH_TOKEN = 'your_twilio_auth_token'
client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)


# Desativar logs do APScheduler
logging.getLogger('apscheduler').setLevel(logging.INFO)

def connect_to_database():
    global conn
    conn = get_connection()

app = Flask(__name__)
CORS(app)



if 'SECRET_KEY' not in os.environ:
    os.environ['SECRET_KEY'] = secrets.token_hex(32)
app.config['SECRET_KEY'] = os.environ['SECRET_KEY']
app.config['SESSION_TYPE'] = 'filesystem'
if auto_reload == 1:
    layout_update = True
else:
    layout_update = False    
app.config['TEMPLATES_AUTO_RELOAD'] = layout_update
# Configurações de e-mail usando Flask-Mail
app.config['MAIL_SERVER'] = config['Email']['smtp_server']
app.config['MAIL_PORT'] = int(config['Email']['smtp_port'])
app.config['MAIL_USERNAME'] = config['Email']['username']
app.config['MAIL_PASSWORD'] = config['Email']['password']
app.config['MAIL_USE_TLS'] = False  # Você vai usar SSL, então TLS deve ser False
app.config['MAIL_USE_SSL'] = True  # Habilita SSL
mail = Mail(app)
key = 'mD6D8ZK7DNcmPjqHgPX73RNQwg7UadHEppz1cWplNSE='
cipher_suite = Fernet(key)





smtp_server = 'smtp.hostinger.com'
smtp_port = 465
username = 'goldenwin@goldenwin.com.br'
password = 'JGSAjhfkj!7422'
sender_email = 'goldenwin@goldenwin.com.br'

# Configuração do logging
logs_folder = 'logs'
os.makedirs(logs_folder, exist_ok=True)

# Nome do arquivo de log
log_file = os.path.join(logs_folder, 'front_bot.log')

# Configurando o logger
logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)

logger = logging.getLogger('front_bot')

# Configurando o logger do Flask para usar o mesmo arquivo
flask_logger = logging.getLogger('werkzeug')  # 'werkzeug' é o logger usado pelo Flask internamente
flask_logger.setLevel(logging.INFO)

# Criando um manipulador para o Flask utilizar
file_handler = logging.FileHandler(log_file)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

# Adicionando o manipulador ao logger do Flask
flask_logger.addHandler(file_handler)

# Dicionário para armazenar a posição da última leitura de cada arquivo de log
last_positions = {}

def save_log_to_file(log_file, log_entry):
    logs_folder = 'logs'
    os.makedirs(logs_folder, exist_ok=True)
    
    log_file_path = os.path.join(logs_folder, log_file)
    
    with open(log_file_path, 'a', encoding='utf-8') as f:
        f.write(log_entry + '\n')



@app.route('/get_all_logs')
def get_all_logs():
    logs_folder = 'logs'

    def generate_logs():
        log_positions = {}

        while True:
            log_files = [f for f in os.listdir(logs_folder) if os.path.isfile(os.path.join(logs_folder, f))]
            
            for log_file in log_files:
                file_path = os.path.join(logs_folder, log_file)
                logs = []

                with open(file_path, 'rb') as f:
                    f.seek(0, os.SEEK_END)
                    end_position = f.tell()
                    buffer_size = 1024
                    buffer = bytearray()
                    while len(logs) < 10 and end_position > 0:
                        start_position = max(end_position - buffer_size, 0)
                        f.seek(start_position)
                        buffer = f.read(end_position - start_position) + buffer
                        lines = buffer.split(b'\n')
                        logs = [line.decode('utf-8') for line in lines if line][-10:]
                        end_position = start_position

                    log_positions[log_file] = f.tell()

                    for log in logs:
                        yield f"id: {log_file}\ndata: {log}\n\n"

            # Continuar enviando novos logs em tempo real
            for log_file in log_files:
                file_path = os.path.join(logs_folder, log_file)
                with open(file_path, 'r', encoding='utf-8') as f:
                    f.seek(log_positions.get(log_file, 0))
                    new_logs = f.readlines()
                    if new_logs:
                        log_positions[log_file] = f.tell()
                        for log in new_logs:
                            yield f"id: {log_file}\ndata: {log}\n\n"

            time.sleep(1)

    return Response(stream_with_context(generate_logs()), content_type='text/event-stream')



def create_users_table():
    connect_to_database
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            cpf TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password TEXT
        );
    ''')
    conn.commit()
    



def is_authenticated():
    if 'user_id' in session:
        user_id = session['user_id']
        connect_to_database()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT l.id FROM users u
            JOIN licences l ON u.licence_id = l.id
            WHERE u.id = %s AND l.venciment > date('now')
        ''', (user_id,))
        licence = cursor.fetchone()
        
        return licence is not None
    return False

# Função para verificar a existência da tabela 'users'
def check_table_users_exists():
    connect_to_database()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users';")
    table_exists = cursor.fetchone() is not None
    
    return table_exists

# Função para criar a tabela 'users' se ela não existir
def create_users_table():
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            cpf TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password TEXT
            type TEXT
            mac TEXT
            ip TEXT
        );
    ''')
    conn.commit()
    

@app.route('/create_user', methods=['POST'])
def create_user():
    new_name = request.form['new_name']
    new_email = request.form['new_email']
    new_cpf = request.form['new_cpf']
    new_password = request.form['new_password']
    confirm_password = request.form['confirm_password']

    # Verifica se as senhas coincidem
    if new_password != confirm_password:
        return jsonify(success=False, message='As senhas não coincidem. Por favor, digite novamente.')
    
    connect_to_database()
    cursor = conn.cursor()

    # Verifica se o CPF já existe no banco de dados
    cursor.execute('SELECT email, cpf, password FROM users WHERE cpf = %s', (new_cpf,))
    existing_user = cursor.fetchone()

    if existing_user:
        # Atualiza o registro existente se a senha estiver ausente
        hashed_password = generate_password_hash(new_password)
        cursor.execute('''UPDATE users SET name = %s, email = %s, password = %s WHERE cpf = %s''',
                       (new_name, new_email, hashed_password, new_cpf))
        conn.commit()
        return jsonify(success=True, message='Usuário atualizado com sucesso!')
    else:
        # Insere um novo usuário no banco de dados com tipo 'user'
        hashed_password = generate_password_hash(new_password)
        cursor.execute('INSERT INTO users (name, email, cpf, password, type) VALUES (%s, %s, %s, %s, %s)',
                       (new_name, new_email, new_cpf, hashed_password, 'user'))
        conn.commit()
        return jsonify(success=True, message='Usuário cadastrado com sucesso!')

@app.route('/change_password', methods=['POST'])
def change_password():
    # Obtém os dados do formulário
    new_password = request.form.get('secret_password')
    confirm_password = request.form.get('confirm_password')
    user_identifier = request.form.get('user_identifier')  # CPF ou email

    # Verifica se as senhas coincidem
    if not new_password or not confirm_password:
        return jsonify(success=False, message='Por favor, preencha todos os campos.')
    
    if new_password != confirm_password:
        return jsonify(success=False, message='As senhas não coincidem. Por favor, digite novamente.')
    print(user_identifier, new_password, confirm_password)
    # Conexão ao banco de dados
    connect_to_database()
    cursor = conn.cursor()

    # Tenta encontrar o usuário pelo CPF ou Email
    cursor.execute('SELECT password FROM users WHERE cpf = %s::text OR email = %s', (user_identifier, user_identifier))

    existing_user = cursor.fetchone()

    if existing_user:
        # Atualiza a senha
        hashed_password = generate_password_hash(new_password)
        cursor.execute('UPDATE users SET password = %s WHERE cpf = %s::text OR email = %s', (hashed_password, user_identifier, user_identifier))
        conn.commit()
        return jsonify(success=False, message='Senha alterada com sucesso! Por favor faça seu login.')
        
    else:
        return jsonify(success=False, message='Usuário não encontrado.')


@app.route('/create_user_admin', methods=['POST'])
def create_user_admin():
    new_name = request.form['new_name']
    new_email = request.form['new_email']
    new_cpf = request.form['new_cpf']
    new_password = request.form['new_password']
    confirm_password = request.form['confirm_password']
    trade = request.form.get('trade', 0)  # Obtém o valor de 'trade' (0 ou 1)
    otc = request.form.get('otc', 0)  # Obtém o valor de 'otc' (0 ou 1)
    username = request.form['username']
    phone = request.form['phone']
    user_type = request.form['type']

    # Verifica se as senhas coincidem
    if new_password != confirm_password:
        flash('As senhas não coincidem. Por favor, digite novamente.', 'warning')
        return redirect('/form_page')  # Redireciona para a página do formulário

    connect_to_database()
    cursor = conn.cursor()

    # Verifica se o CPF já existe no banco de dados
    cursor.execute('SELECT cpf FROM users WHERE cpf = %s', (new_cpf,))
    if cursor.fetchone():
        flash('CPF já cadastrado. Por favor, utilize outro CPF.', 'warning')
        return redirect('/form_page')

    # Verifica se o e-mail já existe no banco de dados
    cursor.execute('SELECT email FROM users WHERE email = %s', (new_email,))
    if cursor.fetchone():
        flash('E-mail já cadastrado. Por favor, utilize outro e-mail.', 'warning')
        return redirect('/form_page')

    # Verifica se o nome de usuário já existe no banco de dados
    cursor.execute('SELECT username FROM users WHERE username = %s', (username,))
    if cursor.fetchone():
        flash('Nome de usuário já cadastrado. Por favor, utilize outro nome de usuário.', 'warning')
        return redirect('/form_page')

    # Insere um novo usuário no banco de dados
    hashed_password = generate_password_hash(new_password)
    cursor.execute('''
        INSERT INTO users (name, email, cpf, password, trade, otc, username, phone, type)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    ''', (new_name, new_email, new_cpf, hashed_password, trade, otc, username, phone, user_type))
    conn.commit()
    flash('Usuário cadastrado com sucesso!', 'success')

    # Retorna vazio, pois não há necessidade de renderizar ou redirecionar
    return '', 204


def get_client_ip():
    return request.remote_addr

@app.route('/verify_mac', methods=['POST'])
def verify_mac():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"status": "warning", "message": "Usuário não autenticado."}), 401

    mac = request.json.get('mac')
    client_ip = get_client_ip()
    connect_to_database()
    cursor = conn.cursor()
    cursor.execute('SELECT mac, ip FROM users WHERE id = %s', (user_id,))
    stored_mac, stored_ip = cursor.fetchone()
    

    if (stored_mac and stored_mac != mac) or (not stored_mac and stored_ip != client_ip):
        return jsonify({"status": "error", "message": "Sessão inválida. Faça login novamente."}), 401

    return jsonify({"status": "success", "message": "MAC/IP address verificado com sucesso."})

def generate_faceid_token():
    return str(uuid.uuid4())

def store_faceid_token(user_id, faceid_token):
    connect_to_database()
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET faceid_credential = %s WHERE id = %s', (faceid_token, user_id))
    conn.commit()

def verify_faceid_token(user_id, provided_token):
    connect_to_database()
    cursor = conn.cursor()
    cursor.execute('SELECT faceid_credential FROM users WHERE id = %s', (user_id,))
    stored_token = cursor.fetchone()
    if stored_token and stored_token[0] == provided_token:
        return True
    return False

@app.route('/webauthn/register', methods=['POST'])
def register():
    user_id = request.json['user_id']
    registration_options = generate_registration_options(
        rp_name="Your App Name",
        rp_id="yourapp.com",
        user_id=user_id,
        user_name="User Name"
    )
    return jsonify(registration_options)

@app.route('/webauthn/register/response', methods=['POST'])
def register_response():
    response = request.json
    verified_registration = verify_registration_response(
        response,
        user_id=response['user_id']
    )
    if verified_registration:
        return jsonify({"status": "success"})
    return jsonify({"status": "failure"}), 400

@app.route('/webauthn/authenticate', methods=['POST'])
def authenticate():
    user_id = request.json['user_id']
    authentication_options = generate_authentication_options(
        rp_id="yourapp.com",
        user_id=user_id
    )
    return jsonify(authentication_options)

@app.route('/webauthn/authenticate/response', methods=['POST'])
def authenticate_response():
    response = request.json
    verified_authentication = verify_authentication_response(
        response,
        user_id=response['user_id']
    )
    if verified_authentication:
        return jsonify({"status": "success"})
    return jsonify({"status": "failure"}), 400

@app.route('/login', methods=['GET', 'POST'])
def login():
    for attempt in range(5):  # Tenta até 5 vezes
        try:
            if request.method == 'POST':
                connect_to_database()
                login_user = request.form['login_user']
                password = request.form['password']
                mac = request.form.get('mac')

                unique_id = request.cookies.get('unique_id')
                client_ip = get_client_ip()
                cursor = conn.cursor()
                if unique_id:
                    session_token = encrypt_token(unique_id)
                # Buscando o usuário pelo login (email, cpf ou username)
                cursor.execute('SELECT id, password, type FROM users WHERE email = %s OR cpf = %s OR username = %s', 
                               (login_user, login_user, login_user))
                user = cursor.fetchone()

                if user:
                    user_id, stored_password, user_type = user

                    # Verificação de senha None
                    if stored_password is None:
                        flash('Você ainda não criou sua senha. Por favor, clique em "Primeiro Acesso" para criar sua senha.', 'warning')
                        return redirect(url_for('homeindex'))

                    # Verificar se a senha é válida
                    password_valid = check_password_hash(stored_password, password) if password else False

                    if password_valid:
                        cursor.execute('SELECT expiration_date, app, free FROM licenses WHERE user_id = %s', (user_id,))
                        licenses = cursor.fetchall()
                        valid_license = False
                        current_date = datetime.now()
                        for license in licenses:
                            expiration_date = license[0]
                            l_app = license[1]
                            free = license[2]
                            if expiration_date >= current_date and (l_app == 1 or free == 1):
                                valid_license = True
                                break
                        if not valid_license:
                            flash('Licença expirou ou é inválida, contate o suporte.', 'warning')
                            return redirect(url_for('homeindex'))
                        
                        # Desativar todas as sessões anteriores
                        cursor.execute('SELECT id FROM user_sessions WHERE user_id = %s AND is_active = True AND unique_id != %s ORDER BY login_time DESC LIMIT 1', 
                                       (user_id, unique_id))
                        session_active = cursor.fetchone()
                        cursor.execute('DELETE FROM user_sessions WHERE user_id = %s', (user_id,))

                        # Reativar sessão anterior se existir
                        if session_active:
                            cursor.execute(
                                '''
                                UPDATE user_sessions 
                                SET is_active = TRUE,
                                token = %s 
                                WHERE id = %s
                                ''', 
                                (session_token, session_active[0],)
                            )

                        # Verificar sessão atual e criar/atualizar se necessário
                        cursor.execute('SELECT is_active FROM user_sessions WHERE unique_id = %s AND user_id = %s', (unique_id, user_id))
                        atual_stat = cursor.fetchone()

                        if atual_stat:
                            cursor.execute(
                                'UPDATE user_sessions SET mac = %s, ip = %s, login_time = %s, is_active = TRUE token = %s WHERE unique_id = %s AND user_id = %s',
                                (mac, client_ip, datetime.now(), session_token, unique_id, user_id)
                            )
                        else:
                            cursor.execute(
                                'INSERT INTO user_sessions (user_id, mac, ip, unique_id, login_time, is_active, token) VALUES (%s, %s, %s, %s, %s, TRUE, %s)',
                                (user_id, mac, client_ip, unique_id, datetime.now(), session_token)
                            )

                        conn.commit()
                        flash('Login bem-sucedido!', 'success')
                        session['user_id'] = user_id
                        session['user_type'] = user_type
                        session['mac'] = mac
                        session['ip'] = client_ip
                        session.pop('_flashes', None)

                        return redirect(url_for('index') if user_type == "admin" else url_for('index'))
                    else:
                        flash('Credenciais incorretas.', 'error')
                else:
                    flash('Credenciais não correspondem a um usuário válido.', 'warning')

            return redirect(url_for('homeindex'))
        except Exception as e:
            print(f"Tentativa {attempt + 1}: Erro ao fazer login", e)
            if attempt < 4:  # Não espera após a última tentativa
                time.sleep(2)

    # Se todas as tentativas falharem
    flash('Erro ao tentar fazer login. Por favor, tente novamente mais tarde.', 'warning')
    return redirect(url_for('homeindex'))

@app.route('/api/login', methods=['POST'])
def api_login():
    try:
        connect_to_database()

        login_user = request.form.get('login_user')
        password = request.form.get('password')
        mac = request.form.get('mac')

        cursor = conn.cursor()
        
        # Buscando o usuário pelo login (email, cpf ou username)
        cursor.execute('SELECT id, password, type FROM users WHERE email = %s OR cpf = %s OR username = %s', 
                       (login_user, login_user, login_user))
        user = cursor.fetchone()

        if user:
            user_id, stored_password, user_type = user

            # Verificação de senha None
            if stored_password is None:
                return jsonify(success=False, message='Você ainda não criou sua senha.')

            # Verificar se a senha é válida
            password_valid = check_password_hash(stored_password, password) if password else False

            if password_valid:
                cursor.execute('SELECT expiration_date, app, free FROM licenses WHERE user_id = %s', (user_id,))
                licenses = cursor.fetchall()
                valid_license = False
                current_date = datetime.now()
                
                for license in licenses:
                    expiration_date = license[0]
                    l_app = license[1]
                    free = license[2]
                    if expiration_date >= current_date and (l_app == 1 or free == 1):
                        valid_license = True
                        break

                if valid_license:
                    # Retornar o user_id no JSON de sucesso
                    return jsonify(success=True, message='Login bem-sucedido!', user_id=user_id)
                else:
                    return jsonify(success=False, message='Licença expirou ou é inválida.')
            else:
                return jsonify(success=False, message='Credenciais incorretas.')
        else:
            return jsonify(success=False, message='Credenciais não correspondem a um usuário válido.')
        
    except Exception as e:
        print("Erro ao fazer login:", e)
        return jsonify(success=False, message='Erro ao tentar fazer login. Por favor, tente novamente mais tarde.')
    finally:
        cursor.close()
        conn.close()


# Carregar a chave
def load_key():
    return open("secret.key", "rb").read()

# Criptografar o token
def encrypt_token(token):
    key = load_key()
    fernet = Fernet(key)
    encrypted_token = fernet.encrypt(token.encode())
    return encrypted_token

@app.route('/api/get_token', methods=['GET'])
def get_token():
    # Ler o token do arquivo de configuração
    config = configparser.ConfigParser()
    config.read('config.ini')
    
    TOKEN = config.get('Telegram', 'TOKEN')
    
    # Criptografar o token
    encrypted_token = encrypt_token(TOKEN)
    
    return jsonify({'encrypted_token': encrypted_token.decode()}), 200


@app.route('/check_session')
def check_session():
    try:
        # Verifica se o usuário está autenticado via sessão
        if 'user_id' in session and session.get('user_type') == 'admin':
            return jsonify({"session_active": True, "user_id": session['user_id'], "user_name": session.get('user_name')})

        # Verifica o unique_id no cookie
        unique_id = request.cookies.get('unique_id')

        if unique_id:
            connect_to_database()
            cursor = conn.cursor()

            # Verificar se há sessões ativas para o unique_id
            cursor.execute('SELECT is_active, user_id FROM user_sessions WHERE unique_id = %s', (unique_id,))
            active_sessions = cursor.fetchall()

            if active_sessions:
                # Encontrar a primeira sessão ativa
                for session_record in active_sessions:
                    session_active, user_id = session_record

                    if session_active:
                        # Verificar validade das licenças
                        cursor.execute('SELECT expiration_date FROM licenses WHERE user_id = %s', (user_id,))
                        licenses = cursor.fetchall()

                        current_date = datetime.now()
                        valid_license = any(license[0] >= current_date for license in licenses)

                        if valid_license:
                            return jsonify({"session_active": True, "user_id": user_id})

            # Se não houver sessões ativas
            return jsonify({"session_active": False})
        
        # Se não houver unique_id no cookie
        return jsonify({"session_active": False})

    except Exception as e:
        print(f"Erro: {e}")
        return jsonify({"session_active": False, "error": str(e)})


@app.route('/')
def homeindex():
    return render_template('landpage.html')

from user_agents import parse

def format_brazilian_phone(cellphone):
    # Remove caracteres não numéricos
    digits = ''.join(filter(str.isdigit, cellphone))

    # Verifica se o número começa com '55' (código do Brasil)
    if digits.startswith('55'):
        digits = digits[2:]  # Remove o código do país

    # Formatação com base no número de dígitos
    if len(digits) == 11:  # Formato: (xx) xxxxx-xxxx
        return f"({digits[0:2]}) {digits[2:7]}-{digits[7:]}"
    elif len(digits) == 10:  # Formato: (xx) xxxx-xxxx
        return f"({digits[0:2]}) {digits[2:6]}-{digits[6:]}"
    elif len(digits) == 9:  # Formato: (xx) xxxxx-xxxx
        return f"({digits[0:2]}) {digits[2:7]}-{digits[7:]}"
    elif len(digits) == 8:  # Formato: (xx) xxxx-xxxx
        return f"({digits[0:2]}) {digits[2:6]}-{digits[6:]}"
    else:
        return cellphone  # Retorna o número original se não se encaixar em nenhum formato


def format_cpf(cpf):
    # Remove caracteres não numéricos
    digits = ''.join(filter(str.isdigit, cpf))
    
    # Verifica se o CPF tem 11 dígitos
    if len(digits) == 11:
        return f"{digits[0:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:11]}"
    else:
        return cpf  # Retorna o número original se não tiver 11 dígitos



@app.route('/index')
def index():
    try:
        user_id = session.get('user_id')
        unique_id = request.cookies.get('unique_id')
        user_cellphone = None
        user_cpf = None
        user_email = None
        user_config = None
        if unique_id:
            connect_to_database()
            cursor = conn.cursor()

            # Verificar se há sessões ativas para o unique_id
            cursor.execute('SELECT is_active, user_id, token FROM user_sessions WHERE unique_id = %s', (unique_id,))
            active_sessions = cursor.fetchall()

            if active_sessions:
                # Encontrar a primeira sessão ativa
                for session_record in active_sessions:
                    session_active, user_id, session_token = session_record

                    if session_active:
                        # Verificar validade das licenças
                        cursor.execute('SELECT expiration_date, app FROM licenses WHERE user_id = %s', (user_id,))
                        licenses = cursor.fetchall()
                        cursor.execute('SELECT name, config, cpf, cellphone, email FROM users WHERE id = %s', (user_id,))
                        result = cursor.fetchone()  # Usa fetchone() já que esperamos uma única linha
                        
                        if result:
                            user_name, user_config, user_cpf, user_cellphone, user_email = result
                            if user_config is None:
                                user_config = 'default_config_value'
                        else:
                            user_name, user_config = None, None
                        if user_cellphone:
                            user_cellphone = format_brazilian_phone(user_cellphone)

                        if user_cpf:
                            user_cpf = format_cpf(user_cpf)    
                        current_date = datetime.now()
                        valid_license = any(license[0] >= current_date for license in licenses)

                        first_name = user_name.split()[0]
                        if valid_license:
                            # Verifica se o aplicativo tem acesso
                            app_access = any(license[1] == 1 for license in licenses)
                            if app_access:
                                session['user_id'] = user_id
                                session['user_type'] = "user"
                                user_license_status = "Ativa"
                                
                                # Obtém a maior data de expiração posterior à data atual
                                future_expirations = [license[0] for license in licenses if license[0] > current_date]
                                user_expiration = max(future_expirations, default=None) if future_expirations else None
                                if user_expiration:
                                    user_expiration = user_expiration.strftime('%d/%m/%Y')
                                user_plan = "Plus"
                                # Verifica o User-Agent
                                user_agent = parse(request.headers.get('User-Agent'))
                                if user_agent.is_mobile:
                                    return render_template('index_mobile.html', session_token=session_token, first_name=first_name, user_name=user_name, user_id=user_id, user_config=user_config, user_cpf=user_cpf, user_cellphone=user_cellphone, user_email=user_email, user_license_status=user_license_status, user_expiration=user_expiration, user_plan=user_plan)
                                else:
                                    return render_template('index.html', session_token=session_token, first_name=first_name, user_name=user_name, user_id=user_id, user_config=user_config, user_cpf=user_cpf, user_cellphone=user_cellphone, user_email=user_email, user_license_status=user_license_status, user_expiration=user_expiration, user_plan=user_plan)
                            else:
                                flash('Licença válida, mas não possui acesso ao aplicativo.', 'warning')
                                return redirect(url_for('homeindex'))
                        else:
                            flash('Licença expirou ou é inválida, contate o suporte.', 'warning')
                            # Limpar sessão do usuário
                            session.pop('user_id', None)
                            session.pop('user_type', None)
                            session.pop('mac', None)
                            session.pop('ip', None)
                            
                            # Atualizar status da sessão no banco de dados
                            cursor.execute('DELETE FROM user_sessions WHERE unique_id = %s', (unique_id,))
                            conn.commit()
                            return redirect(url_for('homeindex'))
            
            # Se não houver sessões ativas
            return redirect(url_for('homeindex'))
        
        # Se não houver unique_id no cookie
        return redirect(url_for('homeindex'))
    
    except Exception as e:
        print(f"Erro: {e}")  # Adicione logging apropriado em vez de print em produção
        return redirect(url_for('homeindex'))


@app.route('/indexadmin')
def indexadmin():
    # Obter o unique_id do cookie
    unique_id = request.cookies.get('unique_id')
    admin_template=1
    try:
        if 'user_id' in session and session.get('user_type') == 'admin':
            user_id = session['user_id']
            mac = session.get('mac')
            client_ip = session.get('ip')
            connect_to_database()
            cursor = conn.cursor()
            cursor.execute('SELECT mac, ip, name FROM users WHERE id = %s', (user_id,))
            stored_mac, stored_ip, user_name = cursor.fetchone()

            first_name = user_name.split()[0]
            return render_template('indexadmin.html', user_name=first_name, user_id=user_id)
        else:
            if unique_id:
                connect_to_database()
                cursor = conn.cursor()
                
                # Verificar se há sessões ativas para o unique_id
                cursor.execute('SELECT is_active, user_id FROM user_sessions WHERE unique_id = %s', (unique_id,))
                active_sessions = cursor.fetchall()

                if active_sessions:
                    # Encontrar a primeira sessão ativa
                    for session_record in active_sessions:
                        session_active, user_id = session_record

                        if session_active:
                            # Obter informações de licença
                            cursor.execute('SELECT expiration_date FROM licenses WHERE user_id = %s', (user_id,))
                            licenses = cursor.fetchall()

                            # Obter informações do usuário
                            cursor.execute('SELECT mac, ip, name FROM users WHERE id = %s', (user_id,))
                            stored_mac, stored_ip, user_name = cursor.fetchone()

                            first_name = user_name.split()[0]
                            valid_license = False
                            current_date = datetime.now()

                            # Verificar validade das licenças
                            for license in licenses:
                                expiration_date = license[0]
                                if expiration_date >= current_date:
                                    valid_license = True
                                    break     

                            if valid_license:
                                return render_template('indexadmin.html', user_name=first_name, user_id=user_id)
                            else:
                                flash('Licença expirou ou é inválida, contate o suporte.', 'warning')
                                return redirect(url_for('homeindex'))
                
                # Se não houver sessões ativas
                return redirect(url_for('homeindex'))
            
            # Se não houver unique_id no cookie
            return redirect(url_for('homeindex'))
    
    except Exception as e:
        print(e)
        return redirect(url_for('homeindex', admin_template=admin_template))
        

@app.route('/logout', methods=['POST'])
def logout():
    unique_id = request.cookies.get('unique_id')
    
    # Certifique-se de que a conexão com o banco de dados está configurada
    connect_to_database()  # Supondo que você tenha uma função para conectar ao banco de dados
    cursor = conn.cursor()  # Correção aqui
    
    # Limpar sessão do usuário
    session.pop('user_id', None)
    session.pop('user_type', None)
    session.pop('mac', None)
    session.pop('ip', None)
    
    # Atualizar status da sessão no banco de dados
    cursor.execute('DELETE FROM user_sessions WHERE unique_id = %s', (unique_id,))
    conn.commit()  # Certifique-se de confirmar a transação
    
    return redirect(url_for('homeindex'))





@app.route('/events')
def events():
    try:
        with open('json/events.json', 'r', encoding='utf-8') as f:
            events_data = json.load(f)
            events = events_data
    except FileNotFoundError:
        return jsonify({"error": "Arquivo não encontrado."}), 404
    except json.JSONDecodeError:
        return jsonify({"error": "Erro ao decodificar JSON."}), 400
    except UnicodeDecodeError as e:
        return jsonify({"error": f"Erro de decodificação: {str(e)}"}), 400
    
    return jsonify(events)

def get_all_prices():
    connect_to_database()
    cursor = conn.cursor()

    cursor.execute("SELECT symbol, timeframe, open_price, current_price, open_time FROM trading_data order by symbol ASC")
    rows = cursor.fetchall()

    results = {}
    for row in rows:
        symbol, timeframe, open_price, current_price, open_time = row

        if isinstance(open_time, dt_time):
            open_time = open_time.strftime('%H:%M:%S')  # Formato de hora, ajuste conforme necessário

        if symbol not in results:
            results[symbol] = {}

        results[symbol][timeframe] = {
            "open_price": open_price,
            "current_price": current_price,
            "open_time": open_time,
            "timeframe": timeframe
        }

    # Salve os dados em um arquivo JSON
    with open('json/prices_mt5.json', 'w') as json_file:
        json.dump(results, json_file, indent=4)


@app.route('/sse/signals')
def sse_signals():
    connect_to_database()
    user_id = session.get('user_id')
    if user_id:
        # Consulta para verificar as licenças
        cursor = conn.cursor()
        cursor.execute('SELECT expiration_date, trade, otc, crypto, free FROM licenses WHERE user_id = %s', (user_id,))
        licenses = cursor.fetchall()
    
    # Verifica se há licenças válidas
    has_valid_license = False
    forex_count = otc_count = crypto_count = 0  # Inicializa as colunas
    if licenses:
        for expiration_date, trade_col, otc_col, crypto_col, free_col in licenses:
            if expiration_date > datetime.now():  # Verifica se a licença é válida
                has_valid_license = True
                forex_count += trade_col
                otc_count += otc_col
                crypto_count += crypto_col
                
                if free_col == 1:
                    forex_count += 1
                    otc_count += 1
                    crypto_count += 1
                else:
                    if trade_col == 1:
                        forex_count += 1
                    if otc_col == 1:
                        otc_count += 1
                    if crypto_col == 1:
                        crypto_count += 1

    def generate():
        while True:
            try:
                update_trading_signals_json()  # Atualiza o arquivo JSON
                combined_signals = []
                bot_signals = get_bot_signals(user_id)
                # Defina as variáveis das fontes (1 = incluir, 0 = não incluir)
                forex_enabled = 1 if has_valid_license and forex_count > 0 else 0
                otc_enabled = 1 if has_valid_license and otc_count > 0 else 0
                crypto_enabled = 1 if has_valid_license and crypto_count > 0 else 0

                sources = {
                    'forex': forex_enabled,
                    'otc': otc_enabled,
                    'crypto': crypto_enabled
                }

                filename = 'json/trading_signals_combined.json'
                if os.path.exists(filename):
                    with open(filename, 'r', encoding='utf-8') as json_file:
                        all_signals = json.load(json_file)
                        combined_signals = [
                            signal for signal in all_signals if sources.get(signal['source'], 0) == 1
                        ]
                else:
                    print(f"Arquivo {filename} não encontrado.")

                # Agrupando 'combined_signals' e 'bot_signals' em um único dicionário
                message = {
                    "combined_signals": combined_signals,
                    "bot_signals": bot_signals
                }

                # Enviando como uma única mensagem SSE
                yield f"data: {json.dumps(message)}\n\n"
                time.sleep(1)  # Ajustar para o intervalo correto de atualização
            
            except json.JSONDecodeError:
                print("Erro ao decodificar o arquivo JSON.")
                yield f"data: {{\"error\": \"Erro ao decodificar o arquivo JSON.\"}}\n\n"
                time.sleep(1)
            except Exception as e:
                print(f"Erro inesperado: {e}")
                yield f"data: {{\"error\": \"{str(e)}\"}}\n\n"
                time.sleep(1)

    return Response(generate(), content_type='text/event-stream')
    
def get_bot_signals(user_id):
    # Conectando ao banco de dados
    connect_to_database()
    cursor = conn.cursor()
    
    # Obter a data de hoje no formato correto
    today = datetime.today().strftime('%Y-%m-%d')
    
    # Consulta SQL para buscar o balance_type do usuário na tabela `users`
    balance_query = "SELECT config FROM users WHERE id = %s;"
    cursor.execute(balance_query, (user_id,))
    user_config = cursor.fetchone()
    
    # Extrair o balance_type do config do usuário
    if user_config and user_config[0]:
        config = user_config[0]
        balance_type = config.get("iq_bot").get("balance_type")

    else:
        balance_type = None  # Defina um valor padrão caso balance_type não exista
    
    # Consulta SQL para buscar os sinais do usuário com base no balance_type
    query = """
    SELECT 
        signal_time, symbol, direction, timeframe, status, profit, order_id, balance_type, id
    FROM 
        scheduled_signals
    WHERE 
        DATE(signal_time) = %s AND
        user_id = %s AND
        balance_type = %s AND
        status != 'late'
    ORDER BY signal_time DESC;
    """
    
    # Executa a consulta e obtém os resultados
    cursor.execute(query, (today, user_id, balance_type))
    rows = cursor.fetchall()
    
    # Converte o resultado em uma lista de dicionários para maior clareza
    signals = [
        {
            "signal_time": row[0].strftime('%H:%M') if isinstance(row[0], datetime) else row[0],
            "symbol": row[1],
            "direction": row[2],
            "timeframe": row[3],
            "status": row[4],
            "profit": row[5],
            "order_id": row[6],
            "balance_type": row[7],
            "id": row[8]
        }
        for row in rows
    ]
    
    return signals


def update_trading_signals_json():
    conn = get_connection()  # Função que obtém a conexão com o banco de dados
    now = datetime.now()

    if conn is None:
        print("Falha ao conectar ao banco de dados")
        return

    try:
        query = """
            SELECT 
            ts.id,
            ts.symbol,
            ts.direction,
            ts.timeframe,
            ts.time,
            ts.result,
            ts.open,
            ts.close,
            ts.open_g1,
            ts.close_g1,
            ts.open_g2,
            ts.payout,
            ts.source,
            CASE 
                WHEN %s > ts.time::timestamp AND ts.result IS NULL THEN td.open_price 
                ELSE NULL 
            END AS open_price,
            CASE 
                WHEN %s > ts.time::timestamp AND ts.result IS NULL THEN td.current_price 
                ELSE NULL 
            END AS current_price,
            CASE 
                WHEN %s > ts.time::timestamp AND ts.result IS NULL THEN 
                    CASE
                        WHEN td.open_price IS NOT NULL 
                            AND td.current_price IS NOT NULL 
                            AND td.open_price::numeric IS NOT NULL 
                            AND td.current_price::numeric IS NOT NULL 
                        THEN CASE
                                WHEN td.current_price > td.open_price THEN 'CALL'
                                WHEN td.current_price < td.open_price THEN 'PUT'
                                ELSE 'DOJI'
                             END
                        ELSE NULL
                    END
                ELSE NULL
            END AS calculated_direction,
            CASE 
                WHEN %s > ts.time::timestamp AND ts.result IS NULL THEN 
                    CASE
                        WHEN td.open_price IS NOT NULL 
                            AND td.current_price IS NOT NULL 
                            AND td.open_price::numeric IS NOT NULL 
                            AND td.current_price::numeric IS NOT NULL 
                        THEN CASE
                                WHEN CASE
                                        WHEN td.current_price > td.open_price THEN 'CALL'
                                        WHEN td.current_price < td.open_price THEN 'PUT'
                                        ELSE 'DOJI'
                                     END = ts.direction THEN 'WIN'
                                WHEN td.current_price = td.open_price THEN 'EMPATE'
                                ELSE 'LOSS'
                             END
                        ELSE NULL
                    END
                ELSE NULL
            END AS result_comparison
        FROM trading_signals ts
        LEFT JOIN trading_data td ON td.symbol = ts.symbol AND td.timeframe = ts.timeframe
        WHERE ts.time::date = %s
        ORDER BY ts.id DESC;
        """

        # Abrir o cursor
        with conn.cursor() as cursor:
            # Executar a consulta passando o parâmetro now para os lugares onde "NOW()" foi substituído
            cursor.execute(query, (now, now, now, now, now.date()))

            # Obter os resultados da query
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()

            # Converter os resultados em um DataFrame
            df = pd.DataFrame(rows, columns=columns)

            # Preencher valores NaN com strings vazias
            df.fillna("", inplace=True)
            
            # Converter colunas de data/hora para string
            for column in df.columns:
                if pd.api.types.is_datetime64_any_dtype(df[column]):
                    df[column] = df[column].astype(str)
            
            # Salvar o JSON combinado em um único arquivo
            filename = 'json/trading_signals_combined.json'
            with open(filename, 'w') as json_file:
                json.dump(df.to_dict(orient='records'), json_file)
        

    except Exception as e:
        print(f"Erro ao consultar o banco de dados: {e}")



@app.route('/json/manifest.json')
def manifest():
    return send_from_directory('json', 'manifest.json')

@app.route('/scripts_html')
def scripts_html():
    return send_from_directory('static/js', 'scripts.js')


@app.route('/service-worker.js')
def service_worker():
    return send_from_directory('static/js', 'service-worker.js')

@app.route('/offline')
def offline():
    return send_from_directory('templates', 'offline.html')


@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory('static', filename)

@app.route('/favicon.ico')
def favicon():
    return send_from_directory('./static/icons', 'favicon.ico')

@app.route('/icons/<path:filename>')
def icons(filename):
    return send_from_directory('./static/icons', filename)

@app.route('/static/<path:filename>')
def logo(filename):
    return send_from_directory('static', filename)

@app.route('/scripts/<path:filename>')
def chart(filename):
    return send_from_directory('scripts', filename)

# Caminho para salvar as chaves VAPID
VAPID_KEYS_FILE = 'json/vapid_keys.json'

# Função para converter a chave pública para base64
def public_key_to_base64(public_key):
    return base64.urlsafe_b64encode(
        public_key.public_bytes(
            encoding=serialization.Encoding.X962,
            format=serialization.PublicFormat.UncompressedPoint
        )
    ).decode('utf-8')

# Função para converter a chave privada para base64
def private_key_to_base64(private_key):
    return base64.urlsafe_b64encode(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
    ).decode('utf-8')

# Função para converter base64 para a chave pública
def base64_to_public_key(key_str):
    return ec.EllipticCurvePublicKey.from_encoded_point(
        ec.SECP256R1(),
        base64.urlsafe_b64decode(key_str)
    )

# Função para converter base64 para a chave privada
def base64_to_private_key(key_str):
    return serialization.load_pem_private_key(
        base64.urlsafe_b64decode(key_str),
        password=None
    )

# Função para gerar e salvar as chaves VAPID
def generate_vapid_keys():
    private_key = ec.generate_private_key(ec.SECP256R1())
    public_key = private_key.public_key()
    keys = {
        "public_key": public_key_to_base64(public_key),
        "private_key": private_key_to_base64(private_key)
    }
    with open(VAPID_KEYS_FILE, 'w') as f:
        json.dump(keys, f)
    return keys

# Função para carregar as chaves VAPID
def load_vapid_keys():
    if not os.path.exists(VAPID_KEYS_FILE):
        return generate_vapid_keys()
    
    try:
        with open(VAPID_KEYS_FILE, 'r') as f:
            keys = json.load(f)
        return {
            "public_key": base64_to_public_key(keys["public_key"]),
            "private_key": base64_to_private_key(keys["private_key"])
        }
    except (json.JSONDecodeError, KeyError, ValueError):
        # Se o arquivo não contiver um JSON válido ou chaves ausentes, gere novas chaves
        return generate_vapid_keys()

# Carregar as chaves VAPID (ou gerar se não existirem ou se houver um erro de leitura)
vapid_keys = load_vapid_keys()

VAPID_PUBLIC_KEY = vapid_keys["public_key"]
VAPID_PRIVATE_KEY = vapid_keys["private_key"]
VAPID_CLAIMS = {
    "sub": "mailto:seu-email@example.com"
}

@app.route('/subscribe', methods=['POST'])
def subscribe():
    subscription_info = request.get_json()
    # Salve subscription_info no seu banco de dados
    return jsonify({"message": "Inscrição recebida com sucesso!"}), 201

def send_push_notification(subscription_info, message_body):
    try:
        webpush(
            subscription_info,
            message_body,
            vapid_private_key=VAPID_PRIVATE_KEY,
            vapid_claims=VAPID_CLAIMS
        )
    except WebPushException as ex:
        print(f"Falha ao enviar notificação: {ex}")

@app.route('/send_notification', methods=['POST'])
def send_notification():
    subscription_info = request.get_json().get('subscription')
    message_body = request.get_json().get('message')
    send_push_notification(subscription_info, message_body)
    return jsonify({"message": "Notificação enviada com sucesso!"}), 201

# Função para gerar uma chave aleatória
def generate_license_key():
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(20))  # Chave com 20 caracteres aleatórios

# Rota para exibir o formulário HTML
@app.route('/add_license', methods=['GET'])
def add_license_form():
    return render_template_string(open('add_license.html').read())


def delete_signals():
    TOKEN = config.get('Telegram', 'TOKEN')
    CHAT_ID_M5 = int(config.get('Telegram', 'CHAT_ID_M5'))
    CHAT_ID_M5_OTC = int(config.get('Telegram', 'CHAT_ID_M5_OTC'))
    CHAT_ID_M1 = int(config.get('Telegram', 'CHAT_ID_M1'))
    CHAT_ID_M1_OTC = int(config.get('Telegram', 'CHAT_ID_M1_OTC'))
    CHAT_ID_M15 = int(config.get('Telegram', 'CHAT_ID_M15'))
    CHAT_ID_M15_OTC = int(config.get('Telegram', 'CHAT_ID_M15_OTC'))
    bot = telebot.TeleBot(TOKEN)
        
    try:
            connect_to_database()
        # Conectar ao banco de dados
            cursor = conn.cursor()
            
            # Executar a consulta
            cursor.execute("SELECT id, symbol, timeframe, message_id, response_id FROM trading_signals WHERE is_deleted = 1")
            
            # Recuperar todos os resultados
            signals = cursor.fetchall()
            
            # Processar cada linha
            for signal in signals:
                id, symbol, timeframe, message_id, response_id = signal

                if timeframe == 'M5' and 'OTC' in symbol:
                    chat_id = CHAT_ID_M5_OTC
                elif timeframe == 'M5':
                    chat_id = CHAT_ID_M5
                elif timeframe == 'M1' and 'OTC' in symbol:
                    chat_id = CHAT_ID_M1
                elif timeframe == 'M1':
                    chat_id = CHAT_ID_M1_OTC
                elif timeframe == 'M15' and 'OTC' in symbol:
                    chat_id = CHAT_ID_M15
                elif timeframe == 'M15':
                    chat_id = CHAT_ID_M15_OTC

                # Excluir mensagens com base no timeframe
                if response_id is not None:
                    try:
                        bot.delete_message(chat_id, response_id)
                        print("Resposta ao sinal:", signal, " excluida com sucesso")
                    except:
                        print("Resposta não encontrada no Chat do telegram")    
                try:
                    bot.delete_message(chat_id, message_id)
                    print("Mensagem do sinal:", signal, " excluida com sucesso")
                except:
                    print("Mensagem não encontrada no chat do telegram")    

                cursor.execute("DELETE FROM trading_signals  WHERE id = %s", (id,))
                conn.commit()
                print("Sinal: ",signal, "excluido com sucesso")

    except Exception as e:
        print(f'Error: {e}')


@app.route('/delete_signal/<int:signal_id>', methods=['DELETE'])
def delete_signal(signal_id):
    response = {}
    try:
            connect_to_database()
            cursor = conn.cursor()

            # Verificar se o sinal existe
            cursor.execute("SELECT id FROM trading_signals WHERE id = %s", (signal_id,))
            if cursor.fetchone() is None:
                response = {"status": "error", "message": "Signal not found"}
                return jsonify(response), 404

            # Executar a exclusão lógica usando a nova coluna
            cursor.execute("UPDATE trading_signals SET is_deleted = 1 WHERE id = %s", (signal_id,))
            conn.commit()
            delete_signals()
            
            # Verificar se alguma linha foi atualizada
            if cursor.rowcount > 0:
                response = {"status": "success", "message": "Sinal marcado para exclusão"}
            else:
                response = {"status": "error", "message": "Failed to update signal"}

    except Exception as e:
        response = {"status": "error", "message": str(e)}

    return jsonify(response)


@app.route('/restart_front', methods=['POST'])
def restart_front():
    try:
        # Verifica o sistema operacional
        if platform.system() == 'Windows':
            # Executa o script batch no Windows
            subprocess.run(['restart_front.bat'], check=True)
        else:
            # Executa o script shell no Linux
            subprocess.run(['bash', 'restart_front.sh'], check=True)
        
        return jsonify({'status': 'success', 'message': 'Script executed successfully...'})
    
    except subprocess.CalledProcessError as e:
        return jsonify({"message": f"Error occurred: {e}"}), 500

def schedule_restart():
    global restart_scheduled
    time.sleep(1)  # Espera por 5 segundos
    if restart_scheduled:
        restart_front()
        restart_scheduled = False  # Reseta o status ap s reiniciar

def load_config():
    config = configparser.ConfigParser()
    config.read('config.ini')
    return config

def save_config(config):
    global restart_scheduled
    with open('config.ini', 'w') as configfile:
        config.write(configfile)
        
    if not restart_scheduled:
        restart_scheduled = True
        threading.Thread(target=schedule_restart).start()
        return jsonify({'status': 'success', 'message': 'Config updated and Flask will restart in 5 seconds...'})
    else:
        return jsonify({'status': 'info', 'message': 'Restart already scheduled, please wait.'})

@app.route('/config', methods=['GET', 'POST', 'DELETE'])
def get_config():
    config = load_config()
    
    if request.method == 'POST':
        data = request.json

        # Atualiza as seções e variáveis existentes
        for section, variables in data.items():
            if not config.has_section(section):
                config.add_section(section)
            for key, value in variables.items():
                config[section][key] = value

        save_config(config)
        return jsonify({"message": "Configurações salvas com sucesso!"})

    elif request.method == 'DELETE':
        data = request.json
        section = data.get('section')
        key = data.get('key')

        # Remover uma seção
        if section and not key:
            config.remove_section(section)
        # Remover uma variável
        elif section and key:
            config.remove_option(section, key)

        save_config(config)
        return jsonify({"message": "Removido com sucesso!"})

    # Converte o configparser para um dicionário
    config_dict = {section: dict(config.items(section)) for section in config.sections()}
    
    return jsonify(config_dict)

@app.route('/.well-known/acme-challenge/<filename>')
def serve_letsencrypt_challenge(filename):
    print("Servindo Well Known")
    # Caminho completo para o arquivo de desafio
    challenge_path = os.path.join('.well-known/acme-challenge', filename)
    
    # Verificar se o arquivo existe
    if os.path.exists(challenge_path):
        return send_file(challenge_path, mimetype='text/plain')
    else:
        abort(404)


@app.route('/sale/other', methods=['POST'])
def compra_aprovada():
    # Verifica se o conteúdo recebido está no formato JSON
    data = request.get_json()
    
    # Imprime os dados recebidos no console
    print(data)
    
    return 'Compra aprovada', 200


@app.route('/sale/compra_aprovada', methods=['POST'])
def create_payment():
    
    data = request.json  # Obtém os dados do JSON recebido na requisição
    print("Processando pagamento:")

    # Obter os dados do comprador a partir do JSON
    name = data.get('customer', {}).get('name')
    email = data.get('customer', {}).get('email')
    cpf = data.get('customer', {}).get('document')
    cellphone = data.get('customer', {}).get('phone_number')
    payment_id = data.get('sale_id')
    payment_key = data.get('checkout_id')
    payment_status = data.get('status')
    license_type = []
    # Iterar sobre os produtos e definir o tipo de licença com base no código do produto
    for product in data.get('products', []):
        product_code = product.get('id')
        if product_code in product_otc:
            license_type.append('otc')
        if product_code in product_trade:
            license_type.append('trade')
        if product_code in product_crypto:
            license_type.append('crypto')
        if product_code in product_free:
            license_type.append('free')
        if product_code in product_app:
            license_type.append('app')
            
    print(license_type)
    # Obter a data de pagamento e converter para datetime
    payment_date = datetime.now()
    days = 180 if any(product.get('id') in dias_180 for product in data.get('products', [])) else \
           30 if any(product.get('id') in dias_30 for product in data.get('products', [])) else 0
    expiration_date = payment_date + timedelta(days=days)

    # Criação do usuário no banco de dados
    user_created = create_user_db(name, cpf, email, 'user', None, cellphone)
    if user_created:
        # Se o pagamento for aprovado
        if payment_status == 'APPROVED':
            user_id = user_created[0]
            insert_license(user_id, payment_date, license_type, '6', payment_id, payment_key, expiration_date, cellphone)
            user_cpf = cpf  # CPF do usuário recém-criado
            user_email = email  # E-mail do usuário recém-criado
            user_key = payment_key  # Chave de pagamento

            # Chamando a função 'send_license_code' para enviar o código da licença
            with app.test_request_context(method='POST'):
                # Simulando a chamada com os dados necessários
                request.form = {
                    'user_cpf': user_cpf,
                    'user_email': user_email,
                    'user_key': user_key
                }
                try:
                    response = send_license_code()
                    print(response)  # Imprime a resposta da função
                    return jsonify({'success': True, 'message': 'Pagamento processado e licença enviada!'}), 200
                except Exception as e:
                    print(f'Erro ao enviar o código da licença: {str(e)}')
                    return jsonify({'success': False, 'message': 'Erro ao enviar o código da licença.'}), 500
        else:
            print('Aguardando pagamento.')
            return jsonify({'success': False, 'message': 'Pagamento não aprovado.'}), 400
    else:
        print('Erro ao criar usuário.')
        return jsonify({'success': False, 'message': 'Erro ao criar usuário.'}), 500

@app.route('/thanks')
def thanks():
    return render_template('thanks.html')

@app.route('/sale/carrinho_abandonado', methods=['POST'])
def cart_abandonment():
    {"error": "Token inválido"}, 401  # Retorna uma resposta de erro se o token for inválido
    
    data = request.json  # Obtém os dados do JSON recebido na requisição

    # Extrair as informações do lead
    transaction_id = data.get('checkout_id')  # 'checkout_id' no novo JSON
    name = data.get('customer', {}).get('name')
    email = data.get('customer', {}).get('email')
    phone = data.get('customer', {}).get('phone_number')
    utm_campaign = data.get('utm', {}).get('utm_campaign')  # UTM agora vindo do novo JSON
    utm_source = data.get('utm', {}).get('utm_source')      # UTM agora vindo do novo JSON
    utm_medium = data.get('utm', {}).get('utm_medium')      # UTM agora vindo do novo JSON
    utm_content = data.get('utm', {}).get('utm_content')    # UTM agora vindo do novo JSON
    last_step = data.get('status')  # 'status' no novo JSON
    payment_method = None  # Não presente no novo JSON
    updated_at = data.get('created_at')  # 'created_at' no novo JSON
    
    # Inserir ou atualizar os dados no banco de dados
    try:
        with conn.cursor() as cursor:
            upsert_query = """
            INSERT INTO leads (transaction_id, name, email, phone, utm_campaign, utm_source, utm_medium, utm_content, last_step, payment_method, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (transaction_id) 
            DO UPDATE SET 
                name = EXCLUDED.name,
                email = EXCLUDED.email,
                phone = EXCLUDED.phone,
                utm_campaign = EXCLUDED.utm_campaign,
                utm_source = EXCLUDED.utm_source,
                utm_medium = EXCLUDED.utm_medium,
                utm_content = EXCLUDED.utm_content,
                last_step = EXCLUDED.last_step,
                payment_method = EXCLUDED.payment_method,
                updated_at = EXCLUDED.updated_at;
            """
            # Executando o upsert com os valores extraídos
            cursor.execute(upsert_query, (transaction_id, name, email, phone, utm_campaign, utm_source, utm_medium, utm_content, last_step, payment_method, updated_at))
            conn.commit()
            print("Lead inserido ou atualizado com sucesso.")
    except Exception as e:
        conn.rollback()
        print(f"Erro ao inserir ou atualizar lead: {e}")

    return {"message": "Carrinho abandonado processado com sucesso."}, 200

def get_user_chatid_by_email(email):
    try:
        cursor = conn.cursor()
        # Faz a busca do chat ID pelo email na coluna `tele_user`
        query = "SELECT tele_user FROM users WHERE email = %s"
        cursor.execute(query, (email,))
        result = cursor.fetchone()
        return result[0] if result else None
    except Exception as e:
        print(f"Erro ao buscar o chat ID do usuário: {e}")
        return None


@app.route('/sale/reembolso_emitido', methods=['POST'])
def invoice_refunded():
    data = request.json  # Obtém os dados do JSON recebido na requisição
    print("Processando reembolso:")

    payment_id = data.get('sale_id')  # 'sale_id' no novo JSON
    buyer_email = data['customer']['email']  # 'email' dentro de 'customer'
    buyer_name = data['customer'].get('name', 'Cliente')  # Nome do cliente se disponível
    new_expiration_date = datetime.now()  # Define a nova data de expiração como a data atual

    try:
        cursor = conn.cursor()
        # Atualizando a licença e a data de expiração
        update_query = """
            UPDATE licenses
            SET refunded = '1', expiration_date = %s
            FROM users
            WHERE users.id = licenses.user_id
            AND licenses.payment_id = %s
            AND users.email = %s
        """
        cursor.execute(update_query, (new_expiration_date, payment_id, buyer_email))
        conn.commit()  # Confirma as alterações no banco de dados
        print("Reembolso processado.")

        # Preparando o conteúdo do e-mail e Telegram
        subject = 'Confirmação de Reembolso'
        email_body = f"""
        <body style="font-family: Arial, sans-serif; background-color: #f4f4f4; margin: 0; padding: 20px;">
            <div style="background-color: #ffffff; border-radius: 8px; padding: 20px; box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);">
                <div style="text-align: center; margin-bottom: 20px;">
                    <h1>Olá, {buyer_name}!</h1>
                </div>
                <p>Informamos que seu reembolso foi processado com sucesso.</p>
                <p><strong>Identificação da Compra:</strong> {payment_id}</p>
                <p><strong>Data de Processamento:</strong> {new_expiration_date.strftime('%d/%m/%Y')}</p>
                <p>Se tiver dúvidas, entre em contato com nosso suporte.</p>
                <div style="text-align: center; margin-top: 20px; font-size: 12px; color: #888888;">
                    <p>Atenciosamente,</p>
                    <p>Equipe GoldenWin</p>
                </div>
            </div>
        </body>
        """
        
        telegram_body = (
            f"Olá {buyer_name},\n\n"
            "Seu reembolso foi processado com sucesso.\n"
            f"Identificação da Compra: {payment_id}\n"
            f"Data de Processamento: {new_expiration_date.strftime('%d/%m/%Y')}\n\n"
            "Para mais informações, entre em contato com nosso suporte.\n\n"
            "Atenciosamente,\n"
            "Equipe GoldenWin"
        )

        # Enviando o e-mail
        msg = Message(subject,
                      sender=config['Email']['username'],
                      recipients=[buyer_email])
        msg.html = email_body
        mail.send(msg)
        print("E-mail de confirmação de reembolso enviado.")

        # Enviando mensagem pelo Telegram se tiver o chat_id
        user_chatid = get_user_chatid_by_email(buyer_email)  # Função para buscar o chat_id pelo e-mail
        
        if user_chatid:
            bot.send_message(
                user_chatid,
                text=telegram_body,
                parse_mode='Markdown'
            )
            print("Mensagem de reembolso enviada pelo Telegram.")

        return jsonify({'success': True, 'message': 'Reembolso processado e notificado.'}), 200

    except Exception as e:
        conn.rollback()  # Reverte as alterações em caso de erro
        print(f"Erro ao processar o reembolso no banco de dados: {e}")
        return jsonify({'success': False, 'message': 'Erro ao processar o reembolso.'}), 500


import re

def normalize_phone(phone):
    # Remove caracteres como () - e espaços
    phone = re.sub(r"[^\d]", "", phone)
    
    # Se o telefone tiver 8 ou 9 dígitos, adiciona o código do Brasil
    if len(phone) in [8, 9]:  
        phone = "55" + phone
    elif len(phone) == 10:  # Telefone com DDD e 8 dígitos
        phone = "55" + phone
    elif len(phone) == 11 and not phone.startswith("55"):  # Telefone com DDD e 9 dígitos
        phone = "55" + phone

    return phone

def get_contacts_by_phone(cellphone):
    try:
        connect_to_database()
        with conn.cursor() as cursor:
            cursor.execute("SELECT chat_user_id FROM contacts WHERE phone_number = %s", (cellphone,))
            result = cursor.fetchone()  # Retorna todas as linhas correspondentes
            return result
    except Exception as e:
        error = f"Erro ao obter dados do contato: {e}"
        print(error)


def create_user_db(name, cpf, email, type, phone, cellphone):
    cursor = conn.cursor()
    chat_user_id = None
    # Verificar se o usuário já existe
    cursor.execute("SELECT id FROM users WHERE email = %s OR cpf = %s", (email, cpf))
    user = cursor.fetchone()
    if cellphone is not None:
        chat_user_id = get_contacts_by_phone(cellphone)
    if user:
        # Criar lista de campos a serem atualizados
        fields = []
        values = []
       
        # Adicionar cada campo à lista somente se o valor não for None
        if name is not None:
            fields.append("name = %s")
            values.append(name)
        if phone is not None:
            fields.append("phone = %s")
            values.append(phone)
        if phone is not None:
            fields.append("phone2 = %s")
            values.append(phone)
        if cellphone is not None:
            fields.append("cellphone = %s")
            values.append(cellphone)
        if type is not None:
            fields.append("type = %s")
            values.append(type)
        if cpf is not None:
            fields.append("cpf = %s")
            values.append(cpf)
        if chat_user_id is not None:
            fields.append("tele_user = %s")
            values.append(chat_user_id)    

        # Construir a query apenas com os campos a serem atualizados
        if fields:
            update_query = f"UPDATE users SET {', '.join(fields)} WHERE email = %s OR cpf = %s"
            values.extend([email, cpf])  # Adicionar as condições à lista de valores
            cursor.execute(update_query, tuple(values))
            print(f"Usuário {name} atualizado no banco de dados.")
    else:
        # Inserir novo registro
        insert_query = """
        INSERT INTO users (name, email, phone, phone2, cellphone, type, cpf, tele_user) 
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(insert_query, (name, email, cellphone, cellphone, cellphone, type, cpf, chat_user_id))
        print(f"Usuário {name} adicionado ao banco de dados.")
    
    # Confirmar a transação
    conn.commit()

    # Buscar o ID do usuário recém-criado ou atualizado
    cursor.execute("SELECT id FROM users WHERE email = %s OR cpf = %s", (email, cpf))
    user_created = cursor.fetchone()
    return user_created



def insert_license(user_id, payment_date, license_type, create_user, payment_id, payment_key, expiration_date, phone):
    cursor = conn.cursor()
    key = generate_license_key()  # Verifique se isso retorna uma string válida
    trade = 0
    otc = 0
    crypto = 0
    free = 0
    l_app = 0
    # Verificando o tipo de licença
    if 'trade' in license_type:
        trade = 1
    if 'otc' in license_type:
        otc = 1
    if 'crypto' in license_type:
        crypto = 1
    if 'free' in license_type:
        free = 1
    if 'app' in license_type:
        l_app = 1
        
    select_user_query = """
        SELECT name, cellphone FROM Users WHERE id = %s
    """
    check_payment_key_query = """
        SELECT * FROM licenses WHERE payment_key = %s OR payment_id = %s
    """
    update_license_query = """
        UPDATE licenses 
        SET payment_date = %s, expiration_date = %s, key = %s, create_user = %s, phone = %s, otc = %s, trade = %s, crypto = %s, free = %s, app = %s, payment_id = %s 
        WHERE payment_key = %s
    """
    insert_license_query = """
        INSERT INTO licenses (user_id, key, payment_date, expiration_date, create_user, phone, otc, trade, crypto, free, app, payment_id, payment_key) 
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    
    try:
        cursor.execute(select_user_query, (user_id,))
        user_result = cursor.fetchone()
        if user_result:
            user_name, user_cellphone = user_result
            print(f"Usuário encontrado: {user_name}, Telefone: {user_cellphone}")
    
            # Verificar se a payment_key já existe
            cursor.execute(check_payment_key_query, (payment_key, payment_id))
            payment_key_exists = cursor.fetchone()
    
            if payment_key_exists:
                # Atualizar a licença existente
                cursor.execute(update_license_query, (payment_date, expiration_date, key, create_user, user_cellphone, otc, trade, crypto, free, l_app, payment_id, payment_key))
                print(f"Licença atualizada para o usuário {user_name}.")
            else:
                # Inserir nova licença
                cursor.execute(insert_license_query, (user_id, key, payment_date, expiration_date, create_user, user_cellphone, otc, trade, crypto, free, l_app, payment_id, payment_key))
                print(f"Licença adicionada para o usuário {user_name}.")
            
            # Confirmar a transação
            conn.commit()
        else:
            print("Usuário não encontrado.")
    except Exception as e:
        print(f"Erro ao adicionar licença: {e}")


# Função que processa o evento de contrato criado e adiciona usuário ao banco de dados
def invoice_paid(data):
    print("Processando contrato criado:")
    # Obter os dados do comprador
    name = data['buyer']['name']
    email = data['buyer']['email']
    phone = data['buyer'].get('phone', None)
    phone2 = data['buyer'].get('phone2', None)
    cellphone = data['buyer'].get('cellphone', None)
    payment_id = data.get('id')
    payment_status = data.get('status')
    type = 'user'
    create_user = 6

    # Juntar os productIds dos itens comprados
    product_code = ','.join([item['productId'] for item in data['items']])
    
    license_type = []
    if product_code in product_otc:
        license_type.append('otc')
    elif product_code in product_trade:
        license_type.append('trade')
    elif product_code in product_crypto:
        license_type.append('crypto')
    elif product_code in product_free:
        license_type.append('free')
    elif product_code in product_app:
        license_type.append('app')
    print(license_type)
    # Obter a data de pagamento e converter para datetime
    payment_date = datetime.now()

    # Calcular a data de expiração (payment_date + 30 dias)
    if product_code in dias_180:
        days = 180
    elif product_code in dias_30:
        days = 30
    else:
        days = 0
    expiration_date = payment_date + timedelta(days=days)

    # Criar o usuário no banco de dados
    user_created = create_user_db(name, None, email, type, None, cellphone)
    
    if user_created:
        if payment_status == 'paid':
            user_id = user_created[0]
            insert_license(user_id, payment_date, license_type, create_user, payment_id, None, expiration_date, cellphone)
        else:
            print('Aguardando pagamento')



def process_other_event(data):
    print("Processando outro evento:")
    print(data)
    # Adicione aqui a lógica para outros eventos


@app.route('/validate_license', methods=['POST'])
def validate_license():
    license_code = request.form.get('license_code')
    
    # Remover o caractere '#' se estiver presente
    if license_code.startswith('#'):
        license_code = license_code[1:]

    is_valid = False
    email = None
    name = None
    cpf = None
    try:
        cursor = conn.cursor()
        cursor.execute(""" 
            SELECT u.name, u.cpf, u.email, l.expiration_date 
            FROM licenses l 
            INNER JOIN users u ON u.id = l.user_id 
            WHERE l.key = %s OR l.payment_id = %s; 
        """, (license_code, license_code))
        
        result = cursor.fetchone()
        if result:
            name, cpf, email, expiration_date = result
            if expiration_date >= datetime.now():
                is_valid = True
    except Exception as e:
        print(f"An error occurred: {e}")
    
    return jsonify({'valid': is_valid, 'email': email, 'name': name, 'cpf': cpf})


def get_user_chatid_email(user_data, user_id):
    try:
        with conn.cursor() as cursor:
            query = """
                SELECT name, cpf, cellphone, tele_user, email 
                FROM users 
                WHERE cpf = %s OR email = %s OR id = %s
            """
            cursor.execute(query, (user_data, user_data, user_id))
            result = cursor.fetchone()
            print(result)
            if result:
                return result[0], result[1], result[2], result[3], result[4]
            else:
                print("Usuário não encontrado.")
                return None
    except Exception as e:
        print(f"Erro ao buscar o telefone: {e}")

def generate_reset_token(user_id):
    expiration = datetime.utcnow() + timedelta(minutes=20)
    token = jwt.encode({'user_id': user_id, 'exp': expiration}, app.config['SECRET_KEY'], algorithm='HS256')
    return token

@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    try:
        # Decodifica o token
        data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        user_id = data['user_id']  # Aqui você deve usar o ID do usuário, ajuste conforme necessário

        # Obtenha os dados do usuário a partir do user_id
        name, cpf, email = get_user_data(user_id)  # Implementação da nova função

        if request.method == 'POST':
            new_password = request.form.get('new_password')
            print("senha alterada")
            return render_template('reset_password.html', user_cpf=cpf, name=name, email=email, success=True)

        # Renderiza um formulário de redefinição de senha
        return render_template('reset_password.html', user_cpf=cpf, name=name, email=email)

    except jwt.ExpiredSignatureError:
        return render_template('error_reset_password.html', error="O token de redefinição de senha expirou. Solicite um novo.")
    except jwt.InvalidTokenError:
        return render_template('error_reset_password.html', error="Token inválido.")

def get_user_data(user_id):
    """Obtém os dados do usuário a partir do banco de dados."""
    name = None
    cpf = None
    email = None
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT name, cpf, email
            FROM users
            WHERE id = %s;
        """, (user_id,))
        
        result = cursor.fetchone()
        if result:
            name, cpf, email = result
    except Exception as e:
        print(f"An error occurred: {e}")
    
    return name, cpf, email




@app.route('/send_license_code', methods=['POST'])
def send_license_code():
    user_cpf = request.form.get('user_cpf')
    user_email = request.form.get('user_email')
    user_key = request.form.get('user_key')
    user_cellphone = None
    user_data = user_cpf or user_email
    user_name = None
    user_chatid = None
    user_mail = None
    # Verifica as licenças com base nos dados fornecidos
    licenses, valid_license_exists, CHAT_IDS, user_id = check_licenses(None, None, user_data, user_key)
    print(licenses)
    reset_password_token = generate_reset_token(user_id)  # Gere o token
    reset_password_link = f"https://goldenwin.com.br/reset_password/{reset_password_token}"
    try:
        # Busca o número de telefone do usuário no banco de dados para Telegram
        user_name, user_cpf, user_cellphone, user_chatid, user_mail = get_user_chatid_email(user_data, user_id)    
    except Exception as e:
        print(e)    
    # Inicializa o corpo do e-mail/Telegram
    subject = ''
    mail_body = ''
    telegram_body = ''
    email_sent = False
    telegram_sent = False
    
    
    if licenses:
        # Filtrando as licenças válidas
        valid_licenses = []
        for license in licenses:
            if 'Licença Válida' in license:
                valid_licenses.append(license.strip())
        
        # Criando uma string formatada com as licenças válidas
        valid_licenses_list = ""
        for license in valid_licenses:
            codigo = license.split("Código: ")[1].split("Tipo da licença:")[0].strip()
            tipo = license.split("Tipo da licença: ")[1].split("Data de vencimento:")[0].strip()
            vencimento = license.split("Data de vencimento: ")[1].strip()
            valid_licenses_list += (
                f"<li><strong>Código:</strong> {codigo} <br>"
                f"<strong>Tipo:</strong> {tipo} <br>"
                f"<strong>Data de Vencimento:</strong> {vencimento}</li>"
            )


        subject = 'Detalhes da sua Licença'
        telegram_body = "\n".join(licenses)
        
        mail_body = f"""
        <body style="font-family: Arial, sans-serif; background-color: #f4f4f4; margin: 0; padding: 20px;">
            <div style="background-color: #ffffff; border-radius: 8px; padding: 20px; box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);">
                <div style="text-align: center; margin-bottom: 20px;">
                    <h1>Olá, {user_name}!</h1>
                </div>
                <p>Obrigado por adquirir sua licença da GoldenWin!</p>
                <p>Abaixo estão as suas informações de Licença:</p>
                <div style="margin: 10px 0;">
                    <strong>Telefone:</strong> {user_cellphone}<br>
                    <strong>CPF:</strong> {user_cpf}<br>
                    <strong>Códigos das Licenças Válidas:</strong>
                    <ul style="list-style-type: none; padding: 0;">
                        {valid_licenses_list}
                    </ul>
                    <strong>Link para Trocar a Senha:</strong> <a href="{reset_password_link}">Clique aqui para trocar sua senha</a>
                </div>
                <p>Estamos aqui para ajudar. Se você tiver alguma dúvida, não hesite em nos contatar.</p>
                <div style="text-align: center; margin-top: 20px; font-size: 12px; color: #888888;">
                    <p>Atenciosamente,</p>
                    <p>Equipe GoldenWin</p>
                </div>
            </div>
        </body>
        """

        telegram_body += (
            "\n"  # Adiciona uma linha em branco
            "Caso deseje adquirir uma nova licença ou se precisar de assistência adicional, entre em contato conosco.\n\n"
            f"Você também pode alterar a senha do seu GW-APP [clicando aqui]({reset_password_link})"
        )

    else:
        subject = 'Licença não encontrada'
        mail_body = f"""
        <body>
            <div class="container">
                <div class="header">
                    <h1>Olá, {user_name}!</h1>
                </div>
                <p>Infelizmente, não conseguimos encontrar licenças válidas com os dados fornecidos.</p>
                <p>Certifique-se de que os dados estão corretos e tente novamente. Se precisar de assistência adicional, entre em contato conosco.</p>
                <div class="info">
                    <strong>CPF Fornecido:</strong> {user_cpf}<br>
                    <strong>Link para Trocar a Senha:</strong> <a href="{reset_password_link}">Clique aqui para trocar sua senha</a>
                </div>
                <p>Estamos aqui para ajudar. Se você tiver alguma dúvida, não hesite em nos contatar.</p>
                <div class="footer">
                    <p>Atenciosamente,</p>
                    <p>Equipe GoldenWin</p>
                </div>
            </div>
        </body>
        """
        
        telegram_body = (
            "Olá,\n\n"
            "Não conseguimos encontrar licenças válidas com os dados fornecidos. "
            "Certifique-se de que os dados estão corretos e tente novamente.\n\n"
            "Se você precisar de assistência adicional, entre em contato conosco.\n\n"
            f"Você também pode alterar a senha do seu GW-APP [clicando aqui]({reset_password_link})\n\n"
            "Atenciosamente,\n"
            "Golden Win"
        )


    if user_chatid:
        invite_links = generate_invite_links(CHAT_IDS)
        invite_keyboard = types.InlineKeyboardMarkup(row_width=1)

        for chat_id, link in invite_links.items():
            if link:
                group_name = get_group_name(chat_id)
                if group_name:
                    # Cria o botão com o nome do grupo e link de convite
                    invite_button = types.InlineKeyboardButton(text=f"{group_name}", url=link)
                    invite_keyboard.add(invite_button)

        try:
            # Envia a nova mensagem ao usuário
            bot.send_message(
                user_chatid,
                text=f"{telegram_body}",
                reply_markup=invite_keyboard,
                parse_mode='Markdown'  # Adicionando o modo de formatação Markdown
            )
            telegram_sent = True  # Marca que a mensagem do Telegram foi enviada
        except telebot.apihelper.ApiTelegramException as e:
            print(f'Erro ao enviar mensagem para o usuário: {e}')
    
    if user_mail:
        msg = Message(subject,
                      sender=config['Email']['username'],
                      recipients=[user_mail])
        msg.html = mail_body
        mail.send(msg)
        email_sent = True  # Marca que o e-mail foi enviado
        

    
    # Retorna 200 se pelo menos um envio for bem-sucedido
    if email_sent or telegram_sent:
        flash('Um email foi enviado com sua licença e o link para alteração de senha. Por favor, verifique também a caixa de spam.', 'warning')
        return jsonify({'success': True}), 200
    else:
        flash('Nenhum usuário encontrado. Por favor, entre em contato com o suporte.', 'warning')
        return jsonify({'success': False}), 400

        
@app.route('/metrics/front')
def metrics_stream():
    def generate():
        while True:
            try:
                # Métricas do servidor
                cpu_usage = psutil.cpu_percent(interval=1)
                memory_info = psutil.virtual_memory()
                disk_usage = psutil.disk_usage('/')
                boot_time = psutil.boot_time()
                uptime_seconds = time.time() - boot_time
                days = uptime_seconds // (24 * 3600)
                hours = (uptime_seconds % (24 * 3600)) // 3600
                minutes = (uptime_seconds % 3600) // 60
                seconds = uptime_seconds % 60
                uptime_string = f'{int(days)} dias {int(hours):02}:{int(minutes):02}:{int(seconds):02}'

                # Consulta para obter user_ids conectados
                with conn.cursor() as cur:
                    cur.execute("SELECT id FROM user_sessions WHERE is_active = TRUE")
                    connected_user_ids = [row[0] for row in cur.fetchall()]

                    # Consulta para obter nomes dos usuários conectados
                    if connected_user_ids:
                        user_ids_tuple = tuple(connected_user_ids)
                        query = "SELECT id, name FROM users WHERE id IN %s"
                        cur.execute(query, (user_ids_tuple,))
                        active_users = cur.fetchall()
                    else:
                        active_users = []

                # Lista de usuários ativos e tempo de sessão
                active_users_list = []

                # Dados das métricas
                metrics = {
                    'server_metrics': {
                        'cpu_usage': cpu_usage,
                        'memory_usage': memory_info.percent,
                        'disk_usage': disk_usage.percent,
                        'uptime': uptime_string,
                    },
                }

                yield f"data: {json.dumps(metrics)}\n\n"
                time.sleep(1)
            except Exception as e:
                print(f"Erro ao gerar métricas: {e}")
                break

    return Response(stream_with_context(generate()), content_type='text/event-stream')


@app.route('/get-script_front', methods=['GET'])
def get_script_front():
    # Lê o conteúdo atual do script
    with open(SCRIPT_PATH, 'r') as script_file:
        code = script_file.read()
    
    return jsonify({'code': code})

@app.route('/save-script_front', methods=['POST'])
def save_script_front():
    global restart_scheduled
    new_code = request.json.get('code')

    # Salva as mudanças no script
    with open(SCRIPT_PATH, 'w') as script_file:
        script_file.write(new_code)

    if not restart_scheduled:
        restart_scheduled = True
        threading.Thread(target=schedule_restart).start()
        return jsonify({'status': 'success', 'message': 'Config updated and Flask will restart in 5 seconds...'})
    else:
        return jsonify({'status': 'info', 'message': 'Restart already scheduled, please wait.'})


@app.route('/get_tables_and_columns', methods=['GET'])
def get_tables_and_columns():
    try:
        connect_to_database()
        cur = conn.cursor()

        table_name = request.args.get('table')

        if table_name:
            cur.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = %s
            """, (table_name,))
            columns = cur.fetchall()
            result = [col[0] for col in columns]
        else:
            cur.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
            """)
            tables = cur.fetchall()
            result = [table[0] for table in tables]


        return jsonify(result)

    except Exception as e:
        return jsonify({'error': str(e)}), 500



# Rota para executar scripts SQL
@app.route('/run_sql', methods=['POST'])
def run_sql():
    sql_query = request.form['sql_query']
    connect_to_database()
    cursor = conn.cursor()
    try:
        cursor.execute(sql_query)
        if sql_query.strip().lower().startswith('select'):
            result = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
        else:
            result = []
            columns = []
            conn.commit()
    except Exception as e:
        return jsonify({"error": str(e)})
    return jsonify({"columns": columns, "data": result})

@app.route('/get_table_data', methods=['POST'])
def get_table_data():
    try:
        connect_to_database()
        cur = conn.cursor()

        table_name = request.form.get('table_name')

        if not table_name:
            return jsonify({'error': 'Table name is required'}), 400

        cur.execute(f"SELECT * FROM {table_name}")
        columns = [desc[0] for desc in cur.description]
        rows = cur.fetchall()

        result = {
            'columns': columns,
            'data': rows
        }


        return jsonify(result)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/containers')
def list_containers():
    try:
        logging.debug("Tentando listar containers...")

        # Obtém a lista de containers
        containers = client_docker.containers.list(all=True)
        containers_info = []

        logging.debug(f"Containers encontrados: {len(containers)}")

        for container in containers:
            # Pegar informações da rede e portas
            network_settings = container.attrs['NetworkSettings']
            ip_address = network_settings['IPAddress']  # IP Address do container
            ports = network_settings['Ports']  # Publicação de portas

            # Formatar portas publicadas para exibição
            published_ports = []
            if ports:
                for port, mappings in ports.items():
                    if mappings:
                        for mapping in mappings:
                            published_ports.append({
                                "PrivatePort": port,
                                "PublicPort": mapping.get("HostPort"),
                                "HostIP": mapping.get("HostIp")
                            })

            # Adicionar informações do container à lista
            containers_info.append({
                "id": container.id[:12],  # Pegando os primeiros 12 caracteres do ID
                "name": container.name,
                "status": container.status,
                "ip_address": ip_address if ip_address else "N/A",  # IP Address ou N/A se não existir
                "published_ports": published_ports if published_ports else "No published ports"
            })

        logging.debug("Envio de containers bem-sucedido.")
        return jsonify(containers_info)

    except Exception as e:
        logging.error(f"Erro ao listar containers: {e}")
        return jsonify({"error": str(e)}), 500

# Rota para iniciar um container
@app.route('/containers/start/<container_id>')
def start_container(container_id):
    container = client_docker.containers.get(container_id)
    container.start()
    return jsonify({"status": f"Container {container_id} iniciado com sucesso."})

# Rota para parar um container
@app.route('/containers/stop/<container_id>')
def stop_container(container_id):
    container = client_docker.containers.get(container_id)
    container.stop()
    return jsonify({"status": f"Container {container_id} parado com sucesso."})

# Rota para reiniciar um container
@app.route('/containers/restart/<container_id>')
def restart_container(container_id):
    container = client_docker.containers.get(container_id)
    container.restart()
    return jsonify({"status": f"Container {container_id} reiniciado com sucesso."})

# Rota para verificar o status de um container
@app.route('/containers/status/<container_id>')
def status_container(container_id):
    container = client_docker.containers.get(container_id)
    status = container.status
    return jsonify({"status": f"Status do container {container_id}: {status}"})
    

@app.route('/get_candles', methods=['POST'])
def get_candles():
    try:
        # Obtendo dados do corpo da requisição
        data = request.get_json()
        symbol = data.get('symbol')
        timeframe = data.get('timeframe')

        # Verifica se os parâmetros foram enviados corretamente
        if not symbol or not timeframe:
            return jsonify({'error': 'symbol e timeframe são obrigatórios!'}), 400

        connect_to_database()
        cursor = conn.cursor()

        # Query para buscar os últimos 100 candles
        query = """
            SELECT symbol, timeframe, time, open, high, low, close, source
            FROM (
                SELECT symbol, timeframe, time, 
                    CAST(open AS DECIMAL) AS open, 
                    CAST(high AS DECIMAL) AS high, 
                    CAST(low AS DECIMAL) AS low, 
                    CAST(close AS DECIMAL) AS close, 
                    source 
                FROM candle_history
                WHERE symbol = %s AND timeframe = %s
                UNION ALL
                SELECT symbol, timeframe, open_time AS time, 
                    CAST(open_price AS DECIMAL) AS open, 
                    CAST(high_price AS DECIMAL) AS high, 
                    CAST(low_price AS DECIMAL) AS low, 
                    CAST(current_price AS DECIMAL) AS close, 
                    source 
                FROM trading_data
                WHERE symbol = %s AND timeframe = %s
            ) AS combined
            ORDER BY time DESC
            LIMIT 100;
        """
        
        cursor.execute(query, (symbol, timeframe, symbol, timeframe))
        candles = cursor.fetchall()

        return jsonify(candles)

    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Função personalizada para serializar objetos datetime
def datetime_serializer(obj):
    if isinstance(obj, datetime):
        return obj.strftime('%Y-%m-%d %H:%M:%S')  # Ajuste o formato conforme necessário
    raise TypeError("Tipo não serializável")
    

def tuples_to_dict(cursor, rows):
    columns = [desc[0] for desc in cursor.description]
    return [dict(zip(columns, row)) for row in rows]


@app.route('/get_candles_stream')
def get_candles_stream():
    symbol = request.args.get('symbol')
    timeframe = request.args.get('timeframe')

    if not symbol or not timeframe:
        return jsonify({'error': 'symbol e timeframe são obrigatórios!'}), 400

    def generate():
        connect_to_database()
        try:
            cursor = conn.cursor()
            while True:
                # Query para combinar os dados das duas tabelas
                query = """
                    SELECT symbol, timeframe, time, open, high, low, close, source
                    FROM (
                        SELECT symbol, timeframe, time, 
                            CAST(open AS DECIMAL) AS open, 
                            CAST(high AS DECIMAL) AS high, 
                            CAST(low AS DECIMAL) AS low, 
                            CAST(close AS DECIMAL) AS close, 
                            source 
                        FROM candle_history
                        WHERE symbol = %s AND timeframe = %s
                        UNION ALL
                        SELECT symbol, timeframe, open_time AS time, 
                            CAST(open_price AS DECIMAL) AS open, 
                            CAST(high_price AS DECIMAL) AS high, 
                            CAST(low_price AS DECIMAL) AS low, 
                            CAST(current_price AS DECIMAL) AS close, 
                            source 
                        FROM trading_data
                        WHERE symbol = %s AND timeframe = %s
                    ) AS combined
                    ORDER BY time DESC
                    LIMIT 100;
                """
                
                cursor.execute(query, (symbol, timeframe, symbol, timeframe))
                rows = cursor.fetchall()
                
                # Converte os resultados para um formato de dicionário
                candles = []
                for row in rows:
                    candle = {
                        'symbol': row[0],
                        'timeframe': row[1],
                        'time': row[2],
                        'open': row[3],
                        'high': row[4],
                        'low': row[5],
                        'close': row[6],
                        'source': row[7]
                    }
                    candles.append(candle)
                
                # Converta os dados dos candles para um formato serializável
                for candle in candles:
                    if isinstance(candle['time'], datetime):
                        candle['time'] = datetime_serializer(candle['time'])
                
                # Envia os dados como um evento SSE
                yield f"data: {json.dumps(candles, default=datetime_serializer)}\n\n"
                
                # Espera por um intervalo antes de enviar novos dados
                time.sleep(1)  # Ajuste conforme necessário
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"




@app.route('/get_trading_data', methods=['GET'])
def get_trading_data():
    try:
        connect_to_database()
        cursor = conn.cursor()

        cursor.execute("SELECT DISTINCT source, symbol, timeframe FROM trading_data;")
        data = cursor.fetchall()


        # Formatar os dados como uma lista de dicionários
        result = [{'source': row[0], 'symbol': row[1], 'timeframe': row[2]} for row in data]

        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    

@app.route('/user_config', methods=['GET', 'POST'])
def user_config():
    connect_to_database()
    # Obter o user_id do parâmetro de consulta
    user_id = request.args.get('user_id')

    cursor = conn.cursor()

    if request.method == 'POST':
        # Obter os dados do formulário
        iq_bot_data = {
            'gale': request.form['gale'],
            'amount': request.form['amount'],
            'iq_login': request.form['user_iq_login'],
            'iq_password': request.form['user_iq_password'],
            'balance_type': request.form['balance_type'],
            'multiplier': request.form['multiplier'],
            'payout_min': request.form['payout_min'],
            'auto': request.form['auto'],
            'hora_inicio': request.form['hora_inicio'],
            'hora_fim': request.form['hora_fim'],
            'stop_win': request.form['stop_win'],
            'stop_loss': request.form['stop_loss'],
            'mercado_aberto': '1' if 'mercado_aberto' in request.form else '0',
            'otc': '1' if 'otc' in request.form else '0',
            'live': '1' if 'live' in request.form else '0',
            'list': '1' if 'list' in request.form else '0',
            'concurrent': '1' if 'concurrent' in request.form else '0',
            'await_loss': '1' if 'await_loss' in request.form else '0',
            'max_signals': request.form['max_signals'],
            'before_seconds': request.form['before_seconds']
        }

        # Obter chat_ids selecionados
        chat_ids = request.form.getlist('chat_ids')  # Coleta todos os checkboxes selecionados
        # Atualiza o JSON no banco de dados
        cursor.execute("UPDATE users SET config = %s WHERE id = %s", 
                       (json.dumps({"iq_bot": iq_bot_data, "telegram": {"chat_ids": chat_ids}}), user_id))
        conn.commit()

        # Adiciona uma mensagem flash
        flash("Configurações atualizadas com sucesso.", "success")
        return redirect(url_for('index', user_id=user_id))  # Redireciona para a mesma página

    # Obtém os dados do banco de dados
    cursor.execute("SELECT config FROM users WHERE id = %s", (user_id,))
    config_data = cursor.fetchone()

    # Verifica se o usuário existe
    if config_data is None:
        flash("Usuário não encontrado.", "error")
        return redirect(url_for('index', user_id=user_id))

    config_data = config_data[0]
    cursor.close()
    # Retornar os dados como JSON
    return jsonify({"status": "success", "data": config_data})

def is_valid_email(email):
    return re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email)

def is_valid_cpf(cpf):
    # Implementar lógica de validação de CPF
    return True  # Apenas como exemplo, implemente a validação real


@app.route('/test_form', methods=['GET', 'POST'])
def submit():
    if request.method == 'POST':
    
        # Recebe os dados do formulário
        name = request.form.get('name')
        cpf = request.form.get('cpf')
        cellphone = request.form.get('cellphone')
        email = request.form.get('email')
        print('Recebendo dados', name, cpf, cellphone, email)


        # Validação de CPF e E-mail
        if not is_valid_email(email):
            return jsonify({"success": False, "message": "O e-mail informado é inválido. Por favor, insira um e-mail válido!"}), 400

        if not is_valid_cpf(cpf):
            return jsonify({"success": False, "message": "O CPF informado é inválido. Verifique e tente novamente!"}), 400

        connect_to_database()
        conn = get_connection()
        cursor = conn.cursor()
        phone = cellphone
        cursor.execute("""
            SELECT id
            FROM users
            WHERE cpf = %s OR cellphone = %s OR email = %s;
        """, (cpf, cellphone, email))
        result = cursor.fetchone()
        if result:
            id = result
            try:
                cursor.execute("""
                    SELECT *
                    FROM licenses
                    WHERE user_id = %s AND free = 1;
                """, (id,))
                free_license_tag = cursor.fetchone()
                if free_license_tag:
                    return jsonify({"success": False, "message": "Já existe uma licença gratuita associada a esses dados. Por favor, adquira uma nova licença."}), 400    

                else:
                    try:
                        free_key = create_free_license(name, phone, cpf, email)
                        user_data = cpf or email
                        licenses, valid_license_exists, CHAT_IDS, user = check_licenses(0, phone, user_data, free_key)
                        
                        if valid_license_exists:
                            return jsonify({
                                "success": True,
                                "message": f"Licença registrada com sucesso! Você receberá os acessos por e-mail. Para qualquer dúvida, entre em contato com nosso bot: <a href='https://t.me/goldenwintradebot?start=Olá%20necessito%20suporte'>aqui</a>."
                            })

                        else:
                            return jsonify({"success": False, "message": "Ocorreu um erro ao criar a licença. Por favor, tente novamente mais tarde."})
                    except Exception as e:
                        error = f"Front: Erro ao criar licença: {e}"
                        print(error)
            except Exception as e:
                error = f"Front: Erro ao consultar licença gratuita: {e}"
                print(error)
        else:
            free_key = create_free_license(name, phone, cpf, email)    
            user_data = cpf or email
            licenses, valid_license_exists, CHAT_IDS, user = check_licenses(0, phone, user_data, free_key)
            if valid_license_exists:
                return jsonify({
                    "success": True,
                    "message": f"Licença registrada com sucesso! Você receberá os acessos por e-mail. Para qualquer dúvida, entre em contato com nosso bot: <a href='https://t.me/goldenwintradebot?start=Olá%20necessito%20suporte'>aqui</a>."
                })
        
    else:
        return render_template('landpage.html', message=None)

ping_status = {}

def get_signals_for_user(user_id):
    try:
        query = """
            SELECT 
                id, 
                user_id, 
                signal_time, 
                symbol, 
                direction, 
                timeframe, 
                status, 
                message_id, 
                response_id, 
                executed_at, 
                profit, 
                order_id, 
                stop, 
                balance_type
            FROM scheduled_signals
            WHERE status = 'pending' 
            AND stop IS NULL 
            AND user_id = %s;
        """

        with conn.cursor() as cursor:
            cursor.execute(query, (user_id,))
            pending_signals = cursor.fetchall()

        if pending_signals:
            signals = [
                {
                    "id": row[0],
                    "user_id": row[1],
                    "signal_time": row[2],
                    "symbol": row[3],
                    "direction": row[4],
                    "timeframe": row[5],
                    "status": row[6],
                    "message_id": row[7],
                    "response_id": row[8],
                    "executed_at": row[9],
                    "profit": row[10],
                    "order_id": row[11],
                    "stop": row[12],
                    "balance_type": row[13],
                }
                for row in pending_signals
            ]
        else:
            signals = []


        return signals    
    except Exception as e:
        print(f"Erro ao consultar sinais: {e}")
        return []

def get_user_totals(user_id, balance_type):
    # Conecta ao banco de dados SQLite
    cursor = conn.cursor()
    
    # Obter a data de hoje no formato correto
    today = datetime.today().strftime('%Y-%m-%d')
    
    # Consultar resultados diários para o usuário e data de hoje
    query = """
    SELECT SUM(CAST(profit AS FLOAT)) AS total_profit
    FROM scheduled_signals
    WHERE DATE(signal_time) = %s AND user_id = %s AND balance_type = %s;
    """
    
    try:
        cursor.execute(query, (today, user_id, balance_type))
        daily_result = cursor.fetchone()

        # Verificar se daily_result é None ou se o valor retornado é None
        if daily_result is None or daily_result[0] is None:
            return 0
        
        return daily_result[0]  # Retorna o total de lucro
    except Exception as e:
        print(f"Erro ao consultar os totais do usuário: {e}")
        return 0  # Retorna 0 em caso de erro

@app.route('/api/user_bot_status', methods=['POST'])
def user_bot_status():
    try:
        data = request.json
        user_id = data.get("user_id")
        connect_to_database()
        cursor = conn.cursor()
        # Obtém os dados do banco de dados
        cursor.execute("SELECT config FROM users WHERE id = %s", (user_id,))
        config_data = cursor.fetchone()

        

        # Verifica se algum dado foi retornado
        if config_data:
            # Extrai o JSON completo
            config_json = config_data[0]  # `config_data[0]` contém o JSON do campo `config`

            # Acessa o valor de "balance_type" dentro de "iq_bot"
            balance_type = config_json.get("iq_bot", {}).get("balance_type")
            amount = config_json.get("iq_bot", {}).get("amount")
            stop_win = config_json.get("iq_bot", {}).get("stop_win")
            stop_loss = config_json.get("iq_bot", {}).get("stop_loss")
            gale = int(config_json.get("iq_bot", {}).get("gale"))
            await_loss = int(config_json.get("iq_bot", {}).get("await_loss"))
            max_signals = config_json.get("iq_bot", {}).get("max_signals")
            concurrent = int(config_json.get("iq_bot", {}).get("concurrent"))

        cursor.execute("SELECT balance FROM daily_results WHERE user_id = %s AND balance_type = %s", (user_id, balance_type))
        balance = cursor.fetchone()    

        profit = get_user_totals(user_id, balance_type)

        if not user_id:
            return jsonify({"error": "user_id é necessário"}), 400
        
        strategy = []
        if await_loss == 1:
            strategy.append("Após Loss")
        if gale > 0:
            strategy.append(f"Gale {gale}")   
        if concurrent == 1:
            strategy.append("Simultâneos")

        # Junta os itens com uma barra "/"
        strategy_text = " / ".join(strategy)

        # Verifica se o user_id está presente no dicionário ping_status
        if user_id in ping_status:
            # Retorna as variáveis solicitadas, todas com valor 1
            return jsonify({
                'ping_status': ping_status[user_id],
                'balance_type': balance_type,
                'bot_amount': amount,
                'bot_profit': profit,
                'bot_balance': balance,
                'bot_stop_win': stop_win,
                'bot_stop_loss': stop_loss,
                'bot_strategy': strategy_text
            }), 200
        else:
            # Se não encontrado, retorna 'inactive' e demais valores como 1
            return jsonify({
                'ping_status': 'inactive',
                'balance_type': balance_type,
                'bot_amount': amount,
                'bot_profit': profit,
                'bot_balance': balance,
                'bot_stop_win': stop_win,
                'bot_stop_loss': stop_loss,
                'bot_strategy': strategy_text
            }), 200
    except Exception as e:
        print(f"Erro ao consultar status do bot: {e}") 
        return jsonify({"error": f"Erro ao consultar sinais pendentes: {str(e)}"}), 500


@app.route('/api/get_pending_signals', methods=['POST'])
def get_pending_signals():
    try:
        data = request.json
        user_id = data.get("user_id")
        if not user_id:
            return jsonify({"error": "user_id é necessário"}), 400

        # Atualiza o status de "ping" para o user_id
        ping_status[user_id] = {"status": "active", "last_ping": datetime.now()}

        # Função para converter objetos datetime para string
        def datetime_converter(obj):
            if isinstance(obj, datetime):
                return obj.strftime('%d/%m/%y - %H:%M:%S')  # Formato brasileiro
            raise TypeError("Type not serializable")

        def event_stream():
            print(f"Cliente {user_id} conectado, status alterado para 'active'.")
            while True:
                try:
                    # Atualiza o ping_status para o usuário atual
                    ping_status[user_id] = {"status": "active", "last_ping": datetime.now()}
                    # Busca sinais para o usuário
                    signals = get_signals_for_user(user_id)
                    # Gera o evento SSE com ping_status e signals
                    yield f"data: {json.dumps({'ping_status': ping_status[user_id], 'signals': signals}, default=datetime_converter)}\n\n"
                    time.sleep(5)  # Intervalo entre os eventos SSE
                except Exception as e:
                    print(f"Erro ao consultar sinais pendentes: {e}")
                    break  # Sai do loop em caso de erro

        @stream_with_context
        def streaming_response():
            try:
                yield from event_stream()
            except GeneratorExit:
                # Marcar o cliente como inativo ao desconectar
                ping_status[user_id] = {"status": "inactive", "last_ping": datetime.now()}
                print(f"Cliente {user_id} desconectado, status alterado para 'inactive'.")

        return Response(streaming_response(), content_type="text/event-stream")

    except Exception as e:
        print(f"Erro ao processar requisição: {e}")
        return jsonify({"error": f"Erro ao processar requisição: {str(e)}"}), 500


@app.route('/unschedule_bot_signal', methods=['POST'])
def unschedule_bot_signal():
    # Obter os dados da requisição
    data = request.get_json()
    user_id = data.get('user_id')
    signal_id = data.get('signal_id')

    if not user_id or not signal_id:
        return jsonify({"success": False, "message": "user_id e signal_id são necessários!"}), 400

    try:
        # Estabelecer a conexão com o banco de dados
        cursor = conn.cursor()

        # Buscar o sinal na tabela schedule_signals
        cursor.execute(
            "SELECT * FROM scheduled_signals WHERE id = %s AND user_id = %s",
            (signal_id, user_id)
        )
        signal = cursor.fetchone()

        # Verificar se o sinal existe
        if not signal:
            return jsonify({"success": False, "message": "Sinal não encontrado ou usuário não autorizado!"}), 404

        # Atualizar o status do sinal para 'canceled'
        cursor.execute(
            "UPDATE scheduled_signals SET status = 'canceled' WHERE id = %s AND user_id = %s",
            (signal_id, user_id)
        )

        # Commit para salvar as mudanças
        conn.commit()


        return jsonify({"success": True, "message": "Sinal desagendado com sucesso!"}), 200

    except Exception as e:
        # Em caso de erro, desfaz a transação e retorna erro
        print(e)
        if conn:
            conn.rollback()
        return jsonify({"success": False, "message": f"Erro ao desagendar o sinal: {str(e)}"}), 500
        


if __name__ == "__main__":
    print(product_free)
    connect_to_database()
    update_events()
    scheduler = BackgroundScheduler()
    scheduler.add_job(update_events, IntervalTrigger(hours=1))
    scheduler.start()
    serve(app, host='0.0.0.0', port=8000, threads=16)

def create_app():
    # Retorne o aplicativo Flask
    return app