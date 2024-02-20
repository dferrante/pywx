import datetime
import json
import os
import re
import shutil
import sys

import dataset
import requests
from faster_whisper import WhisperModel
from sqlalchemy import Text

from logger import get_logger
from spelling_correct import spelling_correct

log = get_logger('transcribe_alerts')

try:
    config = json.load(open('data/local_config.json', encoding='utf-8'))
    config['pywx_path'] = os.path.dirname(os.path.abspath(__file__))
except ImportError:
    log.error('cant import local_config.py')
    sys.exit()


def get_mp3s():
    log.info('getting mp3s')
    database = dataset.connect(config['alerts_database'])
    event_table = database['scanner']
    if 'original_transcription' not in event_table.columns:
        event_table.create_column('original_transcription', Text)

    for county in ['hunterdon', 'morris', 'warren', 'sussex']:
        mp3s = []
        alerts_url = f'https://dispatchalert.group//includes/js/flat.audio.{county}.js'
        resp = requests.get(alerts_url)
        for raw_line in resp.iter_lines():
            line = raw_line.decode('ascii').strip()
            if 'mp3:' in line:
                mp3s.append(line[6:-1])

        grouped_events = []
        event = []
        last_event_date = None
        group_in_seconds = 30
        for mp3_url in mp3s:
            try:
                parsed_url = re.search(r"https://dispatchalert.net/(?P<county>[^/]+)/(?P<unit>[^/_]+)__?(?P<datetime>[\d_]+).mp3", mp3_url).groupdict()
            except AttributeError:
                continue
            parsed_url['unit'] = ' '.join(parsed_url['unit'].split('-'))
            parsed_url['mp3_url'] = mp3_url
            parsed_url['datetime'] = datetime.datetime.strptime(parsed_url['datetime'], "%Y_%m_%d_%H_%M_%S")

            seconds_since_last_event = (last_event_date - parsed_url['datetime']).total_seconds() if last_event_date else group_in_seconds - 1
            if seconds_since_last_event > group_in_seconds:
                if event:
                    grouped_events.append(event)
                event = [parsed_url]
            else:
                event.append(parsed_url)

            last_event_date = parsed_url['datetime']

        for group in grouped_events:
            event = group[0]
            first_datetime = min([e['datetime'] for e in group])
            responding = ','.join(sorted([e['unit'] for e in group]))

            existing_event = event_table.find_one(county=event['county'], datetime=first_datetime)
            if existing_event:
                if responding != existing_event['responding']:
                    log.info(f'updating {existing_event["mp3_url"]}')
                    event_table.update(dict(responding=responding, id=existing_event['id']), ['id'])
            else:
                log.info(f'inserting {event["mp3_url"]}')
                event_table.insert(dict(county=event['county'], datetime=first_datetime, responding=responding, mp3_url=event['mp3_url'], is_transcribed=False, is_irc_notified=False))


def download_and_transcribe():
    log.info('starting transcriptions')
    database = dataset.connect(config['alerts_database'])
    event_table = database['scanner']

    model = WhisperModel("large-v2", device="cpu", compute_type="int8", download_root="data/whisper")
    for event in event_table.find(is_transcribed=False, order_by=['datetime']):
        if event['datetime'] < (datetime.datetime.now() - datetime.timedelta(days=5)):
            log.warning(f'event {event["id"]} too old, skipping')
            continue

        log.info(f'downloading {event["mp3_url"]}')
        local_filename = '/tmp/temp.mp3'
        with requests.get(event['mp3_url'], stream=True) as r:
            with open(local_filename, 'wb') as f:
                shutil.copyfileobj(r.raw, f)

        log.info(f'transcribing {event["mp3_url"]}')
        segments, _ = model.transcribe(local_filename, beam_size=5, vad_filter=True)
        transcription = []
        for segment in segments:
            transcription.append(segment.text)

        transcription = ' '.join(transcription)
        event_table.update(dict(id=event['id'], transcription=transcription, is_transcribed=True), ['id'])


