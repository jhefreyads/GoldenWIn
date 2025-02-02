from datetime import datetime, timedelta
import secrets
import string
import telebot
from telebot import TeleBot, types
from configparser import ConfigParser
from db_connection import get_connection
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import time

# Configuração do bot
config = ConfigParser()
config.read('config.ini')
TOKEN = config.get('Telegram', 'TOKEN')
TOKEN_ALERT = config.get('Telegram', 'TOKEN_ALERT')
admin_chat_id = config.get('Telegram', 'admin_chat_id')

# IDs de chat
CHAT_ID_M1 = int(config.get('Telegram', 'CHAT_ID_M1'))
CHAT_ID_M1_OTC = int(config.get('Telegram', 'CHAT_ID_M1_OTC'))
CHAT_ID_M5 = int(config.get('Telegram', 'CHAT_ID_M5'))
CHAT_ID_M5_OTC = int(config.get('Telegram', 'CHAT_ID_M5_OTC'))
CHAT_ID_M15 = int(config.get('Telegram', 'CHAT_ID_M15'))
CHAT_ID_M15_OTC = int(config.get('Telegram', 'CHAT_ID_M15_OTC'))
CHAT_ID_FREE = int(config.get('Telegram', 'CHAT_ID_FREE'))

# Lista de todos os chats
all_chats = [CHAT_ID_M1, CHAT_ID_M1_OTC, CHAT_ID_M5, CHAT_ID_M5_OTC, CHAT_ID_M15, CHAT_ID_M15_OTC]

# Inicialização do bot do Telegram
bot = telebot.TeleBot(TOKEN)
bot_alert = telebot.TeleBot(TOKEN_ALERT)
bot.remove_webhook()
last_message = {}
invite_links = {}
conn = get_connection()
user_state = {}
VALIDITY_PERIOD = timedelta(minutes=20)


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

def send_message(chat_bot, chat_id, msg):
    connect_to_database() 
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

def get_contacts_by_chat_id(chat_user_id):
    connect_to_database() 
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT phone_number, first_name, last_name FROM contacts WHERE chat_user_id = %s", (chat_user_id,))
            results = cursor.fetchall()  # Retorna todas as linhas correspondentes
            return results
    except Exception as e:
        error = f"Erro ao obter dados do contato: {e}"
        send_message(bot_alert, admin_chat_id, error)
        print(error)

def gerar_chave_aleatoria():
    connect_to_database() 
    try:
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(20))  # Chave com 20 caracteres aleatórios
    except Exception as e:
            error = f"Erro ao chave aleatória: {e}"
            send_message(bot_alert, admin_chat_id, error)
            print(error)

def get_group_name(chat_id):
    connect_to_database() 
    try:
        chat_info = bot.get_chat(chat_id)
        return chat_info.title  # Retorna o nome do grupo
    except Exception as e:
        error = f"Erro ao obter o nome do grupo: {e}"
        send_message(bot_alert, admin_chat_id, error)
        print(error)
        return None

def generate_invite_links(CHAT_IDS):
    connect_to_database() 
    invite_links = {}  # Define o dicionário local para armazenar links de convite
    for chat_id in CHAT_IDS:
        try:
            # Calcular o horário de validade
            valid_until = datetime.now() + VALIDITY_PERIOD
            
            try:
                # Gerar o link de convite
                invite_link_object = bot.create_chat_invite_link(
                    chat_id,
                    member_limit=1,
                    expire_date=valid_until
                )
            except Exception as e:
                error = f"Telegram: Erro ao gerar link de convite para {chat_id}: {e}"
                send_message(bot_alert, admin_chat_id, error)
                print(error)
                invite_links[chat_id] = None
                continue  # Passa para o próximo chat_id se a geração falhar

            # Acessar o link de convite do objeto retornado
            try:
                invite_link = invite_link_object.invite_link
                invite_links[chat_id] = invite_link
            except Exception as e:
                error = f"Telegram: Erro ao acessar link de convite para {chat_id}: {e}"
                send_message(bot_alert, admin_chat_id, error)
                print(error)
                invite_links[chat_id] = None

        except Exception as e:
            error = f"Telegram: Erro inesperado ao processar {chat_id}: {e}"
            send_message(bot_alert, admin_chat_id, error)
            print(error)
            invite_links[chat_id] = None

    # Retorna o dicionário de links de convite
    return invite_links

def change_phone(user, phone):
    connect_to_database() 
    try:
        connect_to_database()
        conn = get_connection()
        cursor = conn.cursor()

        # Verifica se o telefone já existe
        cursor.execute("""
            SELECT phone
            FROM users
            WHERE phone = %s
        """, (phone,))
        existing_phone = cursor.fetchone()
        
        if existing_phone:
            print(f'Número de telefone já existente: {existing_phone[0]}')
            return  # Você pode optar por retornar ou lançar um erro

        try:
            # Atualiza o número de telefone
            cursor.execute("""
                UPDATE users
                SET phone = %s, cellphone = %s
                WHERE id = %s
            """, (phone, phone, user))
            
            cursor.execute("""
                UPDATE licenses
                SET phone = %s
                WHERE user_id = %s
            """, (phone, user))
            
            conn.commit()
            print("Número de telefone atualizado com sucesso.")

        except Exception as e:
            error = f"Telegram: Erro ao atualizar o número de telefone para o usuário {user}: {e}"
            send_message(bot_alert, admin_chat_id, error)
            print(error)

    except Exception as e:
        error = f"Telegram: Erro ao realizar a mudança de telefone para o usuário {user}: {e}"
        send_message(bot_alert, admin_chat_id, error)
        print(error)

