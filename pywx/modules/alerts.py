import datetime
import re
from urllib.parse import quote_plus

import dataset

from . import base
from .registry import register, register_periodic

global LAST_ALERT
LAST_ALERT = None


class Scanner(base.Command):
    multiline = True
    template = """{{ datetime|c('royal') }}: Responding: [{{ responding|c(station_color) }}]
                    {% if full_address %} {{ full_address|c(vip_word_color) }} {{ gmaps_url }} {% elif event['town'] %} {{ event['town']|c(vip_word_color) }} {% elif event['address'] %} {{ event['address']|c(vip_word_color) }} {% endif %}
                    {{ transcription }}"""

    important_stations = ['45fire', '46fire', 'sbes']
    very_important_words = ['studer', 'sunrise', 'austin hill', 'foundations', 'apollo', 'foxfire', 'river bend', 'grayrock', 'greyrock', 'beaver', 'lower west']
    important_words = ['clinton', 'annandale', 'school']

    event_table = None

    def __init__(self, config):
        super().__init__(config)
        database = dataset.connect(config['alerts_database'])
        self.event_table = database['scanner']

    def event_context(self, event):
        time = event['datetime'].strftime('%-I:%M%p')
        responding = ' | '.join([unit for unit in event['responding'].split(',')])
        station_color = 'red' if any([station in event['responding'].lower() for station in self.important_stations]) else 'orange'
        vip_word_color = 'yellow' if any([word in event['transcription'].lower() for word in self.important_words]) else 'royal'
        vip_word_color = 'red' if any([word in event['transcription'].lower() for word in self.very_important_words]) else vip_word_color

        repeating_regex = re.compile(r"(?P<first>.*)(Repeating|repeating|Paging)[\s.,]+(?P<repeat>.*)")
        repeat_search = repeating_regex.search(event['transcription'])
        if repeat_search:
            transcription = '\n'.join([repeat_search.group('first'), 'Repeating ' + repeat_search.group('repeat')])
        else:
            transcription = event['transcription']

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
            gmaps_url = f'https://www.google.com/maps/place/{quote_plus(full_address)}'
            payload['full_address'] = full_address
            payload['gmaps_url'] = gmaps_url

        return payload


@register_periodic(30, chans=['#scanner'])
class ScannerAlerter(Scanner):
    def context(self, msg):
        global LAST_ALERT

        if LAST_ALERT is None:
            LAST_ALERT = datetime.datetime.now()

        event = self.event_table.find_one(datetime={'gt': LAST_ALERT}, is_transcribed=True, order_by=['datetime'])
        if event:
            LAST_ALERT = event['datetime']
            return self.event_context(event)
        raise base.NoMessage


@register(commands=['lastalert',])
class LastScanner(Scanner):
    def parse_args(self, msg):
        parser = base.IRCArgumentParser()
        parser.add_argument('id', type=str, default=None, nargs='*')
        return parser.parse_args(msg)

    def context(self, msg):
        args = self.parse_args(msg)
        if args.id:
            event = self.event_table.find_one(id=int(args.id[0]))
            if not event:
                raise base.ArgumentError('Event not found')
        else:
            event = self.event_table.find_one(is_transcribed=True, order_by=['-datetime'])
        return self.event_context(event)
