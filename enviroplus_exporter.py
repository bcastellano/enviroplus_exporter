#!/usr/bin/env python3
import os
import requests
import time
import logging
import argparse
from threading import Thread

from prometheus_client import start_http_server, Gauge, Histogram

from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

from enviroplus_api import get_temperature, get_humidity, get_pressure, get_light, get_gas, get_particulates

logging.basicConfig(
    format='%(asctime)s.%(msecs)03d %(levelname)-8s %(message)s',
    level=logging.INFO,
    handlers=[logging.FileHandler("enviroplus_exporter.log"),
              logging.StreamHandler()],
    datefmt='%Y-%m-%d %H:%M:%S')

logging.info("""enviroplus_exporter.py - Expose readings from the Enviro+ sensor by Pimoroni in Prometheus format

Press Ctrl+C to exit!

""")

DEBUG = os.getenv('DEBUG', 'false') == 'true'

TEMPERATURE = Gauge('temperature','Temperature measured (*C)')
PRESSURE = Gauge('pressure','Pressure measured (hPa)')
HUMIDITY = Gauge('humidity','Relative humidity measured (%)')
OXIDISING = Gauge('oxidising','Mostly nitrogen dioxide but could include NO and Hydrogen (Ohms)')
REDUCING = Gauge('reducing', 'Mostly carbon monoxide but could include H2S, Ammonia, Ethanol, Hydrogen, Methane, Propane, Iso-butane (Ohms)')
NH3 = Gauge('NH3', 'mostly Ammonia but could also include Hydrogen, Ethanol, Propane, Iso-butane (Ohms)') 
LUX = Gauge('lux', 'current ambient light level (lux)')
PROXIMITY = Gauge('proximity', 'proximity, with larger numbers being closer proximity and vice versa')
PM1 = Gauge('PM1', 'Particulate Matter of diameter less than 1 micron. Measured in micrograms per cubic metre (ug/m3)')
PM25 = Gauge('PM25', 'Particulate Matter of diameter less than 2.5 microns. Measured in micrograms per cubic metre (ug/m3)')
PM10 = Gauge('PM10', 'Particulate Matter of diameter less than 10 microns. Measured in micrograms per cubic metre (ug/m3)')

OXIDISING_HIST = Histogram('oxidising_measurements', 'Histogram of oxidising measurements', buckets=(0, 10000, 15000, 20000, 25000, 30000, 35000, 40000, 45000, 50000, 55000, 60000, 65000, 70000, 75000, 80000, 85000, 90000, 100000))
REDUCING_HIST = Histogram('reducing_measurements', 'Histogram of reducing measurements', buckets=(0, 100000, 200000, 300000, 400000, 500000, 600000, 700000, 800000, 900000, 1000000, 1100000, 1200000, 1300000, 1400000, 1500000))
NH3_HIST = Histogram('nh3_measurements', 'Histogram of nh3 measurements', buckets=(0, 10000, 110000, 210000, 310000, 410000, 510000, 610000, 710000, 810000, 910000, 1010000, 1110000, 1210000, 1310000, 1410000, 1510000, 1610000, 1710000, 1810000, 1910000, 2000000))

PM1_HIST = Histogram('pm1_measurements', 'Histogram of Particulate Matter of diameter less than 1 micron measurements', buckets=(0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 100))
PM25_HIST = Histogram('pm25_measurements', 'Histogram of Particulate Matter of diameter less than 2.5 micron measurements', buckets=(0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 100))
PM10_HIST = Histogram('pm10_measurements', 'Histogram of Particulate Matter of diameter less than 10 micron measurements', buckets=(0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 100))

# Setup InfluxDB
# You can generate an InfluxDB Token from the Tokens Tab in the InfluxDB Cloud UI
INFLUXDB_URL = os.getenv('INFLUXDB_URL', '')
INFLUXDB_TOKEN = os.getenv('INFLUXDB_TOKEN', '')
INFLUXDB_ORG_ID = os.getenv('INFLUXDB_ORG_ID', '')
INFLUXDB_BUCKET = os.getenv('INFLUXDB_BUCKET', '')
INFLUXDB_SENSOR_LOCATION = os.getenv('INFLUXDB_SENSOR_LOCATION', 'Adelaide')
INFLUXDB_TIME_BETWEEN_POSTS = int(os.getenv('INFLUXDB_TIME_BETWEEN_POSTS', '5'))
influxdb_client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG_ID)
influxdb_api = influxdb_client.write_api(write_options=SYNCHRONOUS)

