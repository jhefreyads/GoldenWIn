import mysql.connector
from mysql.connector import Error
from configparser import ConfigParser
from datetime import datetime, timedelta
import secrets
import string
import tkinter as tk
from tkinter import simpledialog

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

# Função para gerar uma chave aleatória
def gerar_chave_aleatoria():
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(20))  # Chave com 20 caracteres aleatórios

# Função para adicionar uma licença
def adicionar_licenca():
    try:
        # Conexão com o banco de dados MariaDB
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()

        # Abrir uma janela de diálogo para obter os outros dados necessários
        root = tk.Tk()
        root.withdraw()  # Esconder a janela principal

        cpf = simpledialog.askstring("CPF", "Digite o CPF do usuário:")
        if not cpf:
            print("Operação cancelada.")
            return
        
        prazo = simpledialog.askinteger("Prazo", "Digite o prazo da licença em dias:")
        if not prazo:
            print("Operação cancelada.")
            return
        
        id_usuario_criacao = simpledialog.askinteger("ID do Usuário", "Digite o ID do usuário que está criando a licença:")
        if not id_usuario_criacao:
            print("Operação cancelada.")
            return

        # Buscar o ID do usuário na tabela `users` pelo CPF
        cursor.execute("SELECT id FROM users WHERE cpf = %s", (cpf,))
        resultado = cursor.fetchone()
        
        if resultado:
            user_id = resultado[0]
            
            # Data de pagamento é a data atual
            data_pagamento = datetime.now().date()

            # Calcular a data de expiração baseada na data de pagamento e no prazo (em dias)
            data_expiracao = data_pagamento + timedelta(days=min(prazo, 3650))  # Limitar a 10 anos (3650 dias)

            # Gerar uma chave aleatória
            chave = gerar_chave_aleatoria()
            
            # Inserir os dados na tabela `licenses`
            cursor.execute("""
                INSERT INTO licenses (user, `key`, payment_date, expiration_date, type, create_user)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (user_id, chave, data_pagamento, data_expiracao, prazo, id_usuario_criacao))
            
            # Commit para salvar as alterações no banco de dados
            conn.commit()
            print("Licença adicionada com sucesso!")
        
        else:
            print(f"Usuário com CPF {cpf} não encontrado.")

    except mysql.connector.Error as e:
        print(f"Erro ao adicionar licença: {e}")
    
    except ValueError as e:
        print(f"Erro ao converter data: {e}")
    
    except tk.TclError:
        print("Operação cancelada.")

    finally:
        # Fechar a conexão com o banco de dados
        if conn.is_connected():
            cursor.close()
            conn.close()

# Exemplo de uso
adicionar_licenca()
