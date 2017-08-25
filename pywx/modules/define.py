import json
from . import base
from registry import register


@register(commands=['define','what', "what's"])
class SpaceWeather(base.Command):
    template = u"""{{ acronym|nc }}: {{ definition }}"""

    def context(self, msg):
        payload = {}
        acronyms = json.load(open('./acro.json'))
        word = msg['args']

        if word[:3] == 'is ':
            word = word[3:]

        word = word.strip().strip('?').upper()

        if word in acronyms:
            payload['acronym'] = word
            payload['definition'] = acronyms[word]
        else:
            raise base.NoMessage

        return payload