# Setup Luftdaten
LUFTDATEN_TIME_BETWEEN_POSTS = int(os.getenv('LUFTDATEN_TIME_BETWEEN_POSTS', '30'))

# Get env var for temperature factor
ENVIROPLUS_FACTOR = float(os.getenv('ENVIROPLUS_FACTOR', 0)) or False

def read_temperature(factor):
    """Get temperature from the api"""
    temperature = get_temperature(factor)

    TEMPERATURE.set(temperature)   # Set to a given value

def read_pressure():
    """Get pressure from the api"""
    pressure = get_pressure()
    PRESSURE.set(pressure)

def read_humidity():
    """Get humidity from the api"""
    humidity = get_humidity()
    HUMIDITY.set(humidity)

def read_gas():
    """Get all gas readings"""
    readings = get_gas()

    OXIDISING.set(readings.oxidising)
    OXIDISING_HIST.observe(readings.oxidising)

    REDUCING.set(readings.reducing)
    REDUCING_HIST.observe(readings.reducing)

    NH3.set(readings.nh3)
    NH3_HIST.observe(readings.nh3)

def read_light():
    """Get all light readings"""
    light = get_light()
    LUX.set(light["lux"])
    PROXIMITY.set(light["prox"])

def read_particulates():
    """Get the particulate matter readings"""
    pms_data = get_particulates()
    
    PM1.set(pms_data.pm_ug_per_m3(1.0))
    PM25.set(pms_data.pm_ug_per_m3(2.5))
    PM10.set(pms_data.pm_ug_per_m3(10))

    PM1_HIST.observe(pms_data.pm_ug_per_m3(1.0))
    PM25_HIST.observe(pms_data.pm_ug_per_m3(2.5) - pms_data.pm_ug_per_m3(1.0))
    PM10_HIST.observe(pms_data.pm_ug_per_m3(10) - pms_data.pm_ug_per_m3(2.5))

def collect_all_data():
    """Collects all the data currently set"""
    sensor_data = {}
    sensor_data['temperature'] = TEMPERATURE.collect()[0].samples[0].value
    sensor_data['humidity'] = HUMIDITY.collect()[0].samples[0].value
    sensor_data['pressure'] = PRESSURE.collect()[0].samples[0].value
    sensor_data['oxidising'] = OXIDISING.collect()[0].samples[0].value
    sensor_data['reducing'] = REDUCING.collect()[0].samples[0].value
    sensor_data['nh3'] = NH3.collect()[0].samples[0].value
    sensor_data['lux'] = LUX.collect()[0].samples[0].value
    sensor_data['proximity'] = PROXIMITY.collect()[0].samples[0].value
    sensor_data['pm1'] = PM1.collect()[0].samples[0].value
    sensor_data['pm25'] = PM25.collect()[0].samples[0].value
    sensor_data['pm10'] = PM10.collect()[0].samples[0].value
    return sensor_data

def post_to_influxdb():
    """Post all sensor data to InfluxDB"""
    name = 'enviroplus'
    tag = ['location', 'adelaide']
    while True:
        time.sleep(INFLUXDB_TIME_BETWEEN_POSTS)
        data_points = []
        epoch_time_now = round(time.time())
        sensor_data = collect_all_data()
        for field_name in sensor_data:
            data_points.append(Point('enviroplus').tag('location', INFLUXDB_SENSOR_LOCATION).field(field_name, sensor_data[field_name]))
        try:
            influxdb_api.write(bucket=INFLUXDB_BUCKET, record=data_points)
            if DEBUG:
                logging.info('InfluxDB response: OK')
        except Exception as exception:
            logging.warning('Exception sending to InfluxDB: {}'.format(exception))

