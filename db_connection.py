import configparser
import psycopg2
from psycopg2 import sql
from sqlalchemy import create_engine
import threading
import time
from threading import Lock
import urllib.parse



# Variáveis globais para armazenar a conexão e a engine
_connection = None
_engine = None
_lock = threading.Lock()
# Configurações para a quantidade de tentativas
MAX_RETRIES = 5
RETRY_DELAY = 2  # Segundos entre cada tentativa

def get_connection():
    global _connection
    with _lock:
        if _connection is None or _connection.closed:
            # Carregar as configurações do arquivo config.ini
            config = configparser.ConfigParser()
            try:
                config.read('config.ini', encoding='utf-8')  # Adicionando o encoding para evitar problemas de codificação
            except Exception as e:
                print(f"Erro ao ler o arquivo de configuração: {e}")
                return None

            # Obter informações de configuração
            try:
                host = config.get('Database', 'host')
                database = config.get('Database', 'database')
                user = config.get('Database', 'user')
                password = config.get('Database', 'password')
            except configparser.Error as e:
                print(f"Erro ao ler as configurações: {e}")
                return None

            # Estabelecer a conexão
            try:
                _connection = psycopg2.connect(
                    host=host,
                    database=database,
                    user=user,
                    password=password
                )
                print("Conexão com o banco de dados estabelecida")
            except Exception as e:
                print(f"Erro ao conectar ao banco de dados: {e}")
                _connection = None

    return _connection

def execute_query(query, params=None):
    conn = get_connection()
    if conn is None:
        print("Conexão indisponível")
        return None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with conn.cursor() as cursor:
                cursor.execute(query, params)
                result = cursor.fetchall()  # Para SELECT, usar fetchall/fetchone
                conn.commit()  # Confirma a transação se tudo estiver OK
                return result
        except psycopg2.DatabaseError as e:
            print(f"uniqueid {conn.get_backend_pid()}")  # ID da conexão
            print(f"Tentativa {attempt}: Erro ao fazer login {e}")

            # Se houver um erro de transação abortada, fazer rollback
            if "current transaction is aborted" in str(e):
                conn.rollback()  # Corrige o estado da transação
                print(f"Transação abortada, tentando novamente...")
            
            # Se for a última tentativa, levantar a exceção
            if attempt == MAX_RETRIES:
                print("Erro após múltiplas tentativas, abortando operação.")
                raise

            # Espera antes de tentar novamente
            time.sleep(RETRY_DELAY)
        finally:
            if conn:
                conn.close()  # Fecha a conexão no final

    return None

def get_engine():
    global _engine
    with _lock:
        if _engine is None:
            # Carregar as configurações do arquivo config.ini
            config = configparser.ConfigParser()
            try:
                config.read('config.ini', encoding='utf-8')  # Adicionando o encoding para evitar problemas de codificação
            except Exception as e:
                print(f"Erro ao ler o arquivo de configuração: {e}")
                return None

            # Obter informações de configuração
            try:
                host = config.get('Database', 'host')
                database = config.get('Database', 'database')
                user = config.get('Database', 'user')
                password = config.get('Database', 'password')
                port = config.get('Database', 'port')  # Se a porta está definida no config.ini
            except configparser.Error as e:
                print(f"Erro ao ler as configurações: {e}")
                return None

            # Codificar a senha para garantir que caracteres especiais sejam tratados corretamente
            password_encoded = urllib.parse.quote_plus(password)

            # Cria a URL de conexão para o SQLAlchemy
            database_url = f'postgresql+psycopg2://{user}:{password_encoded}@{host}:{port}/{database}'

            # Cria a engine
            try:
                _engine = create_engine(database_url)
                print("Engine do SQLAlchemy criada")
            except Exception as e:
                print(f"Erro ao criar a engine do SQLAlchemy: {e}")
                _engine = None

    return _engine

# Exemplo de uso
if __name__ == "__main__":
    query = "SELECT * FROM tabela_exemplo"
    result = execute_query(query)
    if result:
        print(result)
