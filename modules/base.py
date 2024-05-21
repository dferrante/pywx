# -*- coding: utf-8 -*- #
import argparse
import logging
import re

from jinja2 import Environment

MAX_MSG_LEN = 451

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
colors = [c for c in cmap.keys() if c not in ['null', 'reset', 'bold', 'italic', 'underline']]


def irc_color(value, color, nulled=True, bold=False, italics=False, reset=False, underline=False):
    color_code = cmap.get(color, '')
    nulled = cmap['null'] if nulled else ''
    bold = cmap['bold'] if bold else ''
    italics = cmap['italic'] if italics else ''
    reset = cmap['reset'] if reset else ''
    underline = cmap['underline'] if underline else ''
    if not color_code:
        nulled = ""
    return f"{bold}{italics}{underline}{color_code}{value}{nulled}{reset}{bold}{italics}{underline}"


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
    multiline = False

    def __init__(self, config):
        self.config = config

    def parse(self, msg):
        raise NotImplementedError


class Command(object):
    permission = "all"
    private_only = False
    template = None
    multiline = False
    max_msg_length = MAX_MSG_LEN

    def __init__(self, config):
        self.config = config
        self.environment = Environment(autoescape=True)
        self.max_msg_length = self.config.get('max_msg_length', MAX_MSG_LEN)
        self.load_filters()

    def load_filters(self):
        self.environment = Environment(autoescape=True)
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

        if not self.multiline:
            reply = re.sub(r'\s+', ' ', reply)
            reply = reply.strip()
            reply = re.sub(r'\n', '', reply)
            lines = []
            line = []
            for word in reply.split(' '):
                line.append(word)
                if len(' '.join(line)) > self.max_msg_length:
                    lines.append(' '.join(line[:-1]))
                    line = [word]
            lines.append(' '.join(line))
        else:
            lines = []
            line_lines = reply.split('\n')
            for reply in line_lines:
                reply = re.sub(r'\s+', ' ', reply)
                reply = reply.strip()
                line = []
                for word in reply.split(' '):
                    line.append(word)
                    if len(' '.join(line)) > self.max_msg_length:
                        lines.append(' '.join(line[:-1]))
                        line = [word]
                lines.append(' '.join(line))

        return lines
