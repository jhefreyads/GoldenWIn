import requests
from datetime import datetime, timedelta
import pytz
from googletrans import Translator
import json
import os

def get_forex_factory_events():
    url = 'https://nfs.faireconomy.media/ff_calendar_thisweek.json'
    response = requests.get(url)
    
    if response.status_code == 200:
        events = response.json()
        return events
    else:
        print(f'Erro na requisição: {response.status_code}')
        return None
    


def print_events(events):
    events_data = get_forex_factory_events()
    filtered_events = []
    today = datetime.now(pytz.timezone('Etc/GMT+3')).date()  # Data de hoje no fuso horário UTC-3

    translator = Translator()

    for event in events_data:
        if event['impact'] in ['Medium', 'Low', 'High']:
            event_date_str = event.get('date', 'N/A')
            if event_date_str != 'N/A':
                try:
                    utc_minus_3 = pytz.timezone('Etc/GMT+3')
                    # Converter a data e hora do evento para datetime com timezone UTC-4
                    event_datetime = datetime.fromisoformat(event_date_str)
                    utc_minus_4 = pytz.timezone('Etc/GMT+4')
                    localized_event_datetime = utc_minus_4.localize(event_datetime.replace(tzinfo=None))

                    # Converter o horário do evento para UTC-3
                    event_datetime_utc_minus_3 = localized_event_datetime.astimezone(utc_minus_3)
                    
                    # Verificar se a data do evento é hoje
                    if event_datetime_utc_minus_3.date() == today:
                        # Traduzir o título do evento para português
                        title = event.get('title', 'N/A')
                        translated_title = translator.translate(title, dest='pt').text

                        event_info = {
                            'datetime': event_datetime_utc_minus_3.strftime('%H:%M'),
                            'country': event.get('country', 'N/A'),
                            'title': translated_title,
                            'impact': event.get('impact', 'N/A')
                        }
                        filtered_events.append(event_info)
                except ValueError:
                    continue
    print(filtered_events)
    return filtered_events
 
def update_events():
    events_data = get_forex_factory_events()
    if events_data:
        formatted_events = print_events(events_data)
        with open('events.json', 'w') as f:
            json.dump(formatted_events, f)
        print("Eventos Forex atualizados e salvos em events.json")

def check_news_for_symbol(symbol, time):
    try:
        # Dividir o símbolo em duas moedas
        currency1, currency2 = symbol[:3], symbol[3:]
        
        # Converter o datetime fornecido para um datetime consciente do fuso UTC-3
        event_time = datetime.strptime(time, '%Y-%m-%d %H:%M:%S')
        utc_minus_3 = pytz.timezone('Etc/GMT+3')
        event_time = utc_minus_3.localize(event_time)
        
        # Definir o intervalo de 20 minutos
        start_time = event_time - timedelta(minutes=20)
        end_time = event_time + timedelta(minutes=20)
        
        # Buscar eventos
        events = get_forex_factory_events()
        if events is None:
            return None
        
        # Verificar eventos para ambas as moedas
        for event in events:
            if event['impact'] in ['Medium', 'Low', 'High']:
                event_date_str = event.get('date', 'N/A')
                if event_date_str != 'N/A':
                    try:
                        # Converter a data e hora do evento para datetime com timezone UTC-4
                        event_datetime = datetime.fromisoformat(event_date_str)
                        utc_minus_4 = pytz.timezone('Etc/GMT+4')
                        localized_event_datetime = utc_minus_4.localize(event_datetime.replace(tzinfo=None))
                        
                        # Converter o horário do evento para UTC-3
                        event_datetime_utc_minus_3 = localized_event_datetime.astimezone(utc_minus_3)
                        
                        # Verificar se o evento está dentro do intervalo desejado
                        if start_time <= event_datetime_utc_minus_3 <= end_time:
                            # Verificar se a moeda do evento corresponde a uma das moedas do par
                            if currency1 in event.get('country', '') or currency2 in event.get('country', ''):
                                event_info = (
                                    event_datetime_utc_minus_3.strftime('%Y-%m-%d %H:%M:%S'),
                                    event.get('country', 'N/A'),
                                    event.get('title', 'N/A'),
                                    event.get('impact', 'N/A')
                                )
                                return event_info
                    except ValueError:
                        continue
        return None
    except Exception as e:
        print(f'Erro ao processar os dados: {e}')
        return None

if __name__ == "__main__":
    print_events(get_forex_factory_events())