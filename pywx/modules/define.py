import json
from . import base
from registry import register
import os


@register(commands=['define','what', "what's"])
class Acronym(base.Command):
    template = u"""{{ acronym|nc }}: {{ definition }}"""

    def context(self, msg):
        payload = {}
        acronym_file = os.path.join(os.path.abspath(os.path.dirname(__file__)), '..', 'acro.json')
        acronyms = json.load(open(acronym_file))
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
