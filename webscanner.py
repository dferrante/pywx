import collections
import json
import os
import re
import sys
from urllib.parse import quote_plus

import dataset
from flask import Flask, render_template, request, send_from_directory
from markupsafe import Markup

app = Flask(__name__)

try:
    config = json.load(open('data/local_config.json', encoding='utf-8'))
    config['pywx_path'] = os.path.dirname(os.path.abspath(__file__))
except ImportError:
    print('cant import local_config.py')
    sys.exit()

repeating_regex = re.compile(r"(?P<first>.*)(Repeating|Paging|Again|repeating|paging|again)[\s.,]+(?P<repeat>.*)")
important_stations = ['45fire', '46fire', 'sbes', 'southbranch']
very_important_words = ['studer', 'sunrise', 'austin hill', 'foundations', 'apollo', 'foxfire', 'river bend', 'grayrock', 'greyrock', 'beaver', 'lower west', 'norma']
important_words = ['clinton', 'annandale', 'school']

counties = ['hunterdon', 'warren', 'morris', 'sussex']
incident_emojis = {
    'fire': '🔥',
    'medical': '🚑',
    'accident': '⛐',
    'police': '🚓',
    'fall victim': '👇🤕',
    'other': '🚨',
}
subtype_emojis = {
    'sick': '🤒',
    'breathing': '🫁',
    'resperatory': '🫁',
    'chest pain': '💔',
    'cardiac': '💔',
    'unconscious': '😵',
    'stroke': '🧠',
    'seizure': '🧠',
    'trauma': '🩹',
    'fall': '👇🤕',
    'unresponsive': '😵',
    'unconscious': '😵',
    'overdose': '💊',
    'psych': '🧠',
    'heart': '💔',
    'diabetic': '🩸',
    'bleeding': '🩸',
    'burn': '🔥',
    'choking': '🤢',
    'drowning': '🌊',
    'electrocution': '⚡',
    'alarm': '🚨',
    'fire': '🔥',
    'altered': '🧠',
    'pain': '🤕',
    'weakness': '🤕',
    'landing': '🚁',
    'rectal': '🍑',
    'bleed': '🩸',
}

location_type_emojis = {
    'ROOFTOP': '📍',
    'RANGE_INTERPOLATED': '',
    'GEOMETRIC_CENTER': '',
    'APPROXIMATE': '',
}

all_fields = ['id', 'transcription', 'county', 'datetime', 'responding', 'mp3_url', 'is_transcribed', 'age', 'gender', 'town', 'address', 'symptom', 'is_irc_notified', 'original_transcription', 'is_parsed', 'gpt_full_address', 'gpt_incident_details', 'gmaps_types', 'gmaps_address', 'gpt_city', 'gpt_incident_subtype', 'gmaps_location_type', 'gmaps_url', 'gpt_age', 'gpt_gender', 'gpt_incident_type', 'gmaps_parsed', 'gpt_parsed', 'gmaps_latitude', 'gmaps_longitude', 'gpt_place']

metadata_order = {
    '': ['id', 'datetime', 'county', 'responding'],
    'incident': ['gpt_incident_type', 'gpt_incident_subtype', 'gpt_incident_details', 'symptom'],
    'location': ['gpt_place', 'gmaps_address', 'gpt_full_address', 'address', 'gmaps_types', 'gmaps_location_type','gmaps_latitude', 'gmaps_longitude', 'gpt_city', 'town'],
    'person': ['age', 'gender', 'gpt_age', 'gpt_gender'],
    'transcription': ['transcription', 'original_transcription'],
}


def irc_color(value, color):
    return Markup(f'<span style="color: {color};">{value}</span>')


@app.route("/")
def index():
    return render_template('base.html', counties=counties, request=request)


