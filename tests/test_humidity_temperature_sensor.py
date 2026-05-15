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


def test_read_failure_warns_and_returns_none(tmp_path, mock_factory):
    device = make_device(tmp_path)
    # Replace in_temp_input with a directory: it still passes the existence
    # check, but io.open() on it raises OSError, simulating a kernel -EIO.
    temp_path = os.path.join(device, 'in_temp_input')
    os.remove(temp_path)
    os.mkdir(temp_path)
    with HumidityTemperatureSensor(device=device) as s:
        s._last_read_tick = None  # force a fresh read
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            assert s.temperature is None
        assert any(issubclass(rec.category,
                              HumidityTemperatureSensorNoResponse)
                   for rec in w)


def test_retry_succeeds_after_failures(tmp_path, mock_factory, monkeypatch):
    monkeypatch.setattr('gpiozero.internal_devices.sleep', lambda s: None)
    calls = []

    def fake_read_once(self):
        calls.append(1)
        if len(calls) < 3:
            raise OSError('simulated -EIO')
        return 22.2, 44.4

    monkeypatch.setattr(HumidityTemperatureSensor, '_read_once',
                        fake_read_once)
    device = make_device(tmp_path)
    with HumidityTemperatureSensor(device=device, retries=2) as s:
        assert s.temperature == 22.2
        assert s.humidity == 44.4
    assert len(calls) == 3


def test_autodiscovery_single_device(tmp_path, mock_factory, monkeypatch):
    make_device(tmp_path, subdir='iio_device_0')
    monkeypatch.setattr('gpiozero.internal_devices._IIO_DEVICES_ROOT',
                        str(tmp_path))
    with HumidityTemperatureSensor() as s:
        assert pytest.approx(s.temperature, abs=0.01) == 23.4


def test_autodiscovery_no_device(tmp_path, mock_factory, monkeypatch):
    # A non-dht11 IIO device should be ignored.
    make_device(tmp_path, subdir='iio_device_0', name='lsm9ds1_magn')
    monkeypatch.setattr('gpiozero.internal_devices._IIO_DEVICES_ROOT',
                        str(tmp_path))
    with pytest.raises(HumidityTemperatureSensorError):
        HumidityTemperatureSensor()


def test_autodiscovery_multiple_devices(tmp_path, mock_factory, monkeypatch):
    make_device(tmp_path, subdir='iio_device_0', name='dht11@1b')
    make_device(tmp_path, subdir='iio_device_1', name='dht11@4')
    monkeypatch.setattr('gpiozero.internal_devices._IIO_DEVICES_ROOT',
                        str(tmp_path))
    with pytest.raises(HumidityTemperatureSensorError):
        HumidityTemperatureSensor()


def test_discovery_by_pin(tmp_path, mock_factory, monkeypatch):
    make_device(tmp_path, subdir='iio_device_0', name='dht11@1b')  # GPIO 27
    make_device(tmp_path, subdir='iio_device_1', name='dht11@4')   # GPIO 4
    monkeypatch.setattr('gpiozero.internal_devices._IIO_DEVICES_ROOT',
                        str(tmp_path))
    with HumidityTemperatureSensor(4) as s:
        assert s._device_dir.endswith('iio_device_1')


def test_discovery_by_pin_not_found(tmp_path, mock_factory, monkeypatch):
    make_device(tmp_path, subdir='iio_device_0', name='dht11@1b')  # GPIO 27
    monkeypatch.setattr('gpiozero.internal_devices._IIO_DEVICES_ROOT',
                        str(tmp_path))
    with pytest.raises(HumidityTemperatureSensorError):
        HumidityTemperatureSensor(5)


def test_pin_verification_match(tmp_path, mock_factory):
    device = make_device(tmp_path, name='dht11@1b')  # 0x1b == 27
    with HumidityTemperatureSensor(27, device=device) as s:
        assert s.temperature == 23.4


def test_pin_verification_mismatch(tmp_path, mock_factory):
    device = make_device(tmp_path, name='dht11@1b')  # 0x1b == 27
    with pytest.raises(HumidityTemperatureSensorError):
        HumidityTemperatureSensor(4, device=device)


def test_value_normalises_temperature(tmp_path, mock_factory):
    # 20 C with range -40..80 -> (20 - -40) / (80 - -40) = 0.5
    device = make_device(tmp_path, temp='20000')
    with HumidityTemperatureSensor(device=device) as s:
        assert pytest.approx(s.value, abs=0.01) == 0.5


def test_active_measure_humidity(tmp_path, mock_factory):
    device = make_device(tmp_path, temp='25000', humidity='80000')
    with HumidityTemperatureSensor(device=device,
                                   active_measure='humidity') as s:
        assert s.active_measure == 'humidity'
        assert pytest.approx(s.value, abs=0.01) == 0.8   # 80 / 100
        assert s.is_active                               # 0.8 >= 0.8


def test_is_active_below_threshold(tmp_path, mock_factory):
    device = make_device(tmp_path, temp='25000', humidity='50000')
    with HumidityTemperatureSensor(device=device, active_measure='humidity',
                                   threshold=0.8) as s:
        assert not s.is_active                           # 0.5 < 0.8


def test_value_none_before_reading(tmp_path, mock_factory):
    device = make_device(tmp_path)
    temp_path = os.path.join(device, 'in_temp_input')
    os.remove(temp_path)
    os.mkdir(temp_path)  # forces every read to fail
    with HumidityTemperatureSensor(device=device) as s:
        assert s.value is None
        assert not s.is_active


def test_threshold_setter(tmp_path, mock_factory):
    device = make_device(tmp_path)
    with HumidityTemperatureSensor(device=device) as s:
        s.threshold = 0.5
        assert s.threshold == 0.5
        with pytest.raises(ValueError):
            s.threshold = 1.5


def test_range_properties(tmp_path, mock_factory):
    device = make_device(tmp_path)
    with HumidityTemperatureSensor(device=device) as s:
        assert s.min_temp == -40.0
        assert s.max_temp == 80.0
        assert s.min_humidity == 0.0
        assert s.max_humidity == 100.0


def test_repr(tmp_path, mock_factory):
    device = make_device(tmp_path)
    with HumidityTemperatureSensor(device=device) as s:
        assert repr(s).startswith('<gpiozero.HumidityTemperatureSensor object')
    assert repr(s) == '<gpiozero.HumidityTemperatureSensor object closed>'


def test_when_activated_fires(tmp_path, mock_factory):
    device = make_device(tmp_path, humidity='10000')   # 10 %
    fired = Event()
    with HumidityTemperatureSensor(device=device, active_measure='humidity',
                                   threshold=0.5, min_interval=0,
                                   event_delay=0.05) as s:
        s.when_activated = lambda: fired.set()
        assert not s.is_active
        (Path(device) / 'in_humidityrelative_input').write_text('90000')
        assert fired.wait(timeout=5), 'when_activated did not fire'


def test_exported_from_package():
    import gpiozero
    from gpiozero.internal_devices import HumidityTemperatureSensor as Internal
    assert gpiozero.HumidityTemperatureSensor is Internal