def update_chat_user(user, user_id):
    connect_to_database() 
    try:
        if user is not None and user_id is not None:
            try:
                connect_to_database()
                conn = get_connection()
                cursor = conn.cursor()
                
                try:
                    cursor.execute("""
                        UPDATE users
                        SET tele_user = %s
                        WHERE id = %s
                    """, (user, user_id))
                    conn.commit()
                except Exception as e:
                    error = f"Telegram: Erro ao executar a atualização do chat_id para o usuário {user_id}: {e}"
                    send_message(bot_alert, admin_chat_id, error)
                    print(error)
                    
            except Exception as e:
                error = f"Telegram: Erro ao conectar ao banco de dados ou executar o cursor: {e}"
                send_message(bot_alert, admin_chat_id, error)
                print(error)
                
        else:
            print("Telegram: Nenhum dos parâmetros pode ser None.")

    except Exception as e:
        error = f"Telegram: Erro inesperado ao realizar a atualização do chat_id do usuário {user_id}: {e}"
        send_message(bot_alert, admin_chat_id, error)
        print(error)

def check_licenses(user_chat_id=None, phone=None, user_data=None, key=None, email=None):
    connect_to_database() 
    try:
        connect_to_database()
    except Exception as e:
        error = f"Telegram: Erro ao conectar ao banco de dados: {e}"
        send_message(bot_alert, admin_chat_id, error)
        print(error)

    try:
        # Conectar ao banco de dados
        conn = get_connection()
    except Exception as e:
        error = f"Telegram: Erro ao obter conexão com o banco de dados: {e}"
        send_message(bot_alert, admin_chat_id, error)
        print(error)
        return [], False, None, None

    try:
        user_tele_id = None
        cursor = conn.cursor()
        if user_chat_id is not None:
            user_tele_id = str(user_chat_id)
        
        # Garantir que `key` seja uma string
        key_str = str(key)

        # Buscar usuários e verificar licenças
        cursor.execute("""
            SELECT l.phone, l.expiration_date, u.name, l.key, u.id, l.trade, l.otc, l.crypto, l.free, u.phone, u.cpf, u.email
            FROM users u
            JOIN licenses l ON u.id = l.user_id
            WHERE (RIGHT(l.phone, 11) = RIGHT(%s, 11) OR RIGHT(u.phone, 11) = RIGHT(%s, 11))
            OR u.cpf = %s OR l.key = %s OR u.email = %s OR u.email = %s OR u.tele_user = %s
            ORDER BY l.expiration_date DESC
        """, (phone, phone, user_data, key_str, user_data, email, user_tele_id))
        
        licenses = cursor.fetchall()
    except Exception as e:
        error = f"Telegram: Erro ao buscar licenças: {e}"
        send_message(bot_alert, admin_chat_id, error)
        print(error)
        return [], False, None, None

    # Inicializa a variável user
    user = None

    # Obter a data atual
    now = datetime.now().date()

    # Filtrar licenças válidas e expiradas
    valid_licenses = [lic for lic in licenses if lic[1].date() >= now]
    expired_licenses = [lic for lic in licenses if lic[1].date() < now]

    if licenses:
        user = licenses[0][4]

    # Preparar a mensagem e inicializar variáveis para permissões de chat
    result = []
    user_chats = {}
    trade, otc, crypto, free = False, False, False, False

    # Verifica se há licenças válidas
    if valid_licenses:
        # Obter o nome e telefone do primeiro item de licenças válidas
        try:
            _, _, user_name, _, _, _, _, _, _, user_phone, user_cpf, user_mail = valid_licenses[0]
            result.append(f"Nome: {user_name}\nCPF: {user_cpf}\nTelefone: {user_phone}\nEmail: {user_mail}\n")
        except Exception as e:
            error = f"Telegram: Erro ao processar licenças válidas: {e}"
            send_message(bot_alert, admin_chat_id, error)
            print(error)

        for license in valid_licenses:
            try:
                _, expiration_date, _, key, license_user, trade_license, otc_license, crypto_license, free_license, _, _, _ = license

                # Acumula permissões
                trade = trade or trade_license == 1
                otc = otc or otc_license == 1
                crypto = crypto or crypto_license == 1
                free = free or free_license == 1

                if user_chat_id is not None:
                    update_chat_user(user_chat_id, license_user)

                # Define o tipo de licença para exibição
                license_types = []
                if trade_license == 1:
                    license_types.append("Mercado")
                if otc_license == 1:
                    license_types.append("OTC")
                if free_license == 1:
                    license_types.append("Free")

                license_type = " / ".join(license_types)
                formatted_date = expiration_date.strftime('%d/%m/%Y')

                result.append(f"Licença Válida\nCódigo: {key}\nTipo da licença: {license_type}\nData de vencimento: {formatted_date}\n")
            except Exception as e:
                error = f"Telegram: Erro ao processar licença: {e}"
                send_message(bot_alert, admin_chat_id, error)
                print(error)

        # Define os chats com base em todas as licenças acumuladas
        chat_ids = []
        if free:
            chat_ids.extend([CHAT_ID_M1, CHAT_ID_M5, CHAT_ID_M15])
            chat_ids.extend([CHAT_ID_M1_OTC, CHAT_ID_M5_OTC, CHAT_ID_M15_OTC])
        else:
            if trade:
                chat_ids.extend([CHAT_ID_M1, CHAT_ID_M5, CHAT_ID_M15])
            if otc:
                chat_ids.extend([CHAT_ID_M1_OTC, CHAT_ID_M5_OTC, CHAT_ID_M15_OTC])

        user_chats[license_user] = chat_ids

    # Verificar se há licenças expiradas
    if expired_licenses:
        result.append("\nLicenças expiradas:")
        for license in expired_licenses:
            try:
                phone, expiration_date, name, key, _, *_ = license
                formatted_date = expiration_date.strftime('%d/%m/%Y')
                result.append(f"Nome: {name}\nTelefone: {phone}\nCódigo: {key}\nData de vencimento: {formatted_date}\n")
            except Exception as e:
                error = f"Telegram: Erro ao processar licença expirada: {e}"
                send_message(bot_alert, admin_chat_id, error)
                print(error)

    # Se nenhuma licença válida foi encontrada, retorna mensagem de expiração
    if not valid_licenses:
        result.append("Não encontrei nenhum licença válida, selecione uma das opções abaixo")
        return result, False, [], user

    return result, True, user_chats.get(user, []), user

