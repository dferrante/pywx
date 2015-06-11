#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pythabot
import sys
from modules import *

#from IPython.core import ultratb
#sys.excepthook = ultratb.FormattedTB(mode='Verbose', color_scheme='Linux', call_pdb=1)

try:
    from local_config import config
except ImportError, e:
    log.error('missing local_config.py')
    sys.exit()

if __name__ == '__main__':
    reg = registry.registry
    reg.load_modules(config)

    bot = pythabot.Pythabot(config, reg)
    bot.connect()
    bot.listen()
