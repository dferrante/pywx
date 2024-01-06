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


def irc_color(value, color):
    return Markup(f'<span style="color: {color};">{value}</span>')


@app.route("/")
def list():
    database = dataset.connect(config['alerts_database'])
    event_table = database['scanner']

    environment = app.jinja_env
    environment.filters['c'] = irc_color
    environment.filters['highlight'] = lambda text, phrase: text.replace(phrase, irc_color(phrase, '#b8ecf2')) if phrase else text
    environment.filters['station_highlight'] = lambda station: irc_color(station, 'red') if any([important_station in station.lower() for important_station in important_stations]) else irc_color(station, '#fa7516')

    event_query = []
    if request.args.get('id'):
        event_query = event_table.find(id=request.args['id'])
    else:
        default_search = {
            'is_transcribed': True,
            'order_by': ['-datetime'],
            '_limit': 100
        }
        if request.args.get('search'):
            default_search['transcription'] = {'ilike': f'%{request.args["search"]}%'}
        if request.args.get('station'):
            default_search['responding'] = {'ilike': f'%{request.args["station"]}%'}
        if request.args.get('county'):
            default_search['county'] = {'ilike': f'%{request.args["county"]}%'}
        if request.args.get('town'):
            default_search['town'] = request.args["town"]

        event_query = event_table.find(**default_search)

    events = []
    for event in event_query:
        time = event['datetime'].strftime('%m/%d %-I:%M%p')
        responding = sorted(event['responding'].split(','))
        vip_word_color = '#fa7516' if any([word in event['transcription'].lower() for word in important_words if word]) else '#3c99cf'
        vip_word_color = 'red' if any([word in event['transcription'].lower() for word in very_important_words if word]) else vip_word_color

        repeat_search = repeating_regex.search(event['transcription'])
        if repeat_search:
            first = repeat_search.group('first'), event['town']
            repeat = repeat_search.group('repeat'), event['town']
            transcription = '<br>'.join([first, 'Repeating ' + repeat])
        else:
            transcription = event['transcription'], event['town']

        payload = {
            'datetime': time,
            'responding': responding,
            'vip_word_color': vip_word_color,
            'transcription': Markup(transcription),
            'event': event,
        }

        if event['address'] and event['town']:
            full_address = f"{event['address']}, {event['town']}, NJ"
            gmaps_url = f'https://www.google.com/maps/place/{quote_plus(full_address)}/data=!3m1!1e3'
            payload['full_address'] = full_address
            payload['gmaps_url'] = gmaps_url

        events.append(payload)

    return render_template('index.html', events=events, counties=counties, request=request)


@app.route('/stations')
def stations():
    database = dataset.connect(config['alerts_database'])
    event_table = database['scanner']

    county_station = collections.defaultdict(set)
    for event in event_table.all():
        for station in event['responding'].split(','):
            county_station[event['county']].add(station.strip())

    for county in county_station:
        county_station[county] = sorted(county_station[county])

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
        county_towns[county] = sorted(county_towns[county])

    return render_template('towns.html', county_towns=county_towns, counties=counties)


@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'favicon.ico', mimetype='image/vnd.microsoft.icon')
