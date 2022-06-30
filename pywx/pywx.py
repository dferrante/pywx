#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import json
import os
import sys

from pythabot import Pythabot
from modules import *

parser = argparse.ArgumentParser()
parser.add_argument("config_file", help="path to the config file")
args = parser.parse_args()


try:
    config = json.load(open(args.config_file, encoding='utf-8'))
    config['pywx_path'] = os.path.dirname(os.path.abspath(__file__))
except ImportError:
    print('cant import local_config.py')
    sys.exit()

if __name__ == '__main__':
    reg = registry.registry
    reg.load_modules(config)

    # print(reg.commands['lastquake'].run({'sender': 'bp', 'msg': 'lastquake', 'command': 'lastquake', 'args': '',}))
    # parsed_things = []
    # msg = {'msg': 'https://twitter.com/jbenton/status/1541888492443148293'}
    # for parser in reg.parsers:
    #     for line in parser.parse(msg):
    #         parsed_things.append(line)
    # for line in parsed_things:
    #     print(line)

    bot = Pythabot(config, reg)
    bot.connect()
    bot.listen()
