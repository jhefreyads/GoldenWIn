import json
import cloudscraper
from datetime import datetime, timedelta
import arrow
from bs4 import BeautifulSoup
import pytz

def get_forex_factory_events():
    """
    Função para obter as notícias do calendário econômico a partir de um web scraping e tratar o HTML
    :return: Lista de dicionários contendo as informações das notícias
    """
    url = 'https://br.investing.com/economic-calendar/'
    scraper = cloudscraper.create_scraper()
    response = scraper.get(url)

    if response.status_code != 200:
        print(f'Erro na requisição: {response.status_code}')
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    table = soup.find('table', {'id': 'economicCalendarData'})
    if not table:
        return []

    rows = table.find('tbody').findAll('tr', {'class': 'js-event-item'})
    events = []

    tz = pytz.timezone('America/Sao_Paulo')  # Define o fuso horário UTC-3
    now = datetime.now(tz)  # Hora atual no fuso horário UTC-3
    one_hour_ago = now - timedelta(hours=1)  # Hora de uma hora atrás

    for row in rows:
        try:
            datetime_str = row.attrs['data-event-datetime']
            # Converta o datetime_str para um datetime com informações de fuso horário
            event_datetime = arrow.get(datetime_str, 'YYYY/MM/DD HH:mm:ss').naive
            event_datetime = tz.localize(event_datetime)

            # Filtrar eventos que ocorreram há mais de uma hora
            if event_datetime < one_hour_ago:
                continue

            event_country = row.find('td', {'class': 'flagCur'}).find('span')['title'].strip()
            event_currency = row.find('td', {'class': 'flagCur'}).text.strip()
            event_impact = len(row.find('td', {'class': 'sentiment'}).findAll('i', {'class': 'grayFullBullishIcon'}))
            event_link = f"https://br.investing.com{row.find('td', {'class': 'event'}).find('a')['href']}"
            event_title = row.find('td', {'class': 'event'}).find('a').text.strip()

            event_info = {
                'datetime': event_datetime.strftime('%Y-%m-%d %H:%M:%S'),
                'country': event_country,
                'currency': event_currency,
                'impact': event_impact,
                'link': event_link,
                'title': event_title
            }
            events.append(event_info)
        except Exception as e:
            print(f"Erro ao processar evento: {e}")
            continue

    # Ordenar eventos por data (maior para menor) e depois por horário (menor para maior)
    events.sort(key=lambda x: (x['datetime'].split()[0], x['datetime'].split()[1]))

    return events


def update_events():
    events_data = get_forex_factory_events()
    if events_data:
        try:
            # Primeiro, tenta gravar com UTF-8 normalmente
            with open('json/events.json', 'w', encoding='utf-8') as f:
                json.dump(events_data, f, separators=(',', ':'), ensure_ascii=False)  # Remover espaços desnecessários
        except UnicodeEncodeError:
            try:
                # Se falhar com UTF-8, tenta gravar com Latin-1
                with open('json/events.json', 'w', encoding='latin-1') as f:
                    json.dump(events_data, f, separators=(',', ':'), ensure_ascii=False)
            except UnicodeEncodeError:
                # Se falhar novamente, grava ignorando caracteres inválidos
                with open('json/events.json', 'w', encoding='utf-8', errors='ignore') as f:
                    json.dump(events_data, f, separators=(',', ':'), ensure_ascii=False)
        
        print("Eventos Forex atualizados e salvos em events.json")



def check_news_for_symbol(symbol, time):
    try:
        # Carregar eventos do arquivo JSON
        with open('json/events.json', 'r', encoding='utf-8') as f:
            events = json.load(f)
        
        # Se não houver eventos, retorna None
        if not events:
            return None

        currency1, currency2 = symbol[:3], symbol[3:]
        tz = pytz.timezone('America/Sao_Paulo')  # Define o fuso horário UTC-3
        event_time = datetime.strptime(time, '%Y-%m-%d %H:%M:%S')
        event_time = tz.localize(event_time)  # Localizar o datetime do evento

        for event in events:
            event_date_str = event.get('datetime', 'N/A')
            impact = event.get('impact', 'N/A')
            
            if event_date_str != 'N/A' and impact in [2, 3]:
                event_date = datetime.strptime(event_date_str, '%Y-%m-%d %H:%M:%S')
                event_date = tz.localize(event_date)  # Localizar o datetime do evento

                # Ajustar o período com base no impacto
                if impact == 1:
                    start_time = event_date - timedelta(minutes=15)
                    end_time = event_date + timedelta(minutes=15)
                elif impact == 2:
                    start_time = event_date - timedelta(minutes=30)
                    end_time = event_date + timedelta(minutes=30)
                elif impact == 3:
                    start_time = event_date - timedelta(minutes=45)
                    end_time = event_date + timedelta(minutes=45)
                
                # Verificar se o evento está dentro do intervalo
                if start_time <= event_time <= end_time:
                    if currency1 in event.get('currency', '') or currency2 in event.get('currency', ''):
                        event_info = {
                            'datetime': event_date_str,
                            'currency': event.get('currency', 'N/A'),
                            'country': event.get('country', 'N/A'),
                            'title': event.get('title', 'N/A'),
                            'impact': impact,
                            'link': event.get('link', 'N/A')
                        }
                        return event_info
        return None
    except Exception as e:
        print(f'Erro ao processar os dados: {e}')
        return None
    
if __name__ == "__main__":
    print(check_news_for_symbol('EURUSD', '2024-08-12 09:45:00'))
    update_events()
