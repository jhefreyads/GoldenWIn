from iqoptionapi.stable_api import IQ_Option
from configparser import ConfigParser

# Carregar as configurações do arquivo config.ini
config = ConfigParser()
print("Lendo arquivo de configuração...")  # Print para indicar que o arquivo config.ini está sendo lido
config.read('config.ini')

try:
    login = config.get('API', 'iq_login')
    password = config.get('API', 'iq_password')
except Exception as e:
    print(f"Erro ao carregar configurações: {e}")  # Print para capturar erros na leitura do arquivo de configuração


def connect_to_iqoption():
    try:
        print("Iniciando conexão ao IQ Option...")  # Print para indicar que a conexão está sendo iniciada
        Iq = IQ_Option(login, password)

        if not Iq.connect():
            print("Erro ao conectar ao IQ Option. Verifique suas credenciais e a conexão com a internet.")
            return None

        print("Conectado ao IQ Option com sucesso!")  # Print para confirmar que a conexão foi estabelecida
        return Iq
    except Exception as e:
        print(f"Erro ao conectar ao IQ Option: {e}")  # Print para capturar qualquer erro de conexão
        return None


# Chama a função para testar a conexão
Iq = connect_to_iqoption()
if Iq is None:
    print("Conexão falhou.")
else:
    print("Conexão estabelecida com sucesso.")
