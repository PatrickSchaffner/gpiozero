# vim: set fileencoding=utf-8:
#
# GPIO Zero: a library for controlling the Raspberry Pi's GPIO pins
#
# SPDX-License-Identifier: BSD-3-Clause

import os
import warnings
from pathlib import Path
from threading import Event

import pytest

from gpiozero.internal_devices import HumidityTemperatureSensor
from gpiozero.exc import (
    HumidityTemperatureSensorError,
    HumidityTemperatureSensorNoResponse,
)


def make_device(parent, subdir='dev0', name='dht11@1b',
                temp='23400', humidity='61200'):
    """Create a fake IIO device directory and return its path as a str."""
    d = Path(parent) / subdir
    d.mkdir()
    (d / 'name').write_text(name)
    (d / 'in_temp_input').write_text(temp)
    (d / 'in_humidityrelative_input').write_text(humidity)
    return str(d)


def test_explicit_device_basic_read(tmp_path, mock_factory):
    device = make_device(tmp_path, temp='23400', humidity='61200')
    with HumidityTemperatureSensor(device=device) as s:
        assert pytest.approx(s.temperature, abs=0.01) == 23.4
        assert pytest.approx(s.humidity, abs=0.01) == 61.2


def test_negative_temperature(tmp_path, mock_factory):
    device = make_device(tmp_path, temp='-10500', humidity='80000')
    with HumidityTemperatureSensor(device=device) as s:
        assert pytest.approx(s.temperature, abs=0.01) == -10.5
        assert pytest.approx(s.humidity, abs=0.01) == 80.0


def test_reading_namedtuple(tmp_path, mock_factory):
    device = make_device(tmp_path, temp='22000', humidity='55000')
    with HumidityTemperatureSensor(device=device) as s:
        r = s.reading
        assert pytest.approx(r.temperature, abs=0.01) == 22.0
        assert pytest.approx(r.humidity, abs=0.01) == 55.0


def test_caching_within_min_interval(tmp_path, mock_factory):
    device = make_device(tmp_path, temp='20000')
    with HumidityTemperatureSensor(device=device, min_interval=100) as s:
        assert s.temperature == 20.0
        (Path(device) / 'in_temp_input').write_text('25000')
        assert s.temperature == 20.0          # cached: min_interval not elapsed
        s._last_read_tick = None              # force a fresh read
        assert s.temperature == 25.0


def test_device_int_raises_typeerror(tmp_path, mock_factory):
    with pytest.raises(TypeError):
        HumidityTemperatureSensor(device=27)


def test_invalid_active_measure(tmp_path, mock_factory):
    device = make_device(tmp_path)
    with pytest.raises(ValueError):
        HumidityTemperatureSensor(device=device, active_measure='pressure')


def test_invalid_temp_range(tmp_path, mock_factory):
    device = make_device(tmp_path)
    with pytest.raises(ValueError):
        HumidityTemperatureSensor(device=device, min_temp=80, max_temp=-40)


def test_invalid_humidity_range(tmp_path, mock_factory):
    device = make_device(tmp_path)
    with pytest.raises(ValueError):
        HumidityTemperatureSensor(device=device, min_humidity=50,
                                  max_humidity=50)


def test_invalid_threshold(tmp_path, mock_factory):
    device = make_device(tmp_path)
    with pytest.raises(ValueError):
        HumidityTemperatureSensor(device=device, threshold=1.5)