def add_license(user_id, free, forex, otc, crypto, id_usuario_criacao, prazo):
    connect_to_database() 
    # Conexão com o banco de dados PostgreSQL
    try:
        connect_to_database()
        cursor = conn.cursor()
    except Exception as e:
        error = f"Telegram: Erro ao conectar ao banco de dados: {e}"
        send_message(bot_alert, admin_chat_id, error)
        print(error)
        return False

    try:
        # Calcular a data de expiração baseada na data de pagamento e no prazo (em dias)
        data_pagamento = datetime.now()

        # Adiciona o prazo em dias para calcular a data de expiração
        data_expiracao = data_pagamento + timedelta(days=prazo)

        # Gerar uma chave aleatória
        chave = gerar_chave_aleatoria()

        # Inserir os dados na tabela `Licenses`
        try:
            cursor.execute(""" 
                INSERT INTO Licenses (user_id, key, payment_date, expiration_date, create_user, trade, otc, crypto, free)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (user_id, chave, data_pagamento, data_expiracao, id_usuario_criacao, forex, otc, crypto, free))
        except Exception as e:
            error = f"Telegram: Erro ao inserir dados na tabela Licenses: {e}"
            send_message(bot_alert, admin_chat_id, error)
            print(error)
            conn.rollback()  # Reverter transações em caso de erro
            return False
        
        # Commit para salvar as alterações no banco de dados
        try:
            conn.commit()
        except Exception as e:
            error = f"Telegram: Erro ao realizar commit após inserir licença: {e}"
            send_message(bot_alert, admin_chat_id, error)
            print(error)
            conn.rollback()  # Reverter transações em caso de erro
            return False
        
        return chave

    except Exception as e:
        error = f"Telegram: Erro ao adicionar licença: {e}"
        send_message(bot_alert, admin_chat_id, error)
        print(error)
        conn.rollback()  # Reverter transações em caso de erro
        return False
    finally:
        # Certifique-se de fechar o cursor e a conexão, se estiverem abertos
        try:
            cursor.close()
            conn.close()
        except Exception as e:
            error = f"Telegram: Erro ao fechar cursor ou conexão: {e}"
            send_message(bot_alert, admin_chat_id, error)
            print(error)

def create_free_license(name, phone, cpf, email=None):
    connect_to_database() 
    try:
        connect_to_database()
        cursor = conn.cursor()
    except Exception as e:
        error = f"Telegram: Erro ao conectar ao banco de dados: {e}"
        send_message(bot_alert, admin_chat_id, error)
        print(error)
        return False

    try:
        # Verifica se o CPF ou telefone já existe no banco de dados
        try:
            cursor.execute('SELECT id, phone, cpf, email FROM users WHERE cpf = %s OR RIGHT(phone, 11) = RIGHT(%s, 11) OR RIGHT(cellphone, 11) = RIGHT(%s, 11) OR email = %s', (cpf, phone, phone, email))
            existing_user = cursor.fetchone()
        except Exception as e:
            error = f"Telegram: Erro ao verificar usuário existente: {e}"
            send_message(bot_alert, admin_chat_id, error)
            print(error)
            return False

        if existing_user:
            # Se o usuário já existe, adiciona uma licença a esse usuário
            user_id, existing_phone, existing_cpf, existing_email = existing_user
            try:
                key = add_license(user_id, 1, 0, 0, 0, 8, 2)
            except Exception as e:
                error = f"Telegram: Erro ao adicionar licença para usuário existente: {e}"
                send_message(bot_alert, admin_chat_id, error)
                print(error)
                return False
            return key
        else:
            # Insere um novo usuário no banco de dados com tipo 'user'
            try:
                cursor.execute('INSERT INTO users (name, cpf, phone, cellphone, type, email) VALUES (%s, %s, %s, %s, %s, %s)',
                               (name, cpf, phone, phone, 'user', email))
                conn.commit()
            except Exception as e:
                error = f"Telegram: Erro ao inserir novo usuário: {e}"
                send_message(bot_alert, admin_chat_id, error)
                print(error)
                return False

            # Seleciona o novo usuário criado
            try:
                cursor.execute('SELECT id, phone, cpf, email FROM users WHERE cpf = %s or email = %s', (cpf, email))
                new_user = cursor.fetchone()
                user_id, existing_phone, existing_cpf, existing_email = new_user
            except Exception as e:
                error = f"Telegram: Erro ao selecionar novo usuário: {e}"
                send_message(bot_alert, admin_chat_id, error)
                print(error)
                return False

            # Adiciona uma licença para o novo usuário
            try:
                key = add_license(user_id, 1, 0, 0, 0, 8, 2)
                return key
            except Exception as e:
                error = f"Telegram: Erro ao adicionar licença para novo usuário: {e}"
                send_message(bot_alert, admin_chat_id, error)
                print(error)
                return False
    except Exception as e:
        error = f"Telegram: Erro ao gerar licença grátis: {e}"
        send_message(bot_alert, admin_chat_id, error)
        print(error)
        return False
    finally:
        # Certifique-se de fechar o cursor e a conexão, se estiverem abertos
        try:
            cursor.close()
        except Exception as e:
            error = f"Telegram: Erro ao fechar cursor ou conexão: {e}"
            send_message(bot_alert, admin_chat_id, error)
            print(error)

def remove_users():
    connect_to_database() 
    try:
        conn = get_connection()
        cursor = conn.cursor()

        user_chats = {}
        user_flags = {}
        removed_users = set()  # Conjunto para rastrear usuários removidos
        already_removed = set()  # Conjunto para rastrear remoções já feitas

        try:
            cursor.execute("""
                SELECT l.expiration_date, u.tele_user, l.trade, l.otc, l.crypto, l.free
                FROM users u
                JOIN licenses l ON u.id = l.user_id
                ORDER BY l.expiration_date DESC
            """)
            licenses_users = cursor.fetchall()
        except Exception as e:
            error = f"telegram: Erro ao executar a consulta para buscar usuários e licenças: {e}"
            send_message(bot_alert, admin_chat_id, error)
            print(error)
            return

        now = datetime.now().date()

        for license in licenses_users:
            expiration_date, tele_user, trade, otc, crypto, free = license
            
            if not tele_user or not tele_user.isdigit() or int(tele_user) <= 0:
                continue  # Ignora IDs inválidos


            if tele_user not in user_flags:
                user_flags[tele_user] = {'trade': 0, 'otc': 0, 'crypto': 0, 'free': 0}

            # Verifica se a licença é válida
            if expiration_date.date() >= now:
                if free == 1:
                    user_flags[tele_user]['free'] = 1 
                if trade == 1:
                    user_flags[tele_user]['trade'] = 1
                if otc == 1:
                    user_flags[tele_user]['otc'] = 1
                if crypto == 1:
                    user_flags[tele_user]['crypto'] = 1
            else:
                # Licença expirada: adiciona ao conjunto de removidos
                removed_users.add(tele_user)

        # Define os chats permitidos
        for tele_user, flags in user_flags.items():
            chat_ids = []

            if flags['free'] == 1:
                chat_ids.extend([CHAT_ID_M1, CHAT_ID_M5, CHAT_ID_M15, CHAT_ID_M1_OTC, CHAT_ID_M5_OTC, CHAT_ID_M15_OTC])

            if flags['trade'] == 1:
                chat_ids.extend([CHAT_ID_M1, CHAT_ID_M5, CHAT_ID_M15])

            if flags['otc'] == 1:
                chat_ids.extend([CHAT_ID_M1_OTC, CHAT_ID_M5_OTC, CHAT_ID_M15_OTC])

            if chat_ids:
                user_chats[tele_user] = chat_ids

        # Remover usuários sem licença válida
        for tele_user in removed_users:
            for chat_id in all_chats:
                try:
                    if tele_user is None:
                        continue  # Ignora IDs inválidos

                    # Verifica se o usuário está no chat
                    chat_member = bot.get_chat_member(chat_id, tele_user)

                    if chat_member.status in ['creator', 'administrator']:
                        continue  # Não remover donos ou administradores

                    if chat_member.status not in ['left', 'kicked']:  # Verifica se o usuário não saiu ou foi removido
                        # Verifica se o usuário já foi removido deste chat
                        if (tele_user, chat_id) not in already_removed:
                            bot.kick_chat_member(chat_id, tele_user)
                            bot.unban_chat_member(chat_id, tele_user)
                            print(f"Usuário {tele_user} removido do chat {chat_id}.")
                            already_removed.add((tele_user, chat_id))  # Marca como removido
                except Exception as e:
                    error = f"telegram: Erro ao tentar remover usuário {tele_user} do chat {chat_id}: {e}"
                    send_message(bot_alert, admin_chat_id, error)
                    print(error)

        # Gerenciar usuários com licenças válidas mas sem permissão para chats específicos
        for tele_user, allowed_chats in user_chats.items():
            for chat_id in all_chats:
                if chat_id not in allowed_chats:
                    try:
                        chat_member = bot.get_chat_member(chat_id, tele_user)

                        # Verifica se o usuário está no chat
                        if chat_member.status in ['creator', 'administrator']:
                            continue  # Não remover donos ou administradores

                        if chat_member.status not in ['left', 'kicked']:  # Verifica se o usuário não saiu ou foi removido
                            # Verifica se o usuário já foi removido deste chat
                            if (tele_user, chat_id) not in already_removed:
                                bot.kick_chat_member(chat_id, tele_user)
                                bot.unban_chat_member(chat_id, tele_user)
                                print(f"Usuário {tele_user} removido do chat {chat_id} por falta de permissão.")
                                already_removed.add((tele_user, chat_id))  # Marca como removido
                    except Exception as e:
                        error = f"telegram: Erro ao verificar/remover usuário {tele_user} do chat {chat_id}: {e}"
                        send_message(bot_alert, admin_chat_id, error)
                        print(error)

    except Exception as e:
        error = f"telegram: Erro ao remover usuário do grupo: {e}"
        send_message(bot_alert, admin_chat_id, error)
        print(error)

def create_user_db(name, type, cellphone, chat_user_id, cpf=None, email=None, phone=None):
    cursor = conn.cursor()
    chat_user_id = None
    # Verificar se o usuário já existe
    cursor.execute("SELECT id FROM users WHERE email = %s OR cpf = %s OR tele_user = %s OR cellphone = %s", (email, cpf, chat_user_id, cellphone))
    user = cursor.fetchone()
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
    cursor.execute("SELECT id, name, cellphone FROM users WHERE cellphone = %s OR tele_user = %s", (cellphone, chat_user_id))
    user_created = cursor.fetchone()
    id, name, phone = user_created
    return id, name, phone


##################################################################
######################### BOTÕES DE AÇÃO #########################
##################################################################
access_groups_button = types.InlineKeyboardButton(text="Acessar Grupos", callback_data="access_groups")
free_channel_button =  types.InlineKeyboardButton(text="GRUPO FREE", url="https://t.me/goldenwintrade")
get_free_license_button = types.InlineKeyboardButton(text="Teste grátis", callback_data="free_license")
buy_new_license_button = types.InlineKeyboardButton(text="Comprar Nova Licença", url="https://goldenwin.com.br/#assinaturas")
support_button = types.InlineKeyboardButton(text="Suporte Humano", url="https://t.me/GoldenWinSuporte")
send_code_button = types.InlineKeyboardButton(text="Enviar código da licença", callback_data="send_code")
license_status_button = types.InlineKeyboardButton(text="Licenças", callback_data="license_status")
return_button = types.InlineKeyboardButton(text="Voltar", callback_data="return_to_main")
##################################################################
##################################################################
##################################################################

# Manipulador de mensagens
@bot.message_handler(func=lambda message: message.chat.type == 'private')
def handle_message(message):
    connect_to_database() 
    phone = None
    name = None
    user_id = None
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    chat_user_id = message.chat.id
    str_chat_user_id = str(chat_user_id)

    try:                          
        # Verifica se o chat_id ou telefone já existem na tabela users
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT 
                    COALESCE(u.id, c.id) AS user_id, 
                    COALESCE(u.name, c.first_name) AS name, 
                    COALESCE(u.cellphone, c.phone_number) AS phone
                FROM contacts c
                LEFT JOIN users u ON u.cellphone = c.phone_number
                WHERE c.chat_user_id = %s
            """, (str_chat_user_id,))
            
            results = cursor.fetchall()  # Obtemos todas as linhas correspondentes

        if results:
            if len(results) == 1:  # Se houver apenas um usuário
                user_id, name, phone = results[0]
                first_name = name.split()[0]
                keyboard.add(access_groups_button, license_status_button, get_free_license_button, buy_new_license_button, support_button)
                bot.send_message(chat_user_id, f"Olá {first_name}, em que posso ajudar?", reply_markup=keyboard)
            else:  # Caso haja múltiplos usuários              
                for user_id, name, phone in results:
                    first_name = name.split()[0]
                    user_button = types.InlineKeyboardButton(text=name, callback_data=f"user_{user_id}")
                    keyboard.add(user_button)
                
                bot.send_message(chat_user_id, "Olá. Existem mais de um usuários vinculados a esse telefone. Por favor, selecione o usuário que deseja conversar:", reply_markup=keyboard)

        else:
            # Cria um teclado com um botão para compartilhar contato
            keyboard = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
            reg_button = types.KeyboardButton(text="Compartilhar contato", request_contact=True)
            keyboard.add(reg_button)

            # Envia uma mensagem solicitando o compartilhamento de contato
            bot.send_message(chat_user_id, 
                            "Olá, eu sou o Leoh, o chatbot da GoldenWin. Para iniciar o atendimento, por favor, compartilhe seu contato clicando no botão abaixo:", 
                            reply_markup=keyboard)

    except Exception as e:
        keyboard =  types.InlineKeyboardMarkup(row_width=1)
        keyboard.add(support_button, buy_new_license_button, return_button)
        bot.send_message(chat_user_id, f"Não processar a mensagem, por favor, entre em contato com o suporte, ou tente novamente mais tarde.", reply_markup=keyboard)  
        error = f"Erro ao processar mensagem: {e}"
        send_message(bot_alert, admin_chat_id, error)
        print(error)