def parse_transcriptions():
    log.info('parsing transcriptions')
    database = dataset.connect(config['alerts_database'])
    event_table = database['scanner']
    age_to_int = {
        'one': 1,
        'two': 2,
        'three': 3,
        'four': 4,
        'five': 5,
        'six': 6,
        'seven': 7,
        'eight': 8,
        'nine': 9,
        'ten': 10,
    }
    text_ages = '|'.join(age_to_int.keys())

    street_types = [
        'Street', 'Road', 'Lane', 'Drive', 'Avenue', 'Court', 'Blvd', 'Boulevard', 'Highway', 'Circle', 'Way', 'Plaza', 'Hillway',
        'Pass', 'Pike', 'Crestway', 'Place', 'Terrace', 'Ridge', 'Rd', 'Park', 'Run', 'Hills', 'Trail', 'Row', 'St'
    ]
    street_types += [s.lower() for s in street_types]
    street_types = '|'.join(street_types)

    line_breaks = '|'.join(['Repeating', 'Paging', 'Again', 'repeating', 'paging', 'again'])

    genders = r"(?P<gender>male|female|Male|Female)"

    age_regex = re.compile(fr"(?P<age>\d+|{text_ages})(-?ish)?('s)?[\s-]+years?([\s-]+olds?)?")
    month_age_regex = re.compile(fr"(?P<age>\d+|{text_ages})(-?ish)?('s)?[\s-]+months?([\s-]+olds?)?")

    gender_regex = re.compile(rf"years?([\s-]+olds?)?[\s,]+{genders}")

    symptom_regex = re.compile(rf"years?([\s-]+olds?)?[\s,]+{genders}?[\s,]{{,2}}(with a |who |with |that |they |described as (a )?|complaining of|for the )?(?P<symptom>[\w\W]+?)[\s,\.]{{,2}}({line_breaks}|\d+)")
    action_regex = re.compile(rf"(for|For) (an? |the )?({genders}\s)?(?P<symptom>[\w\W]+?)[\s,\.]{{,2}}({line_breaks})")
    gender_action_regex = re.compile(rf"{genders}[\s,\.]{{,2}}(?P<symptom>[\w\W]+?)[\s,\.]{{,2}}({line_breaks})")
    action_no_for_regex = re.compile(fr"({street_types})[\s,]+(?P<symptom>[\w\W]+?)[\s,\.]{{,2}}({line_breaks})")

    city_regex = re.compile(r"(?P<town>(City|Town|city|town) of \w+)")
    town_regex = re.compile(r"(?P<town>(West |East |Glen |High |New )?\w+\s(Borough|Township|Town|City|township|borough))")
    county_regex = re.compile(r"(?P<town>(West |East |Glen |High )?\w+\s(County))")

    address_regex = re.compile(fr"(?P<address>\d[\d-]*[,\s-]{{,2}}([A-Z0-9][\w-]+[,\s]+){{,3}}({street_types}))")
    route_address_regex = re.compile(r"(?P<address>\d+[\s,]+((Old|County)[\s,]+)?(Route|route|at|Highway)\s\d+)")
    route78_regex = re.compile(r"(route|interstate)[\s-]78", re.I)
    milemarker_regex = re.compile(r"mile marker[\s,]{,2}(?P<mile>\d+( over \d|\.\d)?)")
    exit_regex = re.compile(r"exit\s(number)?\s?(?P<exit>\d+)", re.I)

    #morris
    cross_regex = re.compile(r"(?P<alert>.*?)[,.]\s([Cc]ross off?)")
    morris_regex = re.compile(rf"(?P<symptom>[^,]+)[.,]?\s(?P<address>([\d\-.]+(th|[A-Z])?|[Ff]or|[Tt]o)[.,]?\s([\w\s'.-]+({street_types})|[Rr]oute [\d]+))[,.]? (?P<town>[^,.]+)")

    update_rows = []
    for event in event_table.all():
        text = event['transcription']
        if not text:
            continue
        if not event['original_transcription']:
            event['original_transcription'] = event['transcription']
        else:
            text = event['original_transcription']

        text = re.sub(r"(don)+", '', text)
        text = re.sub(r"(ton)+", 'don', text)
        text = re.sub(r"(ship)+", 'ship', text)
        text = re.sub(r"(hip)+", 'hip', text)
        text = re.sub(r"(ington)+", 'ington', text)
        text = re.sub(r"(ingdon)+", '', text)
        text = re.sub(r"(on){3,}", '', text)
        for correction, misspellings in spelling_correct.items():
            for misspelling in misspellings:
                if misspelling in text:
                    text = text.replace(misspelling, correction)
        text = text.strip()
        text = text.replace('  ', ' ')

        event['transcription'] = text
        for field in ['age', 'gender', 'town', 'address', 'symptom']:
            event[field] = None

        age_match = age_regex.search(text)
        if age_match:
            event['age'] = age_match.group('age') if age_match.group('age') not in age_to_int else age_to_int[age_match.group('age')]
        else:
            age_match = month_age_regex.search(text)
            if age_match:
                event['age'] = age_match.group('age') if age_match.group('age') not in age_to_int else age_to_int[age_match.group('age')]
                event['age'] = f'{event["age"]}mo'

        gender_match = gender_regex.search(text)
        if gender_match:
            event['gender'] = gender_match.group('gender')

        cross_of_match = cross_regex.search(text)
        if cross_of_match and event['county'] == 'morris':
            alert = cross_of_match.group('alert')
            alert_split = list(re.split(r'[,.]\s', alert))
            last_responder = 0
            for cnt, part in enumerate(alert_split):
                match = False
                for responder_catch in ['EMS', 'Company', 'Engine', 'ladder', 'platform', 'Utility', 'Team', 'Township',
                                        'Rockaway', 'RIC', 'engine', 'Dover', 'Vernon', 'Chatham', 'Cedar', 'Boon', 'District', 'Lakes',
                                        'Valley', 'lakes', 'captain', 'Wharton', 'Whippany', 'Sterling', 'Mountain Fire', 'Randolph', 'Platform', 'Parsippany', 'Netcong', 'Mount Tabor', 'Mount Arl'
                                        'Morris', 'Minute', 'Mine Hill', 'Mill Fire', 'Mendham', 'Ladder', 'Captain', 'captain', 'Village', 'Fairmount', 'Chester', 'Brookside']:
                    if responder_catch in part:
                        match = True
                        last_responder = cnt + 1
                        break
                if part == 'St':
                    match = True
                if not match:
                    break
            alert = ', '.join(alert_split[last_responder:])
            morris_match = morris_regex.search(alert)
            if morris_match:
                event['symptom'] = morris_match.group('symptom').lower()
                if event['symptom'] == 'falls':
                    event['symptom'] = 'fall victim'
                    event['transcription'] = event['transcription'].replace('falls', 'fall victim')
                else:
                    event['transcription'] = event['transcription'].replace(morris_match.group('symptom'), event['symptom'])
                event['symptom'] = event['symptom'].strip()

                address = morris_match.group('address').replace(',', '')
                if address.startswith('To'):
                    address = address.replace('To', '2')
                if address.startswith('to'):
                    address = address.replace('to', '2')
                if address.startswith('For'):
                    address = address.replace('For', '4')
                if address.startswith('for'):
                    address = address.replace('for', '4')
                event['address'] = address
                event['town'] = morris_match.group('town')
                update_rows.append(event)
                continue

        for regex in [city_regex, town_regex, county_regex]:
            location_match = regex.search(text)
            if location_match:
                event['town'] = location_match.group('town')
                break

        if event['town']:
            event['town'] = event['town'].replace('Town of', '').replace('City of', '').title().strip()

        route78_match = route78_regex.search(text)
        if route78_match:
            event['address'] = "Route 78"
            if 'westbound' in text.lower():
                event['address'] += 'WB'
            elif 'eastbound' in text.lower():
                event['address'] += 'EB'
            milemarker_search = milemarker_regex.search(text)
            if milemarker_search:
                milemarker = milemarker_search.group('mile').replace(' over ', '.')
                event['address'] += f', MM{milemarker}'
            exit_search = exit_regex.search(text)
            if exit_search:
                exit = exit_search.group('exit')
                event['address'] += f', Exit {exit}'
        else:
            address_match = address_regex.search(text)
            if address_match:
                event['address'] = address_match.group('address').replace(',', '')
            else:
                route_match = route_address_regex.search(text)
                if route_match:
                    event['address'] = route_match.group('address').replace(',', '').replace('at', 'Route').replace('route', 'Route')

        if event['address']:
            event['address'] = event['address'].title().strip()

        for regex in [symptom_regex, gender_action_regex, action_regex, action_no_for_regex]:
            symptom_match = regex.search(text)
            if symptom_match:
                event['symptom'] = symptom_match.group('symptom').lstrip('.').rstrip('.').strip()
                if not event['gender'] and 'gender' in symptom_match.groupdict():
                    event['gender'] = symptom_match.group('gender')
                break

        update_rows.append(event)

    event_table.update_many(update_rows, ['id'])
    database.close()
    log.info('done')


if __name__ == '__main__':
    get_mp3s()
    download_and_transcribe()
    parse_transcriptions()
