import argparse
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

parser = argparse.ArgumentParser()
parser.add_argument("config_file", help="path to the config file")
args = parser.parse_args()

try:
    config = json.load(open(args.config_file, encoding='utf-8'))
    config['pywx_path'] = os.path.dirname(os.path.abspath(__file__))
except ImportError:
    print('cant import local_config.py')
    sys.exit()


def parse_alerts():
    print('starting transcription')
    database = dataset.connect(config['alerts_database'])
    model = WhisperModel("large-v2", device="cpu", compute_type="int8")
    event_table = database['scanner']
    if 'transcription' not in event_table.columns:
        event_table.create_column('transcription', Text)

    mp3s = []

    alerts_url = 'https://dispatchalert.group//includes/js/flat.audio.hunterdon.js'
    resp = requests.get(alerts_url)
    for raw_line in resp.iter_lines():
        line = raw_line.decode('ascii').strip()
        if 'mp3:' in line:
            mp3s.append(line[6:-1])

    # alerts_url = 'https://dispatchalert.group//includes/js/flat.audio.warren.js'
    # resp = requests.get(alerts_url)
    # for raw_line in resp.iter_lines():
    #     line = raw_line.decode('ascii').strip()
    #     if 'mp3:' in line:
    #         mp3s.append(line[6:-1])

    grouped_events = []
    event = []
    last_event_date = None
    group_in_seconds = 30
    for mp3_url in mp3s:
        parsed_url = re.search(r"https://dispatchalert.net/(?P<county>[^/]+)/(?P<unit>[^/_]+)_(?P<datetime>[\d_]+).mp3", mp3_url).groupdict()
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
                print('updating', existing_event['mp3_url'])
                event_table.update(dict(responding=responding, id=existing_event['id']), ['id'])
        else:
            print('inserting', event['mp3_url'])
            event_table.insert(dict(county=event['county'], datetime=first_datetime, responding=responding, mp3_url=event['mp3_url'], is_transcribed=False, is_irc_notified=False))

    for event in event_table.find(is_transcribed=False, order_by=['datetime']):
        print('ID:', event['id'])
        print('County:', event['county'])
        print('Date:', event['datetime'])
        print('Responding:')
        for unit in event['responding'].split(','):
            print("  - ", unit)
        print()

        local_filename = '/tmp/temp.mp3'
        with requests.get(event['mp3_url'], stream=True) as r:
            with open(local_filename, 'wb') as f:
                shutil.copyfileobj(r.raw, f)

        segments, _ = model.transcribe(local_filename, beam_size=5, vad_filter=True)
        transcription = []
        for segment in segments:
            transcription.append(segment.text)
            print(segment.text)

        transcription = ' '.join(transcription)
        event_table.update(dict(id=event['id'], transcription=transcription, is_transcribed=True), ['id'])
        print('-------------')

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
    spelling_correct = {
        'Alexandria Township': ['Alexander Township'],
        'Amwell': ['AML', 'Enwood', 'Danwell', 'End West', 'Amel', 'Seminole', 'Sandwell', 'Humbolt', 'Stanwell'],
        'West Amwell': ['West Elmwood', 'West Emerald', 'West Hamilton', 'West Hamlet', 'West Hamlin'],
        'Amwell Township': ['Ammo', 'Amo Township', 'Animal Township', 'Antelope Township'],
        'Barley Sheaf': ['Barley Sheep', 'Barley Chief'],
        'Bethlehem': ['SLAM'],
        'Bloomsbury': ['Bluesberry'],
        'Branchburg': ['Bransford'],
        'Califon Borough': ['California Borough', 'Californ Borough', 'Califontine Borough', 'Caliphon Borough'],
        'Clinton': ['Quentin', 'Caldwin'],
        'Clinton Township': ['Clint Township', 'Clayton Township', 'Clinton Tachib'],
        'Croton': ['Croaten'],
        'Flemington': ['Flamington', 'Clemington', 'Plumbington', 'Wilmington'],
        'Frenchtown': ['French Town'],
        'High Bridge': ['Highbridge', 'highbridge'],
        'High Bridge Borough': ['Hybridsboro'],
        'Hunterdon': ['Huntingdon', 'Hunter'],
        'Hunterdon Care Center': ['Hunter and Care Center', 'Hunterdon and Care Center', 'Hunter Care Center'],
        'Kingwood Township': ['with Township'],
        'Lambertville': ['Lambeville', 'Lamerill', 'Lamberville', 'Lamerville', 'Laramville', 'Limberville', "Lamarville", 'Lambauville', 'Lumberphil', 'Lamberthill', 'Lamberthville', 'Laramieville'],
        'Lebanon Township': ['11 on Township', '111 on Township', '11 to Township', 'Leavett on Township'],
        'Lopatcong': ['Lopatkin'],
        'Paging': ['Puging'],
        'Pittstown': ['Pitsdown', 'Pitstown'],
        'Raritan': ['Rareton', 'Renton'],
        'Raritan Township': [
            'where to Township', "we're in Township", 'route in Township', 'Aaron Township', 'Arrington Township', 'Barrington Township', 'Burrington Township',
            'Barret Township', 'Brereton Township', 'Rarity Township', 'Rarit Township', 'rear end tangent', 'ready to Township', 'ready to township',
            'rare in a township', 'rare in town', 'rare in township', 'route and attach', 'route attached', 'Barrett Township'
        ],
        'Readington': ['Reddington'],
        'Readington Township': ['responding to Township', 'running to Township', 'routing to Township', 'riding to Township', 'right on Township'],
        'Township': ['Tach', 'Tash', 'Tadge', 'Tatchett'],
        'Repeating': ['Skiing', 'Reading '],
        'Responding': ['Spawning'],
        'Route 78': ['route 70'],
        'Tewksbury': ['Tewsbury', 'Chiefsbury'],
        'Tewksbury Township': ['123 Township'],
        'Walter Foran': ['Walter Farran'],
        'chest pain': ['Chesepeake', 'Chesapine'],
        'described': ['ascribed'],
        'fall victim': ['full victim'],
        'leg pain': ['Lake Payne'],
        'lift assist': ['left assist', 'Leipzig'],
        'responding': ['spawning'],
        'syncopal': ['sinkable', 'sickable', 'singapore', 'Singapore', 'syncable'],
        'syncopal episode': ['single episode'],
        'syncope': ['synchro'],
        'vomiting': ['abominate'],
        'Town of Clinton': ['town of Clinton'],
        'Shop Rite': ['shop right'],
        'CO2 alarm': ['seal alarm']
    }

    street_types = '|'.join([
        'Street',
        'Road',
        'Lane',
        'Drive',
        'Avenue',
        'Court',
        'Blvd',
        'Boulevard',
        'Highway',
        'Circle',
        'Way',
        'Plaza',
        'Hillway',
        'Pass',
        'Pike',
        'plaza',
        'Crestway',
        'Place'
    ])

    genders = r"(?P<gender>male|female|Male|Female)"

    age_regex = re.compile(fr"(?P<age>\d+|{text_ages})(-?ish)?('s)?[\s-]+years?([\s-]+olds?)?")
    month_age_regex = re.compile(fr"(?P<age>\d+|{text_ages})(-?ish)?('s)?[\s-]+months?([\s-]+olds?)?")

    gender_regex = re.compile(rf"years?([\s-]+olds?)?[\s,]+{genders}")

    symptom_regex = re.compile(rf"years?([\s-]+olds?)?[\s,]+{genders}?[\s,]{{,2}}(with a |who |with |that |they |described as (a )?|complaining of)?(?P<symptom>[\w\W]+?)[\s,\.]{{,2}}(Repeating|repeating|Paging|\d+)")
    action_regex = re.compile(rf"(for|For) (an? )?({genders}\s)?(?P<symptom>[\w\W]+?)[\s,\.]{{,2}}(Repeating|repeating|Paging)")
    gender_action_regex = re.compile(rf"{genders}[\s,\.]{{,2}}(?P<symptom>[\w\W]+?)[\s,\.]{{,2}}(Repeating|repeating|Paging)")
    action_no_for_regex = re.compile(fr"({street_types})[\s,]+(?P<symptom>[\w\W]+?)[\s,\.]{{,2}}(Repeating|repeating|Paging)")

    city_regex = re.compile(r"(?P<town>(City|Town|city|town) of \w+)")
    town_regex = re.compile(r"(?P<town>(West |East |Glen |High )?\w+\s(Borough|Township|County|Town|City|township|borough))")
    county_regex = re.compile(r"(?P<town>(West |East |Glen |High )?\w+\s(County))")

    address_regex = re.compile(fr"(?P<address>\d[\d-]*[,\s-]{{,2}}([A-Z0-9][\w-]+[,\s]+){{,3}}({street_types}))")
    route_address_regex = re.compile(r"(?P<address>\d+[\s,]+((Old|County)[\s,]+)?(Route|route|at|Highway)\s\d+)")
    route78_regex = re.compile(r"(route|interstate)[\s-]78", re.I)
    milemarker_regex = re.compile(r"mile marker[\s,]{,2}(?P<mile>\d+( over \d|\.\d)?)")
    exit_regex = re.compile(r"exit\s(number)?\s?(?P<exit>\d+)", re.I)

    update_rows = []
    for event in event_table.all():
        text = event['transcription']
        if not text:
            continue
        for correction, misspellings in spelling_correct.items():
            for misspelling in misspellings:
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

        for regex in [city_regex, town_regex, county_regex]:
            location_match = regex.search(text)
            if location_match:
                event['town'] = location_match.group('town')
                break

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

        for regex in [symptom_regex, gender_action_regex, action_regex, action_no_for_regex]:
            symptom_match = regex.search(text)
            if symptom_match:
                event['symptom'] = symptom_match.group('symptom').lstrip('.').rstrip('.').strip()
                if not event['gender'] and 'gender' in symptom_match.groupdict():
                    event['gender'] = symptom_match.group('gender')
                break

        update_rows.append(event)

    for row in update_rows:
        event_table.update(dict(row), ['id'])
    database.close()


if __name__ == '__main__':
    parse_alerts()
