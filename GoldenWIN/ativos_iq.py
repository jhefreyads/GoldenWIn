import time
from iqoptionapi.stable_api import IQ_Option

def get_open_assets():
    Iq = IQ_Option("jhefrey@leoh.store", "Hanna@0502")
    Iq.connect()  # connect to iqoption
    open_asset = Iq.get_all_open_time()
    # Extract only the open assets from 'binary' and 'digital'
    open_assets_list = []
    for market_type in ['binary', 'digital']:
        if market_type in open_asset:
            for asset_name, details in open_asset[market_type].items():
                if details['open']:
                    # Remover o '-op' do nome do ativo, se presente
                    asset_name_without_op = asset_name.replace('-op', '')
                    open_assets_list.append(asset_name_without_op)
    return open_assets_list

def get_payout(asset):
    max_attempts = 20
    attempt = 0
    while attempt < max_attempts:
        try:
            Iq = IQ_Option("jhefrey@leoh.store", "Hanna@0502")
            Iq.connect()
            if Iq.check_connect():
                payout = Iq.get_digital_payout(asset)
                return payout
            else:
                print("Falha na conexão inicial.")
        except Exception as e:
            print(f"Tentativa {attempt+1} falhou: {e}")
            attempt += 1
            time.sleep(1)  # Espera antes de tentar novamente
    
    print(f"Atingido o número máximo de tentativas ({max_attempts}). Não foi possível conectar ao IQ Option.")
    return None


def get_all_assets():
    Iq = IQ_Option("jhefrey@leoh.store", "Hanna@0502")
    Iq.connect()  # connect to iqoption
    print("Conectado")
    all_asset = Iq.get_all_open_time()
    # Extract only the open assets from 'binary' and 'digital'
    all_assets_list = []
    for market_type in ['binary', 'digital']:
        if market_type in all_asset:
            for asset_name, details in all_asset[market_type].items():
                all_assets_list.append(asset_name)
    return all_assets_list



def main():
    all_assets = get_all_assets()
    print(all_assets)

if __name__ == "__main__":
    main()