@app.route("/events")
def list():
    database = dataset.connect(config['alerts_database'])
    event_table = database['scanner']

    environment = app.jinja_env
    environment.filters['c'] = irc_color
    environment.filters['highlight'] = lambda text, phrase: text.replace(phrase, irc_color(phrase, '#b8ecf2')) if phrase else text
    environment.filters['station_highlight'] = lambda station: irc_color(station, 'red') if any([important_station in station.lower() for important_station in important_stations]) else irc_color(station, '#fa7516')

    page = int(request.args.get('page', 1))
    event_query = []
    if request.args.get('id'):
        event_query = event_table.find(id=request.args['id'])
        event_count = False
    else:
        default_search = {
            'is_transcribed': True,
            'order_by': ['-datetime'],
            '_limit': 100,
            '_offset': (page - 1) * 100
        }
        if request.args.get('search'):
            default_search['transcription'] = {'ilike': f'%{request.args["search"]}%'}
        if request.args.get('station'):
            default_search['responding'] = {'ilike': f'%{request.args["station"]}%'}
        if request.args.get('county'):
            default_search['county'] = {'ilike': f'%{request.args["county"]}%'}
        if request.args.get('town'):
            default_search['town'] = request.args["town"]
        if request.args.get('place'):
            default_search['gpt_place'] = {'ilike': f'%{request.args["place"]}%'}

        event_query = event_table.find(**default_search)
        event_count = event_table.count(**default_search)

    events = []
    for event in event_query:
        time = event['datetime'].strftime('%m/%d %-I:%M%p')
        responding = sorted(event['responding'].split(','))
        vip_word_color = '#fa7516' if any([word in event['transcription'].lower() for word in important_words if word]) and event['county'] == 'hunterdon' else '#3c99cf'
        vip_word_color = 'red' if any([word in event['transcription'].lower() for word in very_important_words if word]) and event['county'] == 'hunterdon' else vip_word_color

        repeat_search = repeating_regex.search(event['transcription'])
        if repeat_search:
            first = repeat_search.group('first')
            repeat = repeat_search.group('repeat')
            transcription = '<br>'.join([first, 'Repeating ' + repeat])
        else:
            transcription = event['transcription']

        emojis = set()
        if incident_emojis.get(event.get('gpt_incident_type')):
            emojis.add(incident_emojis.get(event['gpt_incident_type']))
        if event['gpt_incident_subtype']:
            for subtype in event['gpt_incident_subtype'].split(' '):
                emojis.add(subtype_emojis.get(subtype))
        emojis = filter(None, emojis)

        location_emoji = location_type_emojis.get(event.get('gmaps_location_type'), '')

        age_and_gender = []
        if event['gpt_incident_details']:
            if event['gpt_age'] and event['gpt_age'] not in event['gpt_incident_details']:
                age_and_gender.append(event['gpt_age'] + 'yo' if 'mo' not in event['gpt_age'] else event['gpt_age'])
            if event['gpt_gender'] and event['gpt_gender'] not in event['gpt_incident_details']:
                age_and_gender.append(event['gpt_gender'])
        age_and_gender = ' '.join(age_and_gender)

        payload = {
            'datetime': time,
            'responding': responding,
            'vip_word_color': vip_word_color,
            'transcription': Markup(transcription),
            'event': event,
            'emojis': emojis,
            'location_emoji': location_emoji,
            'age_and_gender': age_and_gender,
        }

        if event['address'] and event['town']:
            full_address = f"{event['address']}, {event['town']}, NJ"
            gmaps_url = f'https://www.google.com/maps/place/{quote_plus(full_address)}/data=!3m1!1e3'
            payload['full_address'] = full_address
            payload['gmaps_url'] = gmaps_url

        events.append(payload)

    return render_template('events.html', events=events, counties=counties, request=request, event_count=event_count, metadata_order=metadata_order)


@app.route('/stations')
def stations():
    database = dataset.connect(config['alerts_database'])
    event_table = database['scanner']

    county_station = collections.defaultdict(set)
    for event in event_table.all():
        for station in event['responding'].split(','):
            county_station[event['county']].add(station.strip())

    for county in county_station:
        stations = []
        for station in sorted(county_station[county]):
            count = event_table.count(responding={'ilike': f'%{station}%'})
            stations.append((station, count))
        county_station[county] = stations

    return render_template('stations.html', county_station=county_station, counties=counties)


@app.route('/towns')
def towns():
    database = dataset.connect(config['alerts_database'])
    event_table = database['scanner']

    county_towns = collections.defaultdict(set)
    for event in event_table.all():
        if event['town']:
            county_towns[event['county']].add(event['town'])

    for county in county_towns:
        towns = []
        for town in sorted(county_towns[county]):
            count = event_table.count(town=town)
            towns.append((town, count))
        county_towns[county] = towns

    return render_template('towns.html', county_towns=county_towns, counties=counties)


@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'favicon.ico', mimetype='image/vnd.microsoft.icon')
