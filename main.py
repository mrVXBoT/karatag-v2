from config import sudo,client  ,token,delay,delay1

import os, configparser, config, ast
from importlib import import_module
import traceback


class Loader:
    def __init__(self, plugins : list = [i.split('.py')[0] for i in os.listdir('plugs') if i.endswith('.py')] , exclude : list = list()):
        self.plugins = list(set(plugins).difference(set(exclude)))
        print(self.plugins)

    def count(self, file):
        with open('plugs/{}.py'.format(file), encoding='utf-8') as f:
            tree = ast.parse(f.read())
            number = sum(isinstance(exp, ast.FunctionDef) for exp in tree.body)

            return number

    def config(self):
        for plugin in self.plugins:
            try:
                import_module('plugs.{}'.format(plugin))
                print('successfully imported < {} > module  .  {}  functions'.format(plugin, self.count(plugin)))
            except Exception as e:
                exc = traceback.format_exc() 
                print(exc)

    def load(self):
        self.config()
        print('Client started')
        client.start(bot_token=token)
        client.run_until_disconnected()

p = Loader()
p.load()
