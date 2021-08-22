#!/usr/bin/env python3
import os
import logging
import argparse

from enviroplus_api import get_temperature, get_humidity, get_pressure, get_light, get_gas, get_particulates

logging.basicConfig(
    format='%(asctime)s.%(msecs)03d %(levelname)-8s %(message)s',
    level=logging.INFO,
    handlers=[logging.FileHandler("enviroplus_exporter.log"),
              logging.StreamHandler()],
    datefmt='%Y-%m-%d %H:%M:%S')

logging.info("""enviroplus_api_test.py - Expose readings from the Enviro+ sensor by Pimoroni

Press Ctrl+C to exit!

""")

def str_to_bool(value):
    if value.lower() in {'false', 'f', '0', 'no', 'n'}:
        return False
    elif value.lower() in {'true', 't', '1', 'yes', 'y'}:
        return True
    raise ValueError('{} is not a valid boolean value'.format(value))

# Get env var for temperature factor
ENVIROPLUS_FACTOR = float(os.getenv('ENVIROPLUS_FACTOR', 0)) or False

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("-f", "--factor", metavar='FACTOR', type=float, help="The compensation factor to get better temperature results when the Enviro+ pHAT is too close to the Raspberry Pi board")
    parser.add_argument("-e", "--enviro", metavar='ENVIRO', type=str_to_bool, help="Device is an Enviro (not Enviro+) so don't fetch data from gas and particulate sensors as they don't exist")
    args = parser.parse_args()

    factor = args.factor or ENVIROPLUS_FACTOR
    if factor:
        logging.info("Using compensating algorithm (factor={}) to account for heat leakage from Raspberry Pi board".format(factor))

    while True:
        logging.info(get_temperature(factor))
        logging.info(get_pressure())
        logging.info(get_humidity())
        logging.info(get_light())
        logging.info(get_gas())
        logging.info(get_particulates())