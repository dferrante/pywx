import collections
import json
import os
import re
import sys
from urllib.parse import quote_plus, urlencode

import dataset
from flask import (Flask, make_response, render_template, request,
                   send_from_directory)
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

counties = ['hunterdon', 'warren', 'morris', 'somerset']
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
    'pedestrian': '🚶',
    'bicycle': '🚲',
    'motorcycle': '🏍️',
    'gunshot': '🔫',
    'water': '🌊',
    'bike': '🚲',
    'intoxicated': '🍺',
    'carbon monoxide': '💨',
    'leak': '⛽',
    'odor': '👃',
    'transformer': '🔌',
    'wires': '🔌',
    'doa': '💀',
    'dnr': '💀',
    'alcohol': '🍺',
    'allergy': '🤒',
    'bee': '🐝',
    'stool': '💩',
    'broken': '🩹',
    'cancer': '🎗️',
    'cva': '🧠',
    'detox': '🍺',
    'dog': '🐕',
    'eye': '👁️',
    'eyes': '👁️',
    'foot': '🦶',
    'heat': '🔥',
    'kidney': '🫘',
    'leg': '🦵',
    'hand': '🤚',
    'arm': '🦾',
    'truck': '🚚',
    'car': '🚗',
    'elevator': '🏢',
    'nose': '👃',
    'mouth': '👄',
    'nausea': '🤢',
    'pregnancy': '🤰',
    'respiratory': '🫁',
    'stomach': '🤢',
    'suicidal': '🔪',
    'suicide': '🔪',
    'domestic': '🤜👰‍♀️🤵',
    'hazmat': '☢️',
    'oil': '🛢️',
    'assault': '👊',
    'gummy': '🍬',
    'gummies': '🍬🍬'
}

location_type_emojis = {
    'ROOFTOP': '📍',
    'RANGE_INTERPOLATED': '',
    'GEOMETRIC_CENTER': '',
    'APPROXIMATE': '',
}

