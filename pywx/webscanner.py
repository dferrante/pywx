import json
import os
import re
import sys
from urllib.parse import quote_plus

import dataset
from flask import Flask
from jinja2 import Environment

try:
    config = json.load(open('local_config.json', encoding='utf-8'))
    config['pywx_path'] = os.path.dirname(os.path.abspath(__file__))
except ImportError:
    print('cant import local_config.py')
    sys.exit()


def irc_color(value, color):
    return f'<span style="color: {color}; white-space: nowrap;">{value}</span>'


def highlight(text, phrase):
    if phrase:
        return text.replace(phrase, irc_color(phrase, 'aqua'))
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
def hello_world():
    database = dataset.connect(config['alerts_database'])
    event_table = database['scanner']

    environment = Environment()
    environment.filters['c'] = irc_color
    environment.filters['tc'] = lambda v: irc_color(v, 'royal')
    environment.filters['nc'] = lambda v: irc_color(v, 'orange')
    environment.filters['highlight'] = highlight

    events = []
    for event in event_table.find(is_transcribed=True, order_by=['-datetime'], _limit=100):
        time = event['datetime'].strftime('%-I:%M%p')
        responding = ' - '.join([unit for unit in event['responding'].split(',')])
        station_color = 'red' if any([station in event['responding'].lower() for station in important_stations]) else 'orange'
        vip_word_color = 'yellow' if any([word in event['transcription'].lower() for word in important_words if word]) else 'royal'
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
    print(hello_world())
