# -*- coding: utf-8 -*- #
import argparse
import datetime
import logging
import re

from jinja2 import Environment

MAX_MSG_LEN = 375 #USE CONFIG VALUE

cmap = {
    'black': '\x0301',
    'navy': '\x0302',
    'maroon': '\x0305',
    'green': '\x0303',
    'grey': '\x0314',
    'royal': '\x0312',
    'aqua': '\x0311',
    'lime': '\x0309',
    'silver': '\x0315',
    'orange': '\x0307',
    'pink': '\x0313',
    'purple': '\x0306',
    'red': '\x0304',
    'teal': '\x0310',
    'white': '\x0300',
    'yellow': '\x0308',
    'null': '\x03',
    'reset': '\x0F',
    'bold': '\x02',
    'italic': '\x1D',
    'underline': '\x1F',
}


def irc_color(value, color, nulled=True, bold=False):
    color_code = cmap.get(color, '')
    nulled = cmap['null'] if nulled else ''
    bold = cmap['bold'] if bold else ''
    return f"{bold}{color_code}{value}{nulled}{bold}"


class ArgumentError(Exception):
    pass


class NoMessage(Exception):
    pass


class IRCArgumentParser(argparse.ArgumentParser):
    msg = None

    def parse_args(self, args=None, namespace=None):
        self.msg = args
        args = self.msg['args'].split()
        return super().parse_args(args, namespace)

    def error(self, message):
        raise ArgumentError(message)


class ParserCommand(object):
    def __init__(self, config):
        self.config = config

    def parse(self, msg):
        raise NotImplementedError


class Command(object):
    permission = "all"
    private_only = False
    template = None

    def __init__(self, config):
        self.config = config
        self.environment = Environment()
        self.load_filters()

    def load_filters(self):
        self.environment.filters['c'] = irc_color
        self.environment.filters['tc'] = lambda v: irc_color(v, 'royal')
        self.environment.filters['nc'] = lambda v: irc_color(v, 'orange')

    def context(self, msg): # pylint: disable=unused-argument
        return {}

    def parse_args(self, msg):
        return msg

    def run(self, msg=''):
        try:
            context = self.context(msg)
            template = self.environment.from_string(self.template)
            reply = template.render(context)
        except NoMessage:
            return []
        except ArgumentError as exc:
            return [str(exc)]
        except Exception as exc: # pylint: disable=broad-except
            logging.exception(exc)
            return []

        if not reply:
            return []

        #clean up formatting
        reply = re.sub(r'\n', '', reply)
        reply = re.sub(r'\s+', ' ', reply)
        reply = re.sub(r'^\s', '', reply)
        reply = re.sub(r'\s$', '', reply)
        if datetime.date.today().month == 10 and datetime.date.today().day == 22:
            #CAPS LOCK DAY
            reply = reply.upper()

        lines = []
        line = []
        for word in reply.split(' '):
            line.append(word)
            if sum(map(len, line)) > self.config.get('MAX_MSG_LENgth', 1000):
                lines.append(' '.join(line[:-1]))
                line = [word]
        lines.append(' '.join(line))
        return lines
