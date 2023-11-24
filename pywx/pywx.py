#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import os
import sys

from pythabot import Pythabot
from modules import registry


if __name__ == '__main__':
    try:
        config = json.load(open('/data/local_config.json', encoding='utf-8'))
        config['pywx_path'] = os.path.dirname(os.path.abspath(__file__))
    except ImportError:
        print('cant import local_config.py')
        sys.exit()

    reg = registry.registry
    reg.load_modules(config)

    bot = Pythabot(config, reg)
    bot.connect()
    bot.listen()
