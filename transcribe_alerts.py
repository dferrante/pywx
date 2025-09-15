import argparse
import datetime
import json
import os
import re
import shutil
import sys
import tempfile

import av
import dataset
import geopy
import requests
from faster_whisper import WhisperModel
from openai import OpenAI
from sqlalchemy import Boolean, Integer, Text

from logger import get_logger
from spelling_correct import spelling_correct

log = get_logger('transcribe_alerts')

try:
    config = json.load(open('data/local_config.json', encoding='utf-8'))
    config['pywx_path'] = os.path.dirname(os.path.abspath(__file__))
except ImportError:
    log.error('cant import local_config.py')
    sys.exit(-1)

geoloc = geopy.geocoders.GoogleV3(api_key=config['youtube_key'])

all_fields = ['id', 'transcription', 'county', 'datetime', 'responding', 'mp3_url', 'is_transcribed', 'age', 'gender', 'town', 'address', 'symptom', 'is_irc_notified', 'original_transcription', 'is_parsed', 'gpt_full_address', 'gpt_incident_details', 'gmaps_types', 'gmaps_address', 'gpt_city', 'gpt_incident_subtype', 'gmaps_location_type', 'gmaps_url', 'gpt_age', 'gpt_gender', 'gpt_incident_type', 'gmaps_parsed', 'gpt_parsed', 'gmaps_latitude', 'gmaps_longitude', 'gpt_place', 'gpt_state']


def get_mp3s():
    log.info('getting mp3s')
    database = dataset.connect(config['alerts_database'])
    event_table = database['scanner']

    for county in ['hunterdon', 'morris', 'warren', 'sussex', 'somerset']:
        mp3s = []
        alerts_url = f'https://dispatchalert.group//includes/js/flat.audio.{county}.js'
        resp = requests.get(alerts_url, timeout=60)
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
                if county == 'somerset':
                    parsed_url = re.search(r"https://dispatchalert.net/(?P<county>[^/]+)/(?P<unit>[\w-]*?)(?=_-_)_-_([a-z0-9]{5,})_(?P<datetime>[\d_]+).mp3", mp3_url).groupdict()
                else:
                    parsed_url = re.search(r"https://dispatchalert.net/(?P<county>[^/]+)/(?P<unit>[^/_]+)__?(?P<datetime>[\d_]+).mp3", mp3_url).groupdict()
            except AttributeError:
                log.warn('could not parse url: %s', mp3_url)
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
                event_table.insert(dict(county=event['county'], datetime=first_datetime, responding=responding, mp3_url=event['mp3_url'], is_transcribed=False, is_irc_notified=False, is_parsed=False))


def download_and_transcribe():
    log.info('starting transcriptions')
    database = dataset.connect(config['alerts_database'])
    event_table = database['scanner']

    model = WhisperModel("large-v2", download_root="data/whisper")
    for event in event_table.find(is_transcribed=False, order_by=['datetime']):
        if event['datetime'] < (datetime.datetime.now() - datetime.timedelta(days=5)):
            log.debug(f'event {event["id"]} too old, skipping')
            continue

        log.info(f'downloading {event["mp3_url"]}')
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
            with requests.get(event['mp3_url'], stream=True, timeout=60) as r:
                shutil.copyfileobj(r.raw, temp_file)

            log.info(f'transcribing {event["mp3_url"]}')
            try:
                segments, _ = model.transcribe(temp_file.name, beam_size=5, vad_filter=True)
            except av.error.ValueError:
                log.warn('transcription failed for event {event["id"]} {event["mp3_url"]}')
                segments = []
            transcription = []
            for segment in segments:
                transcription.append(segment.text)

        transcription = ' '.join(transcription)
        event_table.update(dict(id=event['id'], transcription=transcription, is_transcribed=True), ['id'])


def parse_transcriptions(all_events):
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
        'Pass', 'Pike', 'Crestway', 'Place', 'Terrace', 'Ridge', 'Park', 'Run', 'Hills', 'Trail', 'Row'
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
    if all_events:
        events = event_table.all()
    else:
        events = event_table.find(is_parsed=False)

    for event in events:
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

                if not all_events:
                    gpt_parse_results = gpt_parse(event)
                    if gpt_parse_results['gpt_full_address']:
                        geoloc_results = geolocate(event['county'], gpt_parse_results['gpt_full_address'])
                    else:
                        geoloc_results = geolocate(event['county'], f"{event['address']}, {event['town']}, NJ")
                    event.update(gpt_parse_results)
                    event.update(geoloc_results)

                event['is_parsed'] = True
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

        if not all_events:
            gpt_parse_results = gpt_parse(event)
            if gpt_parse_results['gpt_full_address']:
                geoloc_results = geolocate(event['county'], gpt_parse_results['gpt_full_address'])
            else:
                geoloc_results = geolocate(event['county'], f"{event['address']}, {event['town']}, NJ")
            event.update(gpt_parse_results)
            event.update(geoloc_results)
        event['is_parsed'] = True
        update_rows.append(event)

    event_table.update_many(update_rows, ['id'])
    for event in update_rows:
        fts_event(database, event['_id'])
    database.close()
    log.info('done')


