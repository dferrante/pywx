#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pythabot
import os
import sys
import imp
import argparse
from modules import *

parser = argparse.ArgumentParser()
parser.add_argument("config_file", help="path to the config file")
args = parser.parse_args()


try:
    local_config = imp.load_source('local_config', args.config_file)
    config = local_config.config
    config['pywx_path'] = os.path.dirname(os.path.abspath(__file__))
except ImportError:
    log.error('missing local_config.py')
    sys.exit()

if __name__ == '__main__':
    reg = registry.registry
    reg.load_modules(config)

    # print(reg.commands['wxtime'].run(({'sender': 'mach5', 'args': '08809'})))
    # parsed_things = []
    # msg = {'msg': 'https://www.youtube.com/watch?v=_yncRe05nS0'}
    # for parser in reg.parsers:
    #     for line in parser.parse(msg):
    #         parsed_things.append(line)
    # for line in parsed_things:
    #     print(line)

    bot = pythabot.Pythabot(config, reg)
    bot.connect()
    bot.listen()
