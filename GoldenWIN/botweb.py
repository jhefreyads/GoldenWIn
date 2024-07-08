import logging
from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO
import subprocess
import os
import threading
import time
import json
from flask import Flask, request, jsonify, render_template_string
from pywebpush import webpush, WebPushException, Vapid
import pandas as pd
from flask import send_from_directory
from flask import redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
from flask import flash
from googletrans import Translator
from datetime import datetime, timedelta
from calendario import print_events, update_events
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
import MetaTrader5 as mt5
import string
import mysql.connector
from mysql.connector import Error
from configparser import ConfigParser
import asyncio




# Ler as configurações do arquivo config.ini
config = ConfigParser()
config.read('config.ini')

db_config = {
    'host': config.get('database', 'host'),
    'port': config.getint('database', 'port'),
    'database': config.get('database', 'database'),
    'user': config.get('database', 'user'),
    'password': config.get('database', 'password')
}
conn = None
CONFIG_FILE = "config.json"

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

# Inicializando a conexão com o terminal MetaTrader 5
if not mt5.initialize():
    print("initialize() failed")
    mt5.shutdown()



# Configuração básica de logging
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
app.config['SESSION_TYPE'] = 'filesystem'

socketio = SocketIO(app)



# Dicionário para armazenar a posição da última leitura de cada arquivo de log
last_positions = {}

class ScriptRunner:
    def __init__(self, script_name, display_name, log_file):
        self.script_name = script_name
        self.display_name = display_name
        self.log_file = log_file
        self.process = None
        self.is_running = False
        self.restart_interval = 30  # Restart interval in minutes
        self.auto_restart = True  # Whether to auto-restart

    def start_script(self):
        if self.is_running:
            logging.info(f'Script {self.script_name} is already running.')
            return

        logging.info(f'Starting script: {self.script_name}')
        self.is_running = True
        try:
            with open(self.log_file, 'a', encoding='utf-8') as log_file:
                log_file.write(f"{time.ctime()}: Starting script {self.script_name}\n")
            
            self.process = subprocess.Popen(
                ['python', self.script_name],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                encoding='utf-8',  # Specify UTF-8 encoding for subprocess output
                errors='ignore',
                bufsize=1,
                universal_newlines=True
            )
            threading.Thread(target=self.read_output).start()
            if self.auto_restart:
                threading.Timer(self.restart_interval * 60, self.restart_script).start()
        except Exception as e:
            logging.error(f"Error starting script {self.script_name}: {e}")
            self.is_running = False

    def read_output(self):
        if self.process is None:
            return

        try:
            with codecs.open(self.log_file, 'a', encoding='utf-8') as log_file:
                for line in iter(self.process.stdout.readline, ''):
                    if line:
                        log_file.write(line)
                        log_file.flush()
                        socketio.emit(f'log_update_{self.display_name}', {'output': line.strip()}, namespace='/log')
            self.process.stdout.close()
            self.process.stderr.close()
            self.process.wait()
        except AttributeError:
            logging.error(f"{self.script_name}: Process has no stdout or stderr")
        finally:
            self.stop_script()

    def restart_script(self):
        if self.is_running and self.auto_restart:
            logging.info(f'Restarting script: {self.script_name}')
            self.stop_script()
            time.sleep(1)
            self.start_script()

    def stop_script(self):
        if self.is_running:
            logging.info(f'Stopping script: {self.script_name}')
            self.is_running = False
            try:
                with open(self.log_file, 'a', encoding='utf-8') as log_file:
                    log_file.write(f"{time.ctime()}: Stopping script {self.script_name}\n")
            except Exception as e:
                logging.error(f"Error writing stop log for {self.script_name}: {e}")

            if self.process:
                try:
                    self.process.terminate()  # Use terminate() to stop the process on Windows
                except Exception as e:
                    logging.error(f"Error stopping script {self.script_name}: {e}")
                self.process = None

# Dicionário para armazenar os runners dos scripts (exemplo)
script_runners = {
    'ia.py': ScriptRunner('ia.py', 'IA', 'path_to_ia_log'),
    'telegrambot.py': ScriptRunner('telegrambot.py', 'Telegram', 'path_to_telegram_log'),
    'candles.py': ScriptRunner('candles.py', 'MT5', 'path_to_candles_mt5_log'),
    'candles_iq.py': ScriptRunner('candles_iq.py', 'OTC', 'path_to_candles_iq_log')
}

