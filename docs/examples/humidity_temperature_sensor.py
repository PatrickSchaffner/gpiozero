from gpiozero import HumidityTemperatureSensor
from time import sleep

sensor = HumidityTemperatureSensor(27, retries=3)

while True:
    reading = sensor.reading
    if reading.temperature is None:
        print('Waiting for sensor...')
    else:
        print(f'Temperature: {reading.temperature:.1f} C  '
              f'Humidity: {reading.humidity:.1f} %')
    sleep(3)
