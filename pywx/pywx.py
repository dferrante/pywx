#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import json
import os
import sys

from pythabot import Pythabot
from modules import registry


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("config_file", help="path to the config file")
    args = parser.parse_args()

    try:
        config = json.load(open(args.config_file, encoding='utf-8'))
        config['pywx_path'] = os.path.dirname(os.path.abspath(__file__))
    except ImportError:
        print('cant import local_config.py')
        sys.exit()

    reg = registry.registry
    reg.load_modules(config)

    bot = Pythabot(config, reg)
    bot.connect()
    bot.listen()