def post_to_luftdaten():
    """Post relevant sensor data to luftdaten.info"""
    """Code from: https://github.com/sepulworld/balena-environ-plus"""
    LUFTDATEN_SENSOR_UID = 'raspi-' + get_serial_number()
    while True:
        time.sleep(LUFTDATEN_TIME_BETWEEN_POSTS)
        sensor_data = collect_all_data()
        values = {}
        values["P2"] = sensor_data['pm25']
        values["P1"] = sensor_data['pm10']
        values["temperature"] = "{:.2f}".format(sensor_data['temperature'])
        values["pressure"] = "{:.2f}".format(sensor_data['pressure'] * 100)
        values["humidity"] = "{:.2f}".format(sensor_data['humidity'])
        pm_values = dict(i for i in values.items() if i[0].startswith('P'))
        temperature_values = dict(i for i in values.items() if not i[0].startswith('P'))
        try:
            response_pin_1 = requests.post('https://api.luftdaten.info/v1/push-sensor-data/',
                json={
                    "software_version": "enviro-plus 0.0.1",
                    "sensordatavalues": [{"value_type": key, "value": val} for
                                        key, val in pm_values.items()]
                },
                headers={
                    "X-PIN":    "1",
                    "X-Sensor": LUFTDATEN_SENSOR_UID,
                    "Content-Type": "application/json",
                    "cache-control": "no-cache"
                }
            )

            response_pin_11 = requests.post('https://api.luftdaten.info/v1/push-sensor-data/',
                    json={
                        "software_version": "enviro-plus 0.0.1",
                        "sensordatavalues": [{"value_type": key, "value": val} for
                                            key, val in temperature_values.items()]
                    },
                    headers={
                        "X-PIN":    "11",
                        "X-Sensor": LUFTDATEN_SENSOR_UID,
                        "Content-Type": "application/json",
                        "cache-control": "no-cache"
                    }
            )

            if response_pin_1.ok and response_pin_11.ok:
                if DEBUG:
                    logging.info('Luftdaten response: OK')
            else:
                logging.warning('Luftdaten response: Failed')
        except Exception as exception:
            logging.warning('Exception sending to Luftdaten: {}'.format(exception))

def get_serial_number():
    """Get Raspberry Pi serial number to use as LUFTDATEN_SENSOR_UID"""
    with open('/proc/cpuinfo', 'r') as f:
        for line in f:
            if line[0:6] == 'Serial':
                return str(line.split(":")[1].strip())

def str_to_bool(value):
    if value.lower() in {'false', 'f', '0', 'no', 'n'}:
        return False
    elif value.lower() in {'true', 't', '1', 'yes', 'y'}:
        return True
    raise ValueError('{} is not a valid boolean value'.format(value))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("-b", "--bind", metavar='ADDRESS', default='0.0.0.0', help="Specify alternate bind address [default: 0.0.0.0]")
    parser.add_argument("-p", "--port", metavar='PORT', default=8000, type=int, help="Specify alternate port [default: 8000]")
    parser.add_argument("-f", "--factor", metavar='FACTOR', type=float, help="The compensation factor to get better temperature results when the Enviro+ pHAT is too close to the Raspberry Pi board")
    parser.add_argument("-e", "--enviro", metavar='ENVIRO', type=str_to_bool, help="Device is an Enviro (not Enviro+) so don't fetch data from gas and particulate sensors as they don't exist")
    parser.add_argument("-d", "--debug", metavar='DEBUG', type=str_to_bool, help="Turns on more verbose logging, showing sensor output and post responses [default: false]")
    parser.add_argument("-i", "--influxdb", metavar='INFLUXDB', type=str_to_bool, default='false', help="Post sensor data to InfluxDB [default: false]")
    parser.add_argument("-l", "--luftdaten", metavar='LUFTDATEN', type=str_to_bool, default='false', help="Post sensor data to Luftdaten [default: false]")
    args = parser.parse_args()

    # Start up the server to expose the metrics.
    start_http_server(addr=args.bind, port=args.port)
    # Generate some requests.

    if args.debug:
        DEBUG = True

    factor = args.factor or ENVIROPLUS_FACTOR
    if factor:
        logging.info("Using compensating algorithm (factor={}) to account for heat leakage from Raspberry Pi board".format(factor))

    if args.influxdb:
        # Post to InfluxDB in another thread
        logging.info("Sensor data will be posted to InfluxDB every {} seconds".format(INFLUXDB_TIME_BETWEEN_POSTS))
        influx_thread = Thread(target=post_to_influxdb)
        influx_thread.start()

    if args.luftdaten:
        # Post to Luftdaten in another thread
        LUFTDATEN_SENSOR_UID = 'raspi-' + get_serial_number()
        logging.info("Sensor data will be posted to Luftdaten every {} seconds for the UID {}".format(LUFTDATEN_TIME_BETWEEN_POSTS, LUFTDATEN_SENSOR_UID))
        luftdaten_thread = Thread(target=post_to_luftdaten)
        luftdaten_thread.start()

    logging.info("Listening on http://{}:{}".format(args.bind, args.port))

    while True:
        read_temperature(factor)
        read_pressure()
        read_humidity()
        read_light()
        if not args.enviro:
            read_gas()
            read_particulates()
        if DEBUG:
            logging.info('Sensor data: {}'.format(collect_all_data()))