@app.route('/get_logs/<script_name>')
def get_logs(script_name):
    runner = script_runners.get(script_name)
    if runner:
        try:
            log_file = runner.log_file  # Acessando o atributo log_file do objeto runner
            from_position = int(request.args.get('from', 0))  # Obtenha a posição inicial dos logs

            if from_position == 0:
                # Ler os últimos 10 registros do log
                with open(log_file, 'rb') as f:
                    f.seek(0, os.SEEK_END)
                    end_position = f.tell()
                    lines = []
                    buffer_size = 1024
                    buffer = bytearray()
                    while len(lines) < 10 and end_position > 0:
                        start_position = max(end_position - buffer_size, 0)
                        f.seek(start_position)
                        buffer = f.read(end_position - start_position) + buffer
                        lines = buffer.split(b'\n')
                        end_position = start_position
                    logs = [line.decode('utf-8') for line in lines[-10:] if line]
                    new_position = f.tell()
            else:
                # Ler a partir da posição especificada
                with open(log_file, 'r', encoding='utf-8') as f:
                    f.seek(from_position)  # Vá para a posição inicial especificada
                    logs = f.readlines()
                    new_position = f.tell()  # Nova posição após leitura dos logs
            
            return jsonify({
                "status": "success",
                "logs": logs,
                "new_position": new_position
            })
        except UnicodeDecodeError as e:
            logging.error(f"UnicodeDecodeError ao ler o arquivo de log {log_file}: {str(e)}")
            return jsonify({"status": "error", "message": f"UnicodeDecodeError: {str(e)}"}), 500
        except Exception as e:
            logging.error(f"Erro ao ler o arquivo de log {log_file}: {str(e)}")
            return jsonify({"status": "error", "message": str(e)}), 500
    else:
        logging.error(f"Runner não encontrado para o script: {script_name}")
        return jsonify({"status": "error", "message": "Script not found"}), 404
    
# Função para verificar a existência da tabela 'users'
def check_table_users_exists():
    ensure_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_name = 'users';")
    table_exists = cursor.fetchone() is not None   
    return table_exists


# Verificar e criar a tabela 'users' se necessário
if not check_table_users_exists():
    print("A tabela 'users' não existe.")



