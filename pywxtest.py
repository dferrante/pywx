#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import os
import sys

from modules import registry


def test_command(command, args):
    lines = reg.commands[command].run({'sender': 'mach5', 'msg': f'{command} {args}', 'command': command, 'args': args})
    for line in lines:
        print('--')
        print(repr(line))


def test_periodic_command(config, command):
    lines = reg.periodic_tasks[command]['command'](config).run()
    for line in lines:
        print('--')
        print(repr(line))


def test_parser(msg):
    parsed_things = []
    msg = {'msg': msg}
    for parser in reg.parsers:
        for line in parser.parse(msg):
            parsed_things.append(line)
    for line in parsed_things:
        print('--')
        print(repr(line))


if __name__ == '__main__':
    try:
        config = json.load(open('data/local_config.json', encoding='utf-8'))
        config['pywx_path'] = os.path.dirname(os.path.abspath(__file__))
    except ImportError:
        print('cant import local_config.py')
        sys.exit()

    reg = registry.registry
    reg.load_modules(config)

    test_command('lastalert', '35169')
    # test_parser('https://twitter.com/UssamaMakdisi/status/1728055648280072598')
    # test_periodic_command(config, "scanner")
    # test_periodic_command(config, "scanner")
    # test_periodic_command(config, "scanner")
