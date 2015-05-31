# -*- coding: utf-8 -*- #
import datetime
import requests
import re
import pytz
from . import base
from registry import register, register_periodic


global eqdb
eqdb = None

first_greater_selector = lambda i, l: [r for c, r in l if c >= i][0]
hms = lambda s: ''.join(['%s%s' % (n,l) for n,l in filter(lambda x: bool(x[0]), [(s/60/60, 'h'), (s/60%60, 'm'), (s%60%60, 's')])])
mag_words = [(5,'light'),(6,'moderate'),(7,'STRONG'),(8,'MAJOR'),(9,'GREAT'),(10,'CATASTROPHIC'),]
mag_colors = [(5,'yellow'),(6,'orange'),(7,'red'),(8,'red'),(9,'red'),(10,'red'),]
mag_word = lambda mag: first_greater_selector(mag, mag_words)
mag_color = lambda mag: first_greater_selector(mag, mag_colors)
km_to_miles = lambda km: round(float(int(km)*0.621371), 1)
label_km_to_miles = lambda s: re.sub(r'[0-9.]+\s?km', '%s (%smi)' % (re.compile(r'([0-9.]+)\s?km').match(s).group(0), km_to_miles(re.compile(r'([0-9.]+)\s?km').match(s).group(1))), s)


class Earthquake(base.Command):
    template = u"""
        A {{ descriptor|c(color) }} earthquake has occured.
        {{ 'Magnitude'|tc }}: {{ ('◼ ' + magnitude|string)|c(color) }}
        {{ 'Depth'|tc }}: {{ depth }}km
        {{ 'Region'|tc }}: {{ region }}
        {{ 'Local Time'|tc }}: {{ time }} ({{ ago }} ago) ...
        {% if tsunami %}{{ 'A tsunami may have been generated.'|c('red') }}{% endif %} ...
        {{ url }}"""

    def quake_context(self, eq):
        eqp = eq['properties']
        magnitude = eqp.get('mag')
        if not magnitude:
            return {}
        lat, lng, depth = eq['geometry']['coordinates']

        localtime = datetime.datetime.fromtimestamp(eqp['time']/1000, tz=pytz.utc)
        if eqp.get('tz'):
            localtime += datetime.timedelta(minutes=eqp.get('tz', 0))
        localtime = localtime.strftime('%m/%d %I:%M:%S%p')
        ago = hms((datetime.datetime.now() - datetime.datetime.fromtimestamp(eqp['time']/1000)).seconds)

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


@register_periodic
class EarthquakeAlerter(Earthquake):
    usgs_api = 'http://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/significant_hour.geojson'

    def context(self, msg):
        global eqdb
        resp = requests.get(self.usgs_api)
        earthquakes = resp.json()['features']
        if eqdb is None:
            eqdb = []
            for eq in earthquakes:
                eqdb.append(eq['properties']['code'])

        for eq in earthquakes:
            if eq['properties']['code'] in eqdb:
                continue
            else:
                eqdb.append(eq['properties']['code'])
            return self.quake_context(eq)
        return None


@register(commands=['lastquake',])
class LastQuake(Earthquake):
    usgs_api = 'http://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/significant_month.geojson'

    def context(self, msg):
        resp = requests.get(self.usgs_api)
        earthquakes = resp.json()['features']
        return self.quake_context(earthquakes[0])



