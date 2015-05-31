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

    #print reg.commands['wf'].run({'ident': 'mach5', 'command': 'wf', 'sender': 'machasdf5', 'msg': 'wf 08809',
                                  #'chan': '#wax', 'args': '08809', 'mask': 'cloak-CC9475C7.hsd1.nj.comcast.net'})
    #print reg.commands['alerts'].run({'sender': 'mach5', 'args': ['little rock']})
    #print reg.commands['alert'].run({'sender': 'mach5', 'args': ['1',]})

    #print reg.parsers[0].parse({'sender': 'mach5', 'msg': 'https://i.imgur.com/vhxF6tn.gifv'})

    bot = pythabot.Pythabot(config, reg)
    bot.connect()
    bot.listen()
