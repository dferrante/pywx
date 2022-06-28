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

    print(reg.commands['hfx'].run(({'sender': 'mach5', 'args': '08809'})))

    # bot = pythabot.Pythabot(config, reg)
    # bot.connect()
    # bot.listen()
