import json
import os
import re
import sys
from urllib.parse import quote_plus

import dataset
from flask import Flask, request
from jinja2 import Environment

try:
    config = json.load(open('data/local_config.json', encoding='utf-8'))
    config['pywx_path'] = os.path.dirname(os.path.abspath(__file__))
except ImportError:
    print('cant import local_config.py')
    sys.exit()


def irc_color(value, color):
    return f'<span style="color: {color};">{value}</span>'


def highlight(text, phrase):
    if phrase:
        return text.replace(phrase, irc_color(phrase, '#b8ecf2'))
    return text


repeating_regex = re.compile(r"(?P<first>.*)(Repeating|repeating|Paging)[\s.,]+(?P<repeat>.*)")


def townsplit(text, town):
    if town and town in text:
        index = text.index(town)
        return text[index + len(town):].lstrip(',').lstrip('.').strip()
    return text


important_stations = ['45fire', '46fire', 'sbes', 'southbranch']
very_important_words = ['studer', 'sunrise', 'austin hill', 'foundations', 'apollo', 'foxfire', 'river bend', 'grayrock', 'greyrock', 'beaver', 'lower west']
important_words = ['clinton', 'annandale', 'school']


app = Flask(__name__)


@app.route("/")
def list():
    database = dataset.connect(config['alerts_database'])
    event_table = database['scanner']

    environment = Environment()
    environment.filters['c'] = irc_color
    environment.filters['tc'] = lambda v: irc_color(v, 'royal')
    environment.filters['nc'] = lambda v: irc_color(v, '#fa7516')
    environment.filters['highlight'] = highlight

    event_query = []
    if request.args.get('id'):
        event_query = event_table.find(id=request.args['id'])
    elif request.args.get('search'):
        event_query = event_table.find(transcription={'ilike': f'%{request.args["search"]}%'}, is_transcribed=True, order_by=['-datetime'], _limit=100)
    elif request.args.get('station'):
        event_query = event_table.find(responding={'ilike': f'%{request.args["station"]}%'}, is_transcribed=True, order_by=['-datetime'], _limit=100)
    else:
        event_query = event_table.find(is_transcribed=True, order_by=['-datetime'], _limit=100)

    events = []
    for event in event_query:
        time = event['datetime'].strftime('%m/%d %-I:%M%p')
        responding = sorted(event['responding'].split(','))
        station_color = 'red' if any([station in event['responding'].lower() for station in important_stations]) else '#fa7516'
        vip_word_color = '#fa7516' if any([word in event['transcription'].lower() for word in important_words if word]) else 'royal'
        vip_word_color = 'red' if any([word in event['transcription'].lower() for word in very_important_words if word]) else vip_word_color

        repeat_search = repeating_regex.search(event['transcription'])
        if repeat_search:
            first = townsplit(repeat_search.group('first'), event['town'])
            repeat = townsplit(repeat_search.group('repeat'), event['town'])
            transcription = '<br>'.join([first, 'Repeating ' + repeat])
        else:
            transcription = townsplit(event['transcription'], event['town'])

        payload = {
            'datetime': time,
            'responding': responding,
            'vip_word_color': vip_word_color,
            'transcription': transcription,
            'station_color': station_color,
            'event': event,
        }

        if event['address'] and event['town']:
            full_address = f"{event['address']}, {event['town']}, NJ"
            gmaps_url = f'https://www.google.com/maps/place/{quote_plus(full_address)}/data=!3m1!1e3'
            payload['full_address'] = full_address
            payload['gmaps_url'] = gmaps_url

        events.append(payload)

    template = environment.from_string(open('templates/index.html').read())
    reply = template.render({'events': events})

    return reply


if __name__ == '__main__':
    print(list())
