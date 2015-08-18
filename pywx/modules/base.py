# -*- coding: utf-8 -*- #
import functools
import datetime
import re
import logging
import argparse
from jinja2 import Environment

max_msg_len = 375 #USE CONFIG VALUE

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
    return u"{bold}{color_code}{value}{nulled}{bold}".format(**locals())


class ArgumentError(Exception):
    pass

class NoMessage(Exception):
    pass


class IRCArgumentParser(argparse.ArgumentParser):
    def parse_args(self, msg):
        self.msg = msg
        args = self.msg['args'].split()
        return super(IRCArgumentParser, self).parse_args(args)

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

    def __init__(self, config):
        self.config = config
        self.environment = Environment()
        self.load_filters()

    def load_filters(self):
        self.environment.filters['c'] = irc_color
        self.environment.filters['tc'] = lambda v: irc_color(v, 'royal')
        self.environment.filters['nc'] = lambda v: irc_color(v, 'orange')

    def parse_args(self, msg):
        return msg

    def run(self, msg=''):
        template = self.environment.from_string(self.template)
        try:
            context = self.context(msg)
            reply = template.render(context)
        except NoMessage, e:
            return []
        except ArgumentError, e:
            return [e.message]
        except Exception, e:
            logging.exception(e)
            return []

        if not reply:
            return []

        #clean up formatting
        reply = re.sub('\n', '', reply)
        reply = re.sub('\s+', ' ', reply)
        reply = re.sub('^\s', '', reply)
        reply = re.sub('\s$', '', reply)
        if datetime.date.today().month == 10 and datetime.date.today().day == 22:
            #CAPS LOCK DAY
            reply = reply.upper()

        lines = []
        line = []
        for word in reply.split(' '):
            line.append(word)
            if sum(map(len, line)) > self.config.get('max_msg_length', 1000):
                lines.append(' '.join(line[:-1]))
                line = [word]
        lines.append(' '.join(line))
        return lines