def geolocate(county, full_address):
    bounds = {
        'hunterdon': [(-75.3199348684483,40.75823811169378), (-74.61330674375678,40.34974907331191)],
        'morris': [(-74.95349930842227,41.03973731989822), (-74.18804986518307,40.66243060070209)],
        'warren': [(-75.34714596046982,41.06402566152515), (-74.67510691546788,40.62637616797859)],
        'sussex': [(-75.05845242057806,41.36071447694682), (-74.29917269700853,40.94262863833735)],
        'somerset': [(-74.747542,40.758636), (-74.376494, 40.359894)],
    }

    try:
        loc = geoloc.geocode(full_address, exactly_one=True, bounds=bounds[county])
        if not loc:
            return {}
        return {
            'gmaps_latitude': loc.latitude,
            'gmaps_longitude': loc.longitude,
            'gmaps_address': loc.address,
            'gmaps_types': ', '.join(loc.raw['types']),
            'gmaps_location_type': loc.raw['geometry']['location_type'],
            'gmaps_url': f'https://maps.google.com/?t=k&q={loc.latitude},{loc.longitude}',
            'gmaps_parsed': True,
        }
    except Exception:
        return {}


def gpt_parse(event):
    responding = ', '.join(event['responding'].split(','))
    GPT_MODEL = 'gpt-4o'
    system_prompt = """Your goal is to take the transcription of an ems and fire dept call from NJ, and separate out the full address and include the state, what the incident is about, the age, and gender, all in unique fields, and return it in json format.  be succinct. if fields cannot be found, return null.  fields should be: 'full_address', 'incident_type', 'incident_subtype', 'age', 'gender', 'city', 'place', and 'incident_details'.  incident_type field should be all lowercase and should be one of: medical, fire, accident, fall victim, police, or other.  fall victims also include people needing a lift assist.  incident_subtype should be a concise short simple one or two word string about the type of the incident if it is medical.  incident_details field should have a summary of any information about the incident, and should omit hours, address, age, gender, and responding stations.  if the city is not found, derive it from the responding station.  do not include cross streets.  city should be in full_address and also in its own field. the place field should be the name of a place, like a business, school, hospital, etc.  the output should be json with no markdown, and prefix the json keys with 'gpt_'"""
    event_text = f"Responding stations: {responding}\nTranscription: {event['transcription']}"

    client = OpenAI(api_key=config['openai_key'])
    response = client.chat.completions.create(model=GPT_MODEL, response_format={"type": "json_object"}, messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": event_text}])
    summary = response.choices[0].message.content
    summary = json.loads(summary)
    summary['gpt_parsed'] = True
    for key in list(summary.keys()):
        if key not in all_fields:
            del summary[key]
    return summary


def gpt_parse_bulk():
    database = dataset.connect(config['alerts_database'])
    event_table = database['scanner']
    system_prompt = """Your goal is to take the transcription of an ems and fire dept call from NJ, and separate out the full address and include the state, what the incident is about, the age, and gender, all in unique fields, and return it in json format.  be succinct. if fields cannot be found, return null.  fields should be: 'full_address', 'incident_type', 'incident_subtype', 'age', 'gender', 'city', 'place', and 'incident_details'.  incident_type field should be all lowercase and should be one of: medical, fire, accident, fall victim, police, or other.  fall victims also include people needing a lift assist.  incident_subtype should be a concise short simple one or two word string about the type of the incident if it is medical.  incident_details field should have a summary of any information about the incident, and should omit hours, address, age, gender, and responding stations.  if the city is not found, derive it from the responding station.  do not include cross streets.  city should be in full_address and also in its own field. the place field should be the name of a place, like a business, school, hospital, etc.  the output should be json with no markdown, and prefix the json keys with 'gpt_'"""

    with open('data/events.jsonl', 'w') as f:
        for event in event_table.find(gpt_parsed=False):
            responding = ', '.join(event['responding'].split(','))
            event_text = f"Responding stations: {responding}\nTranscription: {event['transcription']}"
            line = {
                "custom_id": f"{event['id']}",
                "method": "POST",
                "url": "/v1/chat/completions",
                "body": {
                    "model": 'gpt-4o',
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": event_text}
                    ],
                }
            }
            f.write(json.dumps(line) + '\n')


