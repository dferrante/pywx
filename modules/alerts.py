import re

import dataset

from . import base
from .registry import register, register_periodic


def highlight(text, phrase):
    if phrase:
        return text.replace(phrase, base.irc_color(phrase, 'aqua'))
    return text


class Scanner(base.Command):
    multiline = True
    template = """{% if not no_line_break %}-------------{% endif %}
        {{ datetime|c('teal') }} - {{ event['county']|c(county_color) }} - {{ responding|c(station_color) }}{% if location_count > 1 %} - {{ location_count|c('green') }}{% endif %} - {{ event.id|c('grey') }}
        {% if event['gpt_place'] %}{{ event['gpt_place']|c(vip_word_color) }} - {% endif %}{% if event['gmaps_address'] %} {{ event['gmaps_address']|c(vip_word_color) }} {% elif full_address %} {{ full_address|c(vip_word_color) }} {% elif event.town %} {{ event.town|c(vip_word_color) }} {% elif event.address %} {{ event.address|c(vip_word_color) }} {% endif %} - {{ scanner_url }}
        {{ incident_type|c('aqua') }}: {{ incident_details }}"""

    repeating_regex = re.compile(r"(?P<first>.*)(Repeating|Paging|Again|repeating|paging|again)[\s.,]+(?P<repeat>.*)")

    def __init__(self, config):
        super().__init__(config)
        self.important_stations = self.config.get('important_stations', [])
        self.very_important_words = self.config.get('very_important_words', [])
        self.important_words = self.config.get('important_words', [])

    def load_filters(self):
        super().load_filters()
        self.environment.filters['highlight'] = highlight

    def townsplit(self, text, town):
        if town and town in text:
            index = text.index(town)
            return text[index + len(town):].lstrip(',').lstrip('.').strip()
        return text

    def location_count(self, event):
        if event['gmaps_location_type'] == 'ROOFTOP':
            database = dataset.connect(self.config['alerts_database'])
            event_table = database['scanner']
            location_count = event_table.count(gmaps_latitude=event['gmaps_latitude'], gmaps_longitude=event['gmaps_longitude'])
            database.close()
        else:
            location_count = 0
        return location_count

    def event_context(self, event):
        time = event['datetime'].strftime('%-I:%M%p')
        responding = ' - '.join([unit for unit in event['responding'].split(',')])
        if event['county'] == 'hunterdon':
            county_color = 'pink'
            station_color = 'red' if any([station in event['responding'].lower() for station in self.important_stations]) else 'orange'
            vip_word_color = 'yellow' if any([word in event['transcription'].lower() for word in self.important_words if word]) else 'teal'
            vip_word_color = 'red' if any([word in event['transcription'].lower() for word in self.very_important_words if word]) else vip_word_color
        else:
            county_color = 'orange'
            station_color = 'orange'
            vip_word_color = 'teal'

        repeat_search = self.repeating_regex.search(event['transcription'])
        if repeat_search:
            transcription = '\n'.join([repeat_search.group('first'), 'Repeating ' + repeat_search.group('repeat')])
        else:
            transcription = event['transcription']

        age_and_gender = ''
        if event['gpt_incident_details']:
            if event['gpt_age'] and event['gpt_age'] not in event['gpt_incident_details']:
                if event['gpt_age'].isdigit():
                    age_and_gender += f"{event['gpt_age']}yo "
                else:
                    age_and_gender += f"{event['gpt_age']} "
            if event['gpt_gender'] and event['gpt_gender'] not in event['gpt_incident_details']:
                age_and_gender += f"{event['gpt_gender']}"
            if age_and_gender:
                age_and_gender += " - "

            subtype = f"/{event['gpt_incident_subtype']}" if event['gpt_incident_subtype'] else ''
            incident_type = f"{event['gpt_incident_type']}{subtype}"
            incident_details = f"{age_and_gender}{event['gpt_incident_details']}"
        else:
            subtype = f"/{event['gpt_incident_subtype']}" if event['gpt_incident_subtype'] else ''
            incident_type = f"{event['gpt_incident_type']}{subtype}"
            incident_details = ""

        payload = {
            'datetime': time,
            'responding': responding,
            'vip_word_color': vip_word_color,
            'transcription': transcription,
            'station_color': station_color,
            'county_color': county_color,
            'event': event,
            'location_count': self.location_count(event),
            'incident_type': incident_type,
            'incident_details': incident_details,
            'scanner_url': f"https://{self.config['scanner_base_url']}/?id={event['id']}"
        }

        event['gmaps_address'] = re.sub(r',\s*NJ\s*(\d{5})?,\s*USA$', '', event['gmaps_address'])
        if event['address'] and event['town']:
            full_address = f"{event['address']}, {event['town']}, NJ"
            payload['full_address'] = full_address

        return payload


@register_periodic('scanner', 30, chans=['#scanner'])
class ScannerAlerter(Scanner):
    def context(self, msg):
        database = dataset.connect(self.config['alerts_database'])
        event_table = database['scanner']

        event = event_table.find_one(is_irc_notified=False, is_transcribed=True, is_parsed=True, order_by=['datetime'])
        if event:
            event['is_irc_notified'] = True
            event_table.update(dict(event), ['id'])
            database.close()
            return self.event_context(event)
        database.close()
        raise base.NoMessage


@register(commands=['lastalert'])
class LastScanner(Scanner):
    def parse_args(self, msg):
        parser = base.IRCArgumentParser()
        parser.add_argument('id', type=str, default=None, nargs='*')
        return parser.parse_args(msg)

    def context(self, msg):
        database = dataset.connect(self.config['alerts_database'])
        event_table = database['scanner']

        args = self.parse_args(msg)
        if args.id:
            event = event_table.find_one(id=int(args.id[0]))
            if not event:
                database.close()
                raise base.ArgumentError('Event not found')
        else:
            event = event_table.find_one(is_transcribed=True, is_parsed=True, order_by=['-datetime'])
        database.close()
        context = self.event_context(event)
        context['no_line_break'] = True
        return context
