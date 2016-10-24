import configparser
import os

config = configparser.ConfigParser()

config_file = os.path.join( 
        os.path.expanduser("~"),
        '.config',
        'camerasync', 
        'config.ini')

if not os.path.isfile(config_file):
    config_file = 'config.ini'

config.read(config_file)

if not config.sections():
    raise Exception("Missing configuration file!")


FT_RAW = config['filetypes']['raw'].split()
FT_IMG = config['filetypes']['img'].split() + FT_RAW

def get_path(name):
    return config['paths'][name]

def get_tmos():
    tmos = []
    for section in config.sections():
        if section.startswith('pfstmo_'):
            tmos.append(section)
    return tmos

def get_tmo_options(tmo):
    return config[tmo]

def get_exe_args(exe):
    if not 'args' in config[exe]:
        return []
    return config[exe]['args'].split()

def get_output_options():
    return config['output']
