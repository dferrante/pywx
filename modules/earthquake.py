# -*- coding: utf-8 -*- #
import datetime
import re

import pytz
import requests

from . import base
from .registry import register, register_periodic


global EQDB
EQDB = None


def first_greater_selector(i, lst):
    return [r for c, r in lst if c >= i][0]


def hms(secs):
    return ''.join([f'{n}{l}' for n,l in filter(lambda x: bool(x[0]), [(int(secs / 60 / 60), 'h'), (int(secs / 60 % 60), 'm'), (int(secs % 60 % 60), 's')])])


mag_words = [(5,'light'),(6,'moderate'),(7,'STRONG'),(8,'MAJOR'),(9,'GREAT'),(10,'CATASTROPHIC'),]
mag_colors = [(5,'yellow'),(6,'orange'),(7,'red'),(8,'red'),(9,'red'),(10,'red'),]


def mag_word(mag):
    return first_greater_selector(mag, mag_words)


def mag_color(mag):
    return first_greater_selector(mag, mag_colors)


def km_to_miles(kms):
    return round(float(int(kms) * 0.621371), 1)


def label_km_to_miles(kms):
    dist = re.compile(r'([0-9.]+)\s?km').match(kms)
    return re.sub(r'[0-9.]+\s?km', f"{dist.group(0)} ({km_to_miles(dist.group(1))}mi)", kms)


class Earthquake(base.Command):
    template = """
        A {{ descriptor|c(color) }} earthquake has occured.
        {{ 'Magnitude'|tc }}: {{ ('◼ ' + magnitude|string)|c(color) }}
        {{ 'Depth'|tc }}: {{ depth }}km
        {{ 'Region'|tc }}: {{ region }}
        {{ 'Local Time'|tc }}: {{ time }} ({{ ago }} ago) ...
        {% if tsunami %}{{ 'A tsunami may have been generated.'|c('red') }}{% endif %} ...
        {{ url }}"""

    def quake_context(self, quake):
        eqp = quake['properties']
        magnitude = eqp.get('mag')
        if not magnitude:
            return {}
        _, _, depth = quake['geometry']['coordinates']

        localtime = datetime.datetime.fromtimestamp(eqp['time'] / 1000, tz=pytz.utc)
        if eqp.get('tz'):
            localtime += datetime.timedelta(minutes=eqp.get('tz', 0))
        localtime = localtime.strftime('%m/%d %I:%M:%S%p')
        ago = hms((datetime.datetime.now() - datetime.datetime.fromtimestamp(eqp['time'] / 1000)).seconds)

        payload = {
            'eqp': eqp,
            'descriptor': mag_word(float(magnitude)),
            'color': mag_color(float(magnitude)),
            'magnitude': magnitude,
            'depth': depth,
            'region': label_km_to_miles(eqp['place']),
            'time': localtime,
            'ago': ago,
            'tsunami': eqp['tsunami'] and int(eqp['tsunami']) == 1,
            'url': eqp['url'],
        }
        return payload


@register_periodic('earthquake', 150)
class EarthquakeAlerter(Earthquake):
    usgs_api = 'http://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/significant_hour.geojson'
    ptwc_api = ''
    ntwc_api = ''

    def context(self, msg):
        global EQDB
        resp = requests.get(self.usgs_api)
        earthquakes = resp.json()['features']
        if EQDB is None:
            EQDB = []
            for quake in earthquakes:
                EQDB.append(quake['properties']['code'])

        for quake in earthquakes:
            if quake['properties']['code'] in EQDB:
                continue
            else:
                EQDB.append(quake['properties']['code'])
            return self.quake_context(quake)
        raise base.NoMessage


@register(commands=['lastquake',])
class LastQuake(Earthquake):
    usgs_api = 'http://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/significant_month.geojson'

    def context(self, msg):
        resp = requests.get(self.usgs_api)
        earthquakes = resp.json()['features']
        return self.quake_context(earthquakes[0])