all_fields = ['id', 'transcription', 'county', 'datetime', 'responding', 'mp3_url', 'is_transcribed', 'age', 'gender', 'town', 'address', 'symptom', 'is_irc_notified', 'original_transcription', 'is_parsed', 'gpt_full_address', 'gpt_incident_details', 'gmaps_types', 'gmaps_address', 'gpt_city', 'gpt_incident_subtype', 'gmaps_location_type', 'gmaps_url', 'gpt_age', 'gpt_gender', 'gpt_incident_type', 'gmaps_parsed', 'gpt_parsed', 'gmaps_latitude', 'gmaps_longitude', 'gpt_place', 'gpt_state']

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
def list_events():
    database = dataset.connect(config['alerts_database'])
    event_table = database['scanner']

    environment = app.jinja_env
    environment.filters['c'] = irc_color
    environment.filters['highlight'] = lambda text, phrase: text.replace(phrase, irc_color(phrase, '#b8ecf2')) if phrase else text
    environment.filters['station_highlight'] = lambda station: irc_color(station, 'red') if any([important_station in station.lower() for important_station in important_stations]) else irc_color(station, '#fa7516')

    page = int(request.args.get('page', 1))
    per_page = 20
    event_query = []
    if request.args.get('id'):
        event_query = event_table.find(id=request.args['id'])
        event_count = 1
    else:
        default_search = {
            'is_transcribed': True,
        }
        if request.args.get('search'):
            search_query = database.query('SELECT rowid FROM scanner_fts WHERE scanner_fts MATCH :search', search=request.args["search"])
            match_ids = [row['rowid'] for row in search_query]
            event_count = len(match_ids)
            default_search['id'] = {'in': match_ids}
            default_search['_limit'] = per_page
            default_search['_offset'] = (page - 1) * per_page
            default_search['order_by'] = ['-datetime']
            event_query = event_table.find(**default_search)
        else:
            if request.args.get('station'):
                default_search['responding'] = {'ilike': f'%{request.args["station"]}%'}
            if request.args.get('county'):
                default_search['county'] = {'ilike': f'%{request.args["county"]}%'}
            if request.args.get('town'):
                default_search['town'] = request.args["town"]
            if request.args.get('place'):
                default_search['gpt_place'] = {'ilike': f'%{request.args["place"]}%'}
            if request.args.get('type') and request.args.get('type') != 'None':
                default_search['gpt_incident_type'] = request.args["type"]
            if request.args.get('subtype') and request.args.get('subtype') != 'None':
                default_search['gpt_incident_subtype'] = request.args["subtype"]

            event_count = event_table.count(**default_search)
            default_search['_limit'] = per_page
            default_search['_offset'] = (page - 1) * per_page
            default_search['order_by'] = ['-datetime']
            event_query = event_table.find(**default_search)

    prev_page = page - 1 if page > 1 else None
    next_page = page + 1 if event_count and event_count > page * per_page else None
    last_page = event_count // per_page
    if last_page == 1:
        last_page = None

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

        punctuation_stripper = re.compile(r'[^\w\s]')
        words = set()
        for field in ['gpt_incident_subtype', 'gpt_incident_details', 'transcription', 'symptom']:
            if event.get(field):
                words.update(event.get(field, '').split(' '))
        emojis = set()
        for word in words:
            word = punctuation_stripper.sub('', word).lower()
            emojis.add(subtype_emojis.get(word))
        emojis = sorted(list(filter(None, emojis)))

        if incident_emojis.get(event.get('gpt_incident_type')):
            incident_emoji = incident_emojis.get(event['gpt_incident_type'])
            if incident_emoji:
                emojis = [incident_emoji] + list(filter(lambda x: x != incident_emoji, emojis))

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

    response = {
        'events': events,
        'counties': counties,
        'request': request,
        'event_count': event_count,
        'metadata_order': metadata_order,
        'gmaps_embed_key': config['gmaps_embed_key'],
        'page': page,
        'prev_page': prev_page,
        'next_page': next_page,
        'last_page': last_page,
    }

    rendered_template = render_template('events.html', **response)
    response = make_response(rendered_template)
    if request.args:
        args = request.args.copy()
        args.pop('issues', None)
        args.pop('towns', None)
        args.pop('stations', None)
        sorted_args = dict(sorted(args.items()))
        response.headers['HX-Push-Url'] = f'?{urlencode(sorted_args)}'
    response.headers['HX-Trigger-After-Swap'] = 'scrollToTop'
    return response


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

    rendered_template = render_template('stations.html', county_station=county_station, counties=counties)
    response = make_response(rendered_template)
    return response


@app.route('/towns')
def towns():
    database = dataset.connect(config['alerts_database'])
    event_table = database['scanner']

    distinct_pairs = event_table.distinct('county', 'town')
    counter = collections.defaultdict(list)
    for pair in distinct_pairs:
        count = event_table.count(county=pair['county'], town=pair['town'])
        counter[pair['county']].append((pair['town'], count))

    rendered_template = render_template('towns.html', county_towns=counter, counties=counties)
    response = make_response(rendered_template)
    return response


@app.route('/issues')
def issues():
    database = dataset.connect(config['alerts_database'])
    event_table = database['scanner']

    distinct_pairs = event_table.distinct('gpt_incident_type', 'gpt_incident_subtype')
    counter = collections.defaultdict(list)
    for pair in distinct_pairs:
        count = event_table.count(gpt_incident_type=pair['gpt_incident_type'], gpt_incident_subtype=pair['gpt_incident_subtype'])
        counter[pair['gpt_incident_type']].append((pair['gpt_incident_subtype'], count))

    rendered_template = render_template('issues.html', counter=counter)
    response = make_response(rendered_template)
    return response


@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'favicon.ico', mimetype='image/vnd.microsoft.icon')