def is_authenticated():
    if 'user_id' in session:
        user_id = session['user_id']
        ensure_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT l.id FROM users u
            JOIN licences l ON u.licence_id = l.id
            WHERE u.id = ? AND l.venciment > date('now')
        ''', (user_id,))
        licence = cursor.fetchone()
        return licence is not None
    return False

# Função para verificar a existência da tabela 'users'
def check_table_users_exists():
    ensure_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'sua_base_de_dados' AND table_name = 'users';")
    table_exists = cursor.fetchone() is not None
    return table_exists

@app.route('/create_user', methods=['POST'])
def create_user():
    new_name = request.form['new_name']
    new_email = request.form['new_email']
    new_cpf = request.form['new_cpf']
    new_password = request.form['new_password']
    confirm_password = request.form['confirm_password']

    # Verifica se as senhas coincidem
    if new_password != confirm_password:
        flash('As senhas não coincidem. Por favor, digite novamente.')
        return redirect(url_for('login'))
    ensure_connection()
    cursor = conn.cursor()

    # Verifica se o CPF já existe no banco de dados
    cursor.execute('SELECT email, cpf, password FROM users WHERE cpf = %s', (new_cpf,))
    existing_user = cursor.fetchone()

    if existing_user:
        existing_email, existing_cpf, existing_password = existing_user
        if existing_password:
            # Se já houver uma senha cadastrada, não permita o cadastro
            flash('CPF já cadastrado com senha. Por favor, utilize outro CPF.')
        else:
            # Atualiza o registro existente se a senha estiver ausente
            hashed_password = generate_password_hash(new_password)
            cursor.execute('''
                UPDATE users
                SET name = %s, email = %s, password = %s
                WHERE cpf = %s
            ''', (new_name, new_email, hashed_password, new_cpf))
            conn.commit()
            flash('Usuário atualizado com sucesso!', 'success')
    else:
        # Insere um novo usuário no banco de dados com tipo 'user'
        hashed_password = generate_password_hash(new_password)
        cursor.execute('''
                INSERT INTO users (name, email, cpf, password, type)
                VALUES (%s, %s, %s, %s, %s)
                ''', (new_name, new_email, new_cpf, hashed_password, 'user'))
        conn.commit()
        flash('Usuário cadastrado com sucesso!', 'success')

    return redirect(url_for('login'))

@app.route('/create_user_admin', methods=['POST'])
def create_user_admin():
    new_name = request.form['new_name']
    new_email = request.form['new_email']
    new_cpf = request.form['new_cpf']
    new_password = request.form['new_password']
    confirm_password = request.form['confirm_password']

    # Verifica se as senhas coincidem
    if new_password != confirm_password:
        flash('As senhas não coincidem. Por favor, digite novamente.', 'error')
    else:
        ensure_connection()
        cursor = conn.cursor()

        # Verifica se o CPF já existe no banco de dados
        cursor.execute('SELECT email, cpf, password FROM users WHERE cpf = %s', (new_cpf,))
        existing_user = cursor.fetchone()

        if existing_user:
            existing_email, existing_cpf, existing_password = existing_user
            if existing_password:
                # Se já houver uma senha cadastrada, não permita o cadastro
                flash('CPF já cadastrado com senha. Por favor, utilize outro CPF.', 'error')
            else:
                # Atualiza o registro existente se a senha estiver ausente
                hashed_password = generate_password_hash(new_password)
                cursor.execute('''
                UPDATE users
                SET name = %s, email = %s, password = %s
                WHERE cpf = %s
                ''', (new_name, new_email, hashed_password, new_cpf))
                conn.commit()
                flash('Usuário atualizado com sucesso!', 'success')
        else:
            # Insere um novo usuário no banco de dados com tipo 'user'
            hashed_password = generate_password_hash(new_password)
            cursor.execute('''
                INSERT INTO users (name, email, cpf, password, type)
                VALUES (%s, %s, %s, %s, %s)
                ''', (new_name, new_email, new_cpf, hashed_password, 'user'))

            conn.commit()
            flash('Usuário cadastrado com sucesso!', 'success')


    # Retorna vazio, pois não há necessidade de renderizar ou redirecionar
    return '', 204



def get_client_ip():
    return request.remote_addr

@app.route('/verify_mac', methods=['POST'])
def verify_mac():
    try:
        user_id = session.get('user_id')
        if not user_id:
            return redirect(url_for('login'))  # Redireciona para a rota 'login'

        mac = request.json.get('mac')
        client_ip = get_client_ip()
        ensure_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT mac, ip, username FROM users WHERE id = %s', (user_id,))
        result = cursor.fetchone()

        if result:
            stored_mac, stored_ip, user_name = result
            if (stored_mac and stored_mac != mac) or (not stored_mac and stored_ip != client_ip):
                return jsonify({"status": "error", "message": "Sessão inválida. Faça login novamente."}), 401
            else:
                return jsonify({"status": "success", "message": "MAC/IP address verificado com sucesso."})
        else:
            return redirect(url_for('login'))  # Redireciona para a rota 'login' se o usuário não for encontrado

    except:
        return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        mac = request.form.get('mac')  # Supondo que o MAC address é enviado no formulário de login
        client_ip = get_client_ip()
        ensure_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT id, password, type, mac, ip FROM users WHERE email = %s', (email,))
        user = cursor.fetchone()

        if user:
            user_id, stored_password, user_type, stored_mac, stored_ip = user
            if check_password_hash(stored_password, password):
                # Verificar validade da licença
                cursor.execute('SELECT expiration_date FROM licenses WHERE user = %s', (user_id,))
                licenses = cursor.fetchall()
                valid_license = False
                current_date = datetime.now()

                for license in licenses:
                    expiration_date_str = str(license[0])  # Convertendo para string
                    expiration_date = datetime.strptime(expiration_date_str, '%Y-%m-%d')
                    if expiration_date >= current_date:
                        valid_license = True
                        break

                if not valid_license:
                    flash('Licença expirou ou é inválida, contate o suporte.', 'error')
                    return redirect(url_for('login'))

                # Senha correta, verificar se o MAC/IP é diferente
                if (stored_mac and stored_mac != mac) or (not stored_mac and stored_ip != client_ip):
                    # Invalida a sessão anterior
                    session.pop('_flashes', None)
                    flash('Você foi desconectado da sessão anterior.', 'warning')

                # Atualiza o MAC address ou IP address no banco de dados
                if mac:
                    cursor.execute('UPDATE users SET mac = %s, ip = %s WHERE id = %s', (mac, client_ip, user_id))
                else:
                    cursor.execute('UPDATE users SET ip = %s WHERE id = %s', (client_ip, user_id))
                conn.commit()

                # Login bem-sucedido
                flash('Login bem-sucedido!', 'success')
                session['user_id'] = user_id
                session['user_type'] = user_type
                session['mac'] = mac  # Armazena o MAC address na sessão, se disponível
                session['ip'] = client_ip  # Armazena o IP address na sessão


                if user_type == 'admin':
                    session.pop('_flashes', None)
                    return redirect(url_for('indexadmin'))
                if user_type == 'user':
                    session.pop('_flashes', None)
                    return redirect(url_for('index'))
                else:
                    session.pop('_flashes', None)
                    return redirect(url_for('login'))
            else:
                flash('Senha incorreta.', 'error')
        else:
            flash('E-mail não correspondente a um usuário válido.', 'error')



    return render_template('login.html')

@app.route('/')
def index():
    try:
        if 'user_id' in session and session.get('user_type') == 'admin':
            user_id = session['user_id']
            mac = session.get('mac')
            client_ip = session.get('ip')
            ensure_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT mac, ip, name FROM users WHERE id = %s', (user_id,))
            stored_mac, stored_ip, user_name = cursor.fetchone()


            first_name = user_name.split()[0]

            return render_template('indexadmin.html', user_name=first_name, user_id=user_id)
        
        if 'user_id' in session:
            user_id = session['user_id']
            mac = session.get('mac')
            client_ip = session.get('ip')
            ensure_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT mac, ip, name FROM users WHERE id = %s', (user_id,))
            stored_mac, stored_ip, user_name = cursor.fetchone()

            if (stored_mac and stored_mac != mac) or (not stored_mac and stored_ip != client_ip):
                flash('Sessão inválida. Faça login novamente.', 'error')
                return redirect(url_for('logout'))

            first_name = user_name.split()[0]

            
            return render_template('index.html', user_name=first_name)
        else:
            return render_template('login.html')
    except:
        return render_template('login.html')

@app.route('/indexadmin')
def indexadmin():
    if 'user_id' in session and session.get('user_type') == 'admin':
        user_id = session['user_id']
        mac = session.get('mac')
        client_ip = session.get('ip')
        ensure_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT mac, ip, name FROM users WHERE id = %s', (user_id,))
        stored_mac, stored_ip, user_name = cursor.fetchone()

        if (stored_mac and stored_mac != mac) or (not stored_mac and stored_ip != client_ip):
            flash('Sessão inválida. Faça login novamente.', 'error')
            return redirect(url_for('logout'))

        first_name = user_name.split()[0]

        return render_template('indexadmin.html', user_name=first_name, user_id=user_id)
    else:
        return render_template('index.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('user_type', None)
    session.pop('mac', None)
    session.pop('ip', None)
    return redirect(url_for('login'))


def save_config():
    config = {}
    for script_name, runner in script_runners.items():
        config[script_name] = {
            "auto_restart": runner.auto_restart,
            "restart_interval": runner.restart_interval
        }
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f)

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
        for script_name, runner in script_runners.items():
            if script_name in config:
                runner.auto_restart = config[script_name]["auto_restart"]
                runner.restart_interval = config[script_name]["restart_interval"]

@app.route('/start/<script_name>')
def start_script(script_name):
    runner = script_runners.get(script_name)
    if runner and not runner.is_running:
        runner.start_script()
        return jsonify({"status": "started"})
    return jsonify({"status": "error", "message": "Script not found or already running"}), 404

@app.route('/stop/<script_name>')
def stop_script(script_name):
    runner = script_runners.get(script_name)
    if runner and runner.is_running:
        runner.stop_script()
        return jsonify({"status": "stopped"})
    return jsonify({"status": "error", "message": "Script not found or not running"}), 404

@app.route('/status/<script_name>')
def status_script(script_name):
    runner = script_runners.get(script_name)
    if runner:
        if runner.is_running:
            return jsonify({"status": "running"})
        else:
            return jsonify({"status": "stopped"})
    return jsonify({"status": "error", "message": "Script not found"}), 404

@app.route('/events')
def events():
    with open('events.json', 'r') as f:
        events_data = json.load(f)
        events=events_data
    
    return jsonify(events)

    

@app.route('/update_table')
def update_table():
    # Certifique-se de que a conexão com o banco de dados está ativa
    ensure_connection()
    cursor = conn.cursor()
    
    # Query para selecionar os dados do MariaDB
    query = "SELECT * FROM trading_signals WHERE timeframe = 'M5' ORDER BY id DESC LIMIT 1000"

    # Executando a consulta
    cursor.execute(query)

    # Obtendo todos os resultados da consulta
    rows = cursor.fetchall()

    # Obtendo os nomes das colunas a partir do cursor.description
    columns = [col[0] for col in cursor.description]

    # Criando o DataFrame com Pandas
    df = pd.DataFrame(rows, columns=columns)
    
    # Ignore linhas onde a coluna "sent" tem o valor "ignorado"
    df = df.query('sent != "ignorado"')
    
    # Preencha valores nulos com valores apropriados para cada tipo de dado
    for column in df.columns:
        if pd.api.types.is_numeric_dtype(df[column]):
            df[column] = df[column].fillna(0)  # Use 0 ou outro valor apropriado para dados numéricos
        else:
            df[column] = df[column].fillna("")  # Use uma string vazia para dados não numéricos
    
    # Converta Timedelta para string
    for column in df.select_dtypes(include=['timedelta']):
        df[column] = df[column].astype(str)
    
    # Converta o DataFrame para uma lista de dicionários
    signals = df.to_dict(orient='records')
    
    # Feche o cursor
    cursor.close()
    
    return jsonify(signals)
    
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/manifest.json')
def manifest():
    return send_from_directory('.', 'manifest.json')

@app.route('/service-worker.js')
def service_worker():
    return send_from_directory('.', 'service-worker.js')

@app.route('/offline.html')
def offline():
    return send_from_directory('.', 'offline.html')

@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory('static', filename)

@app.route('/icons/<path:filename>')
def icons(filename):
    return send_from_directory('./icons', filename)

@app.route('/static/<path:filename>')
def logo(filename):
    return send_from_directory('static', filename)

@app.route('/scripts/<path:filename>')
def chart(filename):
    return send_from_directory('scripts', filename)

# Caminho para salvar as chaves VAPID
VAPID_KEYS_FILE = 'vapid_keys.json'

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
def gerar_chave_aleatoria():
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(20))  # Chave com 20 caracteres aleatórios

# Função para adicionar uma licença
def adicionar_licenca(cpf, data_pagamento, prazo, id_usuario_criacao):
    # Conexão com o banco de dados SQLite
    ensure_connection()
    cursor = conn.cursor()

    try:
        # Buscar o ID do usuário na tabela `users` pelo CPF
        cursor.execute("SELECT id FROM users WHERE cpf = %s", (cpf,))
        resultado = cursor.fetchone()
        
        if resultado:
            user_id = resultado[0]
            
            # Calcular a data de expiração baseada na data de pagamento e no prazo (em dias)
            data_pagamento = datetime.strptime(data_pagamento, '%Y-%m-%d')
            data_expiracao = data_pagamento + timedelta(days=prazo)
            
            # Gerar uma chave aleatória
            chave = gerar_chave_aleatoria()
            
            # Inserir os dados na tabela `Licenses`
            cursor.execute("""
                INSERT INTO Licenses (user, `key`, payment_date, expiration_date, type, create_user)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (user_id, chave, data_pagamento, data_expiracao, prazo, id_usuario_criacao))

            # Commit para salvar as alterações no banco de dados
            conn.commit()
            return "Licença adicionada com sucesso!"
        else:
            return f"Usuário com CPF {cpf} não encontrado."

    except mysql.connector.Error as e:
        return f"Erro ao adicionar licença: {e}"


# Rota para exibir o formulário HTML
@app.route('/add_license', methods=['GET'])
def add_license_form():
    return render_template_string(open('add_license.html').read())

# Rota para processar o formulário HTML
@app.route('/add_license', methods=['POST'])
def add_license():
    cpf = request.form['cpf']
    data_pagamento = request.form['data_pagamento']
    prazo = int(request.form['prazo'])
    id_usuario_criacao = int(request.form['id_usuario_criacao'])
    
    mensagem = adicionar_licenca(cpf, data_pagamento, prazo, id_usuario_criacao)
    return mensagem

def get_prices(symbol, timeframe, time_str):
    # Convertendo o horário fornecido para um objeto datetime
    time_obj = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
    
    # Adicionando 6 horas ao horário fornecido
    time_obj = time_obj + timedelta(hours=6)

    # Definindo os mapeamentos de timeframe do MetaTrader 5
    timeframe_map = {
        "M1": mt5.TIMEFRAME_M1,
        "M5": mt5.TIMEFRAME_M5,
        "M15": mt5.TIMEFRAME_M15,
        "M30": mt5.TIMEFRAME_M30,
        "H1": mt5.TIMEFRAME_H1,
        "H4": mt5.TIMEFRAME_H4,
        "D1": mt5.TIMEFRAME_D1,
        "W1": mt5.TIMEFRAME_W1,
        "MN1": mt5.TIMEFRAME_MN1
    }

    # Verificando se o timeframe fornecido é válido
    if timeframe not in timeframe_map:
        print(f"Timeframe '{timeframe}' não é válido.")
        mt5.shutdown()
        open_price = 0
        current_price = 0
        return open_price, current_price

    # Verificando se o símbolo está ativo
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        open_price = 0
        current_price = 0
        return open_price, current_price

    if not symbol_info.visible:
        print(f"O símbolo {symbol} não está visível. Tentando ativar.")
        if not mt5.symbol_select(symbol, True):
            open_price = 0
        current_price = 0
        return open_price, current_price

    # Obtendo o histórico de velas
    rates = mt5.copy_rates_from(symbol, timeframe_map[timeframe], time_obj, 1)

    if rates is None or len(rates) == 0:
        open_price = 0
        current_price = 0
        return open_price, current_price

    # Obtendo o preço de abertura da vela
    open_price = rates[0]['open']

    # Obtendo o preço atual do ativo
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        print(f"Não foi possível obter o tick para o símbolo {symbol}.")
        mt5.shutdown()
        open_price = 0
        current_price = 0
        return open_price, current_price

    current_price = tick.bid
    print(symbol, time_str, "Open:", open_price, "Now:", current_price)
    return open_price, current_price

@app.route('/get_prices', methods=['POST'])
def get_prices_route():
    data = request.json
    symbol = data.get('symbol')
    timeframe = data.get('timeframe')
    time_str = data.get('time_str')
    
    if not symbol or not timeframe or not time_str:
        return jsonify({"error": "Parâmetros ausentes"}), 400

    prices = get_prices(symbol, timeframe, time_str)
    if prices is None:
        return jsonify({"error": "Erro ao obter preços"}), 500
    
    open_price, current_price = prices
    return jsonify({"open_price": open_price, "current_price": current_price})


if __name__ == "__main__":
    load_config()
    # Iniciar scripts automaticamente
    
    for runner in script_runners.values():
        runner.start_script()


    # Crie e inicie o agendador
    scheduler = BackgroundScheduler()
    # Agende a função para rodar todos os dias às 00:00 e 07:00
    scheduler.add_job(update_events, IntervalTrigger(hours=1))
    scheduler.start()

    
    socketio.run(app, host='0.0.0.0', port=80, debug=False)

