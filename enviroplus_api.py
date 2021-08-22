#!/usr/bin/env python3
import time
import logging
import subprocess

from bme280 import BME280
from enviroplus import gas
from pms5003 import PMS5003, ReadTimeoutError as pmsReadTimeoutError

try:
    from smbus2 import SMBus
except ImportError:
    from smbus import SMBus

try:
    # Transitional fix for breaking change in LTR559
    from ltr559 import LTR559
    ltr559 = LTR559()
except ImportError:
    import ltr559

logging.basicConfig(
    format='%(asctime)s.%(msecs)03d %(levelname)-8s %(message)s',
    level=logging.INFO,
    handlers=[logging.FileHandler("enviroplus_exporter.log"),
              logging.StreamHandler()],
    datefmt='%Y-%m-%d %H:%M:%S')

bus = SMBus(1)
bme280 = BME280(i2c_dev=bus)
pms5003 = PMS5003()

# Sometimes the sensors can't be read. Resetting the i2c 
def reset_i2c():
    subprocess.run(['i2cdetect', '-y', '1'])
    time.sleep(2)


# Get the temperature of the CPU for compensation
def get_cpu_temperature():
    with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
        temp = f.read()
        temp = int(temp) / 1000.0
    return temp

def get_temperature(factor):
    """Get temperature from the weather sensor"""
    # Tuning factor for compensation. Decrease this number to adjust the
    # temperature down, and increase to adjust up
    raw_temp = bme280.get_temperature()

    if factor:
        cpu_temps = [get_cpu_temperature()] * 5
        cpu_temp = get_cpu_temperature()
        # Smooth out with some averaging to decrease jitter
        cpu_temps = cpu_temps[1:] + [cpu_temp]
        avg_cpu_temp = sum(cpu_temps) / float(len(cpu_temps))
        temperature = raw_temp - ((avg_cpu_temp - raw_temp) / factor)
    else:
        temperature = raw_temp

    return temperature

def get_pressure():
    """Get pressure from the weather sensor"""
    try:
        pressure = bme280.get_pressure()
        return pressure
    except IOError:
        logging.error("Could not get pressure readings. Resetting i2c.")
        reset_i2c()

def get_humidity():
    """Get humidity from the weather sensor"""
    try:
        humidity = bme280.get_humidity()
        return humidity
    except IOError:
        logging.error("Could not get humidity readings. Resetting i2c.")
        reset_i2c()

def get_gas():
    """Get all gas readings"""
    try:
        readings = gas.read_all()
        return readings
    except IOError:
        logging.error("Could not get gas readings. Resetting i2c.")
        reset_i2c()

def get_light():
    """Get all light readings"""
    try:
        lux = ltr559.get_lux()
        prox = ltr559.get_proximity()
        return { "lux": lux, "prox": prox }
    except IOError:
        logging.error("Could not get lux and proximity readings. Resetting i2c.")
        reset_i2c()

def get_particulates():
    """Get the particulate matter readings"""
    try:
        pms_data = pms5003.read()
    except pmsReadTimeoutError:
        logging.warning("Failed to read PMS5003")
    except IOError:
        logging.error("Could not get particulate matter readings. Resetting i2c.")
        reset_i2c()
    else:
        return pms_data