def fix_columns():
    log.info('fixing columns')
    database = dataset.connect(config['alerts_database'])
    event_table = database['scanner']
    for col in ['original_transcription', 'gpt_full_address', 'gpt_incident_details', 'gmaps_types', 'gmaps_address', 'gpt_city', 'gpt_incident_subtype', 'gmaps_location_type', 'gmaps_url', 'gpt_age', 'gpt_gender', 'gpt_incident_type', 'gpt_place', 'gpt_state']:
        if col not in event_table.columns:
            event_table.create_column(col, Text)
    for col in ['gmaps_parsed', 'gpt_parsed']:
        if col not in event_table.columns:
            event_table.create_column(col, Boolean)
    for col in ['gmaps_latitude', 'gmaps_longitude']:
        if col not in event_table.columns:
            event_table.create_column(col, Integer)


def fts_event(database, event_id):
    database.query('''
    INSERT INTO scanner_fts (responding,
            transcription,
            gpt_full_address,
            gpt_incident_details,
            gmaps_address,
            gpt_incident_subtype,
            gpt_place)
    SELECT responding,
            transcription,
            gpt_full_address,
            gpt_incident_details,
            gmaps_address,
            gpt_incident_subtype,
            gpt_place
    FROM scanner
    WHERE id = :event_id;
    ''', event_id=event_id)


def create_fts_table():
    log.info('creating FTS table')
    database = dataset.connect(config['alerts_database'])
    database.query('DROP TABLE IF EXISTS scanner_fts;')
    database.query('''
        CREATE VIRTUAL TABLE IF NOT EXISTS scanner_fts USING fts5(
            responding,
            transcription,
            gpt_full_address,
            gpt_incident_details,
            gmaps_address,
            gpt_incident_subtype,
            gpt_place
        );
    ''')

    # Populate the FTS table with data from the existing table
    database.query('''
    INSERT INTO scanner_fts (responding,
            transcription,
            gpt_full_address,
            gpt_incident_details,
            gmaps_address,
            gpt_incident_subtype,
            gpt_place)
    SELECT responding,
            transcription,
            gpt_full_address,
            gpt_incident_details,
            gmaps_address,
            gpt_incident_subtype,
            gpt_place
    FROM scanner;
    ''')


def create_indexes():
    log.info('creating indexes')
    database = dataset.connect(config['alerts_database'])
    database.query("CREATE INDEX IF NOT EXISTS idx_scanner_responding ON scanner(responding)")
    database.query("CREATE INDEX IF NOT EXISTS idx_scanner_responding_county ON scanner(responding, county)")
    database.query("CREATE INDEX IF NOT EXISTS idx_scanner_town ON scanner(town)")
    database.query("CREATE INDEX IF NOT EXISTS idx_scanner_town_county ON scanner(town, county)")
    database.query("CREATE INDEX IF NOT EXISTS idx_scanner_type ON scanner(gpt_incident_type)")
    database.query("CREATE INDEX IF NOT EXISTS idx_scanner_type_subtype ON scanner(gpt_incident_type, gpt_incident_subtype)")
    database.query("CREATE INDEX IF NOT EXISTS idx_scanner_gmaps_lat_lon ON scanner(gmaps_latitude, gmaps_longitude)")


def migration():
    log.info('running migration')
    fix_columns()
    create_fts_table()
    create_indexes()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Grab and transcribe scanner traffic")
    parser.add_argument('--fullparse', action='store_true', help="Enable full parsing mode")
    parser.add_argument('--migrate', action='store_true', help="Run database tasks")
    parser.add_argument('--bulk-parse', action='store_true', help="Output the bulk file")
    args = parser.parse_args()

    if args.bulk_parse:
        gpt_parse_bulk()
        sys.exit(0)

    if args.migrate:
        migration()
        sys.exit(0)

    if not args.fullparse:
        get_mp3s()
        download_and_transcribe()
    parse_transcriptions(all_events=args.fullparse)

    # database = dataset.connect(config['alerts_database'])
    # event_table = database['scanner']
    # event = event_table.find_one(id=35097)
    # gpt_parse_results = gpt_parse(event)
    # geoloc_results = geolocate(event['county'], gpt_parse_results['gpt_full_address'])
    # from pprint import pprint
    # pprint(event['transcription'])
    # pprint(gpt_parse_results)
    # pprint(geoloc_results)
    # gpt_parse_bulk()

    sys.exit(0)
