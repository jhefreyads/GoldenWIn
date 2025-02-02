from db_connection import get_connection, get_engine
import pandas as pd
import psycopg2
import json
import select
from front_bot import update_trading_signals_json, get_all_prices

def connect_to_database():
    global conn
    global engine
    conn = get_connection()
    engine = get_engine()  # Chamar a função get_engine para obter o engine

def listen_for_notifications():
    try:
        connect_to_database()
        conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        
        # Escuta os canais de notificação
        cur.execute("LISTEN trading_signals_update;")
        cur.execute("LISTEN price_changes;")

        print("Aguardando notificações...")

        while True:
            # Verifica se há notificações disponíveis
            if select.select([conn], [], [], 5) == ([], [], []):
                continue
            
            conn.poll()
            while conn.notifies:
                notify = conn.notifies.pop(0)
                channel = notify.channel
                payload = notify.payload

                print(f"Notificação recebida no canal '{channel}': {payload}")

                # Chame get_all_prices para atualizar os preços
                if channel == 'price_changes':
                    get_all_prices()

                # Chame update_trading_signals_json para atualizar os sinais
                if channel == 'trading_signals_update':
                    update_trading_signals_json()

    except Exception as e:
        print(f"Erro ao consultar o banco de dados: {e}")

def main():
    connect_to_database()
    get_all_prices()
    update_trading_signals_json()
    listen_for_notifications()

if __name__ == "__main__":
    main()
