import time
from iqoptionapi.stable_api import IQ_Option
from iq_connection import connect_to_iqoption

global Iq
Iq = connect_to_iqoption()

def get_open_assets():
    try:    
        open_asset = Iq.get_all_open_time()
        # Extract only the open assets from 'binary' and 'digital'
        open_assets_list = []
        for market_type in ['digital']:
            if market_type in open_asset:
                for asset_name, details in open_asset[market_type].items():
                    if details['open']:
                        # Remover o '-op' do nome do ativo, se presente
                        asset_name_without_op = asset_name.replace('-op', '')
                        open_assets_list.append(asset_name_without_op)
        return open_assets_list
    except Exception as e:
        return ["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD", "NZDUSD", "EURGBP", "EURJPY", "GBPJPY", "EURAUD", "EURCHF", "GBPCHF", "AUDJPY", "NZDJPY", "AUDNZD", "GBPAUD", "EURUSD-OTC", "GBPUSD-OTC", "USDJPY-OTC", "USDCHF-OTC", "AUDUSD-OTC", "USDCAD-OTC", "NZDUSD-OTC", "EURGBP-OTC", "EURJPY-OTC", "GBPJPY-OTC", "EURAUD-OTC", "EURCHF-OTC", "GBPCHF-OTC", "AUDJPY-OTC", "NZDJPY-OTC", "AUDNZD-OTC", "GBPAUD-OTC"]

def get_payout(asset):
    try:
        if Iq.check_connect():
            # Espera 2 segundos
            payout = Iq.get_digital_payout(asset, seconds=2)
            
            if payout is None:
                return None
            else:
                return payout
        else:
            return None

    except Exception as e:
        print(f"Erro ao obter payout: {e}")
        return None

def get_all_assets():
    try:
        print("Conectado")
        all_asset = Iq.get_all_open_time()
        # Extract only the open assets from 'binary' and 'digital'
        all_assets_list = []
        for market_type in ['binary', 'digital']:
            if market_type in all_asset:
                for asset_name, details in all_asset[market_type].items():
                    all_assets_list.append(asset_name)
        return all_assets_list
    except Exception as e:
        print(f"Erro ao obter dados: {e}")
        return ["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD", "NZDUSD", "EURGBP", "EURJPY", "GBPJPY", "EURAUD", "EURCHF", "GBPCHF", "AUDJPY", "NZDJPY", "AUDNZD", "GBPAUD", "EURUSD-OTC", "GBPUSD-OTC", "USDJPY-OTC", "USDCHF-OTC", "AUDUSD-OTC", "USDCAD-OTC", "NZDUSD-OTC", "EURGBP-OTC", "EURJPY-OTC", "GBPJPY-OTC", "EURAUD-OTC", "EURCHF-OTC", "GBPCHF-OTC", "AUDJPY-OTC", "NZDJPY-OTC", "AUDNZD-OTC", "GBPAUD-OTC"]


def main():
    data = Iq.get_all_init_v2()  # Obter os dados
    digital_data = data.get('binary', {}).get('actives', {})  # Escolher a categoria correta

    # Criar o dicionário no formato desejado, ordenando pelo ID
    actives = dict(sorted(
        {
            asset_info.get('name', f'Unnamed-{asset_id}').replace('front.', ''): int(asset_id)
            for asset_id, asset_info in digital_data.items()
        }.items(),
        key=lambda item: item[1]  # Ordenar pelo valor do ID
    ))

    # Resultado no formato JSON
    import json
    print(json.dumps(actives, indent=4))

if __name__ == "__main__":
    main()