@bot.message_handler(content_types=['contact'])
def handle_contact(message):
    connect_to_database() 
    contact = message.contact
    chat_user_id = contact.user_id
    phone = contact.phone_number
    first_name = contact.first_name
    last_name = contact.last_name if contact.last_name else None
    username = message.from_user.username
    chat_id = message.chat.id
    name = f"{contact.first_name} {contact.last_name}".strip()
    user_id = None
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    str_chat_user_id = str(chat_user_id)
    try:           
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO contacts (user_id, phone_number, first_name, last_name, username, chat_user_id)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (user_id) DO NOTHING
            """, (chat_user_id, phone, first_name, last_name, username, chat_user_id))
            conn.commit()

            cursor.execute("SELECT id, name, cellphone FROM users WHERE tele_user = %s OR cellphone = %s", (str_chat_user_id, phone))
            results = cursor.fetchall()  # Obtemos todas as linhas correspondentes

        if results:
            if len(results) == 1:  # Se houver apenas um usuário
                user_id, name, phone = results[0]
                first_name = name.split()[0]
                keyboard.add(access_groups_button, license_status_button, get_free_license_button, support_button, buy_new_license_button)
                bot.send_message(chat_user_id, f"Olá {first_name}, em que posso ajudar?", reply_markup=keyboard)
            else:  # Caso haja múltiplos usuários              
                for user_id, name, phone in results:
                    first_name = name.split()[0]
                    user_button = types.InlineKeyboardButton(text=name, callback_data=f"user_{user_id}")
                    keyboard.add(user_button)
                
                bot.send_message(chat_user_id, "Olá. Existem mais de um usuários vinculados a esse telefone. Por favor, selecione o usuário que deseja conversar:", reply_markup=keyboard)

        else:
            first_name = contact.first_name  # Usando first_name do contato
            keyboard.add(free_channel_button, send_code_button, get_free_license_button, support_button, buy_new_license_button, return_button)
            bot.send_message(chat_user_id, f"Olá {first_name}. Não encontrei nenhuma licença cadastrada para esse telefone 😢. Por favor tente uma das opções abaixo.",
                            reply_markup=keyboard)

    except Exception as e:
        keyboard =  types.InlineKeyboardMarkup(row_width=1)
        keyboard.add(support_button, buy_new_license_button, return_button)
        bot.send_message(chat_user_id, f"Não consegui processar a mensagem, por favor, entre em contato com o suporte, ou tente novamente mais tarde.", reply_markup=keyboard)  
        error = f"Telegram: Erro ao receber contato: {e}"
        send_message(bot_alert, admin_chat_id, error)
        print(error)

@bot.callback_query_handler(func=lambda call: True)
def handle_query(call):
    connect_to_database() 
    chat_user_id = call.message.chat.id
    contact = get_contacts_by_chat_id(chat_user_id)
    phone, first_name, last_name = contact[0]
    name = f"{first_name} {last_name}".strip()
    keyboard =  types.InlineKeyboardMarkup(row_width=1)
    if call.data.startswith("user_"):
        try:
            selected_user_id = call.data.split("_")[1]
            # Agora buscamos as informações do usuário selecionado no banco de dados
            with conn.cursor() as cursor:
                cursor.execute("SELECT name, cellphone FROM users WHERE id = %s", (selected_user_id,))
                result = cursor.fetchone()
            if result:
                name, phone = result
                first_name = name.split()[0]
                
                # Remove a mensagem de seleção após a escolha do usuário
                bot.delete_message(chat_user_id, call.message.message_id)
                # Criamos um teclado para o usuário selecionado
                keyboard.add(access_groups_button, license_status_button, get_free_license_button, support_button, buy_new_license_button)
                
                # Enviamos a mensagem personalizada para o usuário selecionado
                bot.send_message(chat_user_id, f"Olá {first_name}, em que posso ajudar?", reply_markup=keyboard)
            else:              
                # Remove a mensagem de seleção após a escolha do usuário
                bot.delete_message(chat_user_id, call.message.message_id)
                # Criamos um teclado para o usuário selecionado
                keyboard.add(support_button, buy_new_license_button, return_button)
                
                # Enviamos a mensagem personalizada para o usuário selecionado
                bot.send_message(chat_user_id, f"Não consegui acessar os dados do usuário, por favor, entre em contato com o suporte, ou tente novamente mais tarde.", reply_markup=keyboard)
        except Exception as e:
            bot.delete_message(chat_user_id, call.message.message_id)
            keyboard.add(support_button, buy_new_license_button, return_button)
            bot.send_message(chat_user_id, f"Não consegui acessar os dados do usuário, por favor, entre em contato com o suporte, ou tente novamente mais tarde.", reply_markup=keyboard)    
            error = f"Telegram: Erro ao receber contato: {e}"
            send_message(bot_alert, admin_chat_id, error)
            print(error)
            bot.answer_callback_query(call.id)

    elif call.data == "return_to_main":
        bot.delete_message(chat_user_id, call.message.message_id)
        handle_message(call.message)      

    elif call.data == "access_groups":
        try:
            bot.delete_message(chat_user_id, call.message.message_id)
            # Envia uma mensagem inicial e guarda o message_id
            message = bot.send_message(chat_user_id, "Validando licença e criando convites...")
            message_id = message.message_id  # Obtendo o message_id da mensagem enviada
            # Verifica as licenças
            licenses, valid_license_exists, CHAT_IDS, user = check_licenses(chat_user_id, phone, None, None)
            if licenses:
                change_phone(user, phone)
                response_text = "\n".join(licenses)
                if valid_license_exists:
                    # Gera os links de convite
                    invite_links = generate_invite_links(CHAT_IDS)  # Use a lista de CHAT_IDS obtida da verificação de licença
                    # Cria o teclado inline com todos os botões de convite
                    invite_keyboard = types.InlineKeyboardMarkup(row_width=1)
                    invite_keyboard.add(free_channel_button)
                    for chat_id, link in invite_links.items():
                        if link:
                            group_name = get_group_name(chat_id)
                            if group_name:
                                invite_button = types.InlineKeyboardButton(text=f"{group_name}", url=link)
                                invite_keyboard.add(invite_button)
                    invite_keyboard.add(return_button)
                    # Edita a mensagem com os links de convite
                    bot.edit_message_text(
                        chat_id=chat_user_id,  # Passando o chat_id
                        message_id=message_id,  # Passando o message_id
                        text="Aqui estão seus convites:",
                        reply_markup=invite_keyboard)

                else:
                    keyboard.add(free_channel_button, get_free_license_button, support_button, buy_new_license_button, return_button)
                    bot.send_message(chat_user_id, "Não encontrei nenhuma licença válida, tente uma das opções abaixo.", reply_markup=keyboard)
                                          
        except Exception as e:
            bot.delete_message(chat_user_id, message_id)
            keyboard =  types.InlineKeyboardMarkup(row_width=1)
            keyboard.add(support_button, buy_new_license_button, return_button)
            bot.send_message(chat_user_id, f"Não consegui processar a solicitação, por favor, entre em contato com o suporte, ou tente novamente mais tarde.", reply_markup=keyboard)  
            error = f"Erro ao enviar convites para o usuário {name} - {chat_user_id}: {e}"
            send_message(bot_alert, admin_chat_id, error)
            print(error)
            bot.answer_callback_query(call.id)

    elif call.data == "license_status":
        try:
            bot.delete_message(chat_user_id, call.message.message_id)
            # Envia uma mensagem inicial e guarda o message_id
            message = bot.send_message(chat_user_id, "Validando licenças...")
            message_id = message.message_id  # Obtendo o message_id da mensagem enviada
            # Verifica as licenças
            licenses, valid_license_exists, CHAT_IDS, user = check_licenses(chat_user_id, phone, None, None)
            if licenses:
                change_phone(user, phone)
                response_text = "\n".join(licenses)
                if valid_license_exists:
                    keyboard =  types.InlineKeyboardMarkup(row_width=1)
                    keyboard.add(access_groups_button, buy_new_license_button, support_button, return_button)
                    # Edita a mensagem com os links de convite
                    bot.edit_message_text(
                        chat_id=chat_user_id,  # Passando o chat_id
                        message_id=message_id,  # Passando o message_id
                        text=f"{response_text}\n\n",
                        reply_markup=keyboard)

                else:
                    keyboard.add(free_channel_button, get_free_license_button, support_button, buy_new_license_button, return_button)
                    bot.edit_message_text(
                        chat_id=chat_user_id,  # Passando o chat_id
                        message_id=message_id,  # Passando o message_id
                        text="Não encontrei nenhuma licença válida, tente uma das opções abaixo.", reply_markup=keyboard)
                    
                                          
        except Exception as e:
            bot.delete_message(chat_user_id, message_id)
            keyboard =  types.InlineKeyboardMarkup(row_width=1)
            keyboard.add(support_button, buy_new_license_button, return_button)
            bot.send_message(chat_user_id, f"Não consegui processar a solicitação, por favor, entre em contato com o suporte, ou tente novamente mais tarde.", reply_markup=keyboard)  
            error = f"Erro ao enviar convites para o usuário {name} - {chat_user_id}: {e}"
            send_message(bot_alert, admin_chat_id, error)
            print(error)
            bot.answer_callback_query(call.id)    

    elif call.data == "send_code":
        try:
            bot.send_message(chat_user_id, "Por favor, envie o código da licença.")
            user_state[chat_user_id] = "waiting_for_license_code"
        
        except Exception as e:
            bot.delete_message(chat_user_id, call.message.message_id)
            keyboard =  types.InlineKeyboardMarkup(row_width=1)
            keyboard.add(support_button, buy_new_license_button, return_button)
            bot.send_message(chat_user_id, f"Não consegui processar a solicitação, por favor, entre em contato com o suporte, ou tente novamente mais tarde.", reply_markup=keyboard)  
            error = f"Telegram: Erro ao enviar mensagem de código: {e}"
            send_message(bot_alert, admin_chat_id, error)
            print(error)    
            bot.answer_callback_query(call.id)

    elif call.data == "buy_license":
        bot.delete_message(chat_user_id, call.message.message_id)
        try:
            bot.send_message(chat_user_id, "Clique aqui para comprar uma nova licença: [Comprar Licença](https://goldenwin.com.br)", parse_mode='Markdown')
        except Exception as e:
            bot.delete_message(chat_user_id, call.message.message_id)
            keyboard =  types.InlineKeyboardMarkup(row_width=1)
            keyboard.add(support_button, buy_new_license_button, return_button)
            bot.send_message(chat_user_id, f"Não consegui processar a solicitação, por favor, entre em contato com o suporte, ou tente novamente mais tarde.", reply_markup=keyboard)  
            error = f"Telegram: Erro ao enviar mensagem de compra de licença: {e}"
            send_message(bot_alert, admin_chat_id, error)
            print(error)
            bot.answer_callback_query(call.id)

    elif call.data == "free_license":
            bot.delete_message(chat_user_id, call.message.message_id)
            try:
                validation_message = bot.send_message(chat_user_id, "Verificando histórico de licenças...")
                cpf = None
                name = None
                email = None
                phone = None
                cursor = conn.cursor()

                chat_user_id_str = str(chat_user_id)

                cursor.execute("""
                    SELECT id, name, cpf, email, cellphone
                    FROM users
                    WHERE tele_user = %s;
                """, (chat_user_id_str,))
                result = cursor.fetchone()
                print(result)
                if result:
                    id, name, cpf, email, phone = result   

                else:
                    cursor.execute("""
                        SELECT first_name, last_name, phone_number
                        FROM contacts
                        WHERE chat_user_id = %s;
                    """, (chat_user_id_str,))
                    contact_user = cursor.fetchone()
                    first_name, last_name, phone = contact_user
                    name = f"{first_name} {last_name}".strip()
                    id, name, phone = create_user_db(name, "Free", phone, chat_user_id)
                try:
                    cursor.execute("""
                        SELECT *
                        FROM licenses
                        WHERE user_id = %s AND free = 1;
                    """, (id,))
                    free_license_tag = cursor.fetchone()

                    if free_license_tag:
                        keyboard.add(buy_new_license_button, support_button, return_button)

                        bot.edit_message_text(
                            chat_id=chat_user_id,
                            message_id=validation_message.message_id,
                            text="Uma licença gratuita já foi utilizada nesse telegram. Por favor, selecione uma das opções abaixo.",
                            reply_markup=keyboard
                        )
                    else:
                        try:
                            print("criando licença")
                            free_key = create_free_license(name, phone, cpf, email)
                            print(free_key)
                            licenses, valid_license_exists, CHAT_IDS, user = check_licenses(chat_user_id, phone, cpf, free_key)

                            if valid_license_exists:
                                response_text = "Licença criada com sucesso!\n" + "\n".join(licenses)
                                invite_links = generate_invite_links(CHAT_IDS)
                                change_phone(user, phone)

                                invite_keyboard = types.InlineKeyboardMarkup(row_width=1)
                                invite_keyboard.add(free_channel_button)
                                for chat_id, link in invite_links.items():
                                    if link:
                                        group_name = get_group_name(chat_id)
                                        if group_name:
                                            invite_button = types.InlineKeyboardButton(text=f"{group_name}", url=link)
                                            invite_keyboard.add(invite_button)
                                invite_keyboard.add(return_button)
                                bot.edit_message_text(
                                    chat_id=chat_user_id,
                                    message_id=validation_message.message_id,
                                    text=f"{response_text}\n\nClique nos botões abaixo para entrar nos nossos grupos:",
                                    reply_markup=invite_keyboard
                                )
                            else:
                                bot.edit_message_text(
                                    chat_id=chat_user_id,
                                    message_id=validation_message.message_id,
                                    text="Ocorreu um erro ao criar a licença. Por favor, tente novamente mais tarde."
                                )
                        except Exception as e:
                            bot.delete_message(chat_user_id, call.message.message_id)
                            keyboard =  types.InlineKeyboardMarkup(row_width=1)
                            keyboard.add(support_button, buy_new_license_button, return_button)
                            bot.send_message(chat_user_id, f"Não consegui processar a solicitação, por favor, entre em contato com o suporte, ou tente novamente mais tarde.", reply_markup=keyboard)  
                            error = f"Telegram: Erro ao criar licença: {e}"
                            send_message(bot_alert, admin_chat_id, error)
                            print(error)
                            bot.answer_callback_query(call.id)
                except Exception as e:
                    bot.delete_message(chat_user_id, call.message.message_id)
                    keyboard =  types.InlineKeyboardMarkup(row_width=1)
                    keyboard.add(support_button, buy_new_license_button, return_button)
                    bot.send_message(chat_user_id, f"Não consegui processar a solicitação, por favor, entre em contato com o suporte, ou tente novamente mais tarde.", reply_markup=keyboard)  
                    error = f"Telegram: Erro ao consultar licença gratuita: {e}"
                    send_message(bot_alert, admin_chat_id, error)
                    print(error)
                    bot.answer_callback_query(call.id)

            except Exception as e:
                bot.delete_message(chat_user_id, call.message.message_id)
                keyboard =  types.InlineKeyboardMarkup(row_width=1)
                keyboard.add(support_button, buy_new_license_button, return_button)
                bot.send_message(chat_user_id, f"Não consegui processar a solicitação, por favor, entre em contato com o suporte, ou tente novamente mais tarde.", reply_markup=keyboard)  
                error = f"Telegram: Erro ao validar licença gratuita: {e}"
                send_message(bot_alert, admin_chat_id, error)
                print(error)
                bot.answer_callback_query(call.id)

    bot.answer_callback_query(call.id)

@bot.message_handler(func=lambda message: user_state.get(message.chat.id) is not None)
def handle_user_input(message):
    connect_to_database() 
    try:
        chat_user_id = message.chat.id
        state = user_state.get(chat_user_id)
        keyboard = types.InlineKeyboardMarkup(row_width=1)
        contact = get_contacts_by_chat_id(chat_user_id)
        phone, first_name, last_name = contact[0]
        
        if state == "waiting_for_license_code":   
            try:
                license_code = message.text
                licenses, valid_license_exists, CHAT_IDS, user = check_licenses(chat_user_id, phone, None, license_code)
                
                if licenses:
                    change_phone(user, phone)
                    response_text = "\n".join(licenses)
                    if valid_license_exists:
                        generate_invite_links(CHAT_IDS)
                        invite_keyboard = types.InlineKeyboardMarkup(row_width=1)
                        invite_keyboard.add(free_channel_button)
                        for chat_id, link in invite_links.items():
                            if link:
                                group_name = get_group_name(chat_id)
                                if group_name:
                                    invite_button = types.InlineKeyboardButton(text=f"{group_name}", url=link)
                                    invite_keyboard.add(invite_button)
                        invite_keyboard.add(return_button)
                        bot.send_message(
                            chat_user_id,
                            f"{response_text}\n\nClique nos botões abaixo para entrar nos nossos grupos:",
                            reply_markup=invite_keyboard
                        )

                else:
                    keyboard.add(free_channel_button, get_free_license_button, support_button, buy_new_license_button)
                    bot.send_message(chat_user_id, "Não encontrei nenhuma licença válida, tente uma das opções abaixo.", reply_markup=keyboard)
                
                
                user_state[chat_user_id] = None

            except Exception as e:
                error = f"Telegram: Erro ao processar código de licença: {e}"
                send_message(bot_alert, admin_chat_id, error)
                print(error)

    except Exception as e:
        keyboard =  types.InlineKeyboardMarkup(row_width=1)
        keyboard.add(support_button, buy_new_license_button, return_button)
        bot.send_message(chat_user_id, f"Não consegui processar a solicitação, por favor, entre em contato com o suporte, ou tente novamente mais tarde.", reply_markup=keyboard)  
        error = f"Telegram: Erro ao receber input do usuário: {e}"
        send_message(bot_alert, admin_chat_id, error)
        print(error)

@bot.message_handler(content_types=['new_chat_members'])
def handle_new_members(message):
    connect_to_database() 
    try:
        if message.chat.type in ['group', 'supergroup'] and message.new_chat_members:
            cur = conn.cursor()
            for new_member in message.new_chat_members:
                chat_id = message.chat.id
                chat_title = message.chat.title
                chat_type = message.chat.type
                first_name = new_member.first_name
                last_name = new_member.last_name or ''
                user_id = new_member.id
                username = new_member.username or ''
                joined_at = datetime.now()

                try:
                    # Verifica se a combinação user_id e chat_id já existe
                    cur.execute("""
                        SELECT COUNT(*) FROM user_info
                        WHERE user_id = %s AND chat_id = %s
                    """, (user_id, chat_id))

                    exists = cur.fetchone()[0] > 0

                    if exists:
                        # Atualiza os dados existentes
                        cur.execute("""
                            UPDATE user_info
                            SET chat_title = %s, chat_type = %s, first_name = %s, last_name = %s, username = %s, joined_at = %s
                            WHERE user_id = %s AND chat_id = %s
                        """, (chat_title, chat_type, first_name, last_name, username, joined_at, user_id, chat_id))
                        print(f"Informações do usuário {user_id} no chat {chat_id} atualizadas.")
                    else:
                        # Insere um novo registro
                        cur.execute("""
                            INSERT INTO user_info (chat_id, chat_title, chat_type, first_name, last_name, user_id, username, joined_at)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """, (chat_id, chat_title, chat_type, first_name, last_name, user_id, username, joined_at))
                        print(f"Informações do novo membro {first_name} {last_name} no chat {chat_id} adicionadas ao banco de dados.")

                    conn.commit()

                except Exception as e:
                    error = f"Telegram: Erro ao processar dados do usuário {first_name} {last_name}: {e}"
                    send_message(bot_alert, admin_chat_id, error)
                    print(error)

    except Exception as e:
        error = f"Telegram: Erro ao processar novo usuário: {e}"
        send_message(bot_alert, admin_chat_id, error)
        print(error)      

def main():
    conn = connect_to_database() 
    scheduler = BackgroundScheduler()
    scheduler.add_job(remove_users, IntervalTrigger(minutes=10))
    scheduler.start()
    bot.polling()

if __name__ == "__main__":
    main()