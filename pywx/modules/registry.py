import os
import sys

class Register(object):
    def __init__(self):
        self.commands = {}
        self.command_klasses = {}
        self.parsers = []
        self.parser_klasses = []
        self.periodic_tasks = []
        self.periodic_klasses = []

    def load_modules(self, config):
        for cls, cmds in self.command_klasses.iteritems():
            cmdcls = cls(config)
            for cmd in cmds:
                self.commands[cmd] = cmdcls

        self.parsers = [cls(config) for cls in self.parser_klasses]
        self.periodic_tasks = [cls(config) for cls in self.periodic_klasses]


registry = Register()

def register(commands=[]):
    def add_class(cmd):
        registry.command_klasses[cmd] = commands
        return cmd
    return add_class

def register_periodic(cls):
    registry.periodic_tasks.append(cls)
    return cls

def register_parser(cls):
    registry.parser_klasses.append(cls)
    return cls
