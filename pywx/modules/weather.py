# -*- coding: utf-8 -*- #
import forecastio
import collections
import time
import pytz
import dataset
import datetime
import csv
import urllib
import requests
import re
import os
from . import base
from geopy.geocoders import GoogleV3
from jinja2 import contextfilter
from registry import register


epoch_tz_dt = lambda ts, tz='UTC': datetime.datetime.fromtimestamp(ts, tz=pytz.utc).astimezone(pytz.timezone(tz))
first_greater_selector = lambda i, l: [r for c, r in l if c >= i][0]
hms = lambda s: ''.join(['%s%s' % (n,l) for n,l in filter(lambda x: bool(x[0]), [(s/60/60, 'h'), (s/60%60, 'm'), (s%60%60, 's')])])
to_celcius = lambda f: (f-32)*5.0/9.0
to_fahrenheight = lambda c: (c*9.0/5.0)+32
wind_chill = lambda t, ws: int(35.74 + (0.6215*t) - 35.75*(ws**0.16) + 0.4275*t*(ws**0.16))
wind_chill_si = lambda t, ws: int(13.12 + (0.6215*t) - 11.37*(ws**0.16) + 0.3965*t*(ws**0.16))
wind_directions = [(11.25, 'N'),(33.75, 'NNE'),(56.25, 'NE'),(78.75, 'ENE'),(101.25, 'E'),(123.75, 'ESE'),
                   (146.25, 'SE'),(168.75, 'SSE'),(191.25, 'S'),(213.75, 'SSW'),(236.25, 'SW'),(258.75, 'WSW'),
                   (281.25, 'W'),(303.75, 'WNW'),(326.25, 'NW'),(348.75, 'NNW'),(360, 'N')]
hic = [0,-42.379,2.04901523,10.14333127,-0.22475541,-6.83783*(10.0**-3.0),-5.481717*(10.0**-2.0),1.22874*(10.0**-3.0),8.5282*(10.0**-4.0),-1.99*(10.0**-6.0)]
heat_index = lambda t,r: round(hic[1]+(hic[2]*t)+(hic[3]*r)+(hic[4]*t*r)+(hic[5]*(t**2))+(hic[6]*(r**2))+(hic[7]*(t**2)*r)+(hic[8]*t*(r**2))+(hic[9]*(t**2)*(r**2)), 1)
heat_index_si = lambda t,r: round(to_celcius(heat_index(to_fahrenheight(t), r)), 1)
moon_phases = [
    (0.0625, 'New'),(0.1875, 'Waxing Crescent'),(0.3125, 'First Quarter'),(0.4375, 'Waxing Gibbous'),(0.5625, 'Full'),
    (0.6875, 'Waning Gibbous'),(0.8125, 'Last Quarter'),(0.9375, 'Waning Crescent'),(1, 'New'),
]
meters_to_feet = lambda m: int(m)*3.28084


icon_colors = {
    'clear-day': 'white',
    'clear-night': 'white',
    'rain': 'aqua',
    'snow': 'purple',
    'sleet': 'pink',
    'wind': 'royal',
    'fog': 'silver',
    'cloudy': 'silver',
    'partly-cloudy-day': 'silver',
    'partly-cloudy-night': 'silver',
    'hail': 'pink',
    'thunderstorm': 'red',
    'tornado': 'red'
}

alert_color = lambda a: ([c for m,c in alert_colors if m in a['title'].lower()] or ['orange'])[0]
alert_colors = (
    ('tornado', 'red'),
    ('thunder', 'yellow'),
    ('hail', 'pink'),
    ('winter', 'purple'),
    ('freeze', 'purple'),
    ('frost', 'purple'),
    ('chill', 'royal'),
    ('ice', 'royal'),
    ('flood', 'navy'),
    ('fog', 'grey'),
    ('wind', 'aqua'),
    ('special', 'null'),
)
temp_colors = ((-100, 'pink'), (15, 'pink'), (32, 'royal'), (50, 'green'), (65, 'lime'), (75, 'yellow'), (85, 'orange'), (150, 'red'))

Airport = collections.namedtuple('Airport', 'airport_id name city country faa icao lat long alt tz dst')


class LocationNotFound(Exception):
    pass


@contextfilter
def pretty_temp(ctx, temp):
    return u"%s°%s" % (int(temp), ctx['units'].temp)

@contextfilter
def color_temp(ctx, temp):
    ct = int(to_fahrenheight(temp)) if ctx['units'].temp == 'C' else int(temp)
    color = first_greater_selector(ct, temp_colors)
    bold = True if ct > 100 else False
    return base.irc_color(pretty_temp(ctx, temp), color, bold=bold)

class BaseWeather(base.Command):
    def __init__(self, config):
        super(BaseWeather, self).__init__(config)
        self.airport_lookup = self.load_airports()
        db = dataset.connect(config['database'])
        self.usertable = db['users']
        self.geoloc = GoogleV3(api_key=config['youtube_key'])

    def load_filters(self):
        super(BaseWeather, self).load_filters()
        self.environment.filters['temp'] = pretty_temp
        self.environment.filters['ctemp'] = color_temp
        self.environment.filters['ic'] = lambda val, icon: base.irc_color(val, icon_colors[icon])
        self.environment.filters['icon_colors'] = icon_colors
        self.environment.filters['alert_colors'] = alert_colors

    def parse_args(self, msg):
        parser = base.IRCArgumentParser()
        group = parser.add_mutually_exclusive_group()
        group.add_argument('-F', action="store_true")
        group.add_argument('-C', action="store_true")
        parser.add_argument('location', type=str, default=None, nargs='*')
        return parser.parse_args(msg)

    def load_airports(self):
        airport_lookup = {}
        adb = self.config.get('pywx_path') + '/airports.dat'
        if adb and os.path.exists(adb):
            for ap in csv.reader(open(adb)):
                ap = map(lambda x: '' if x == '\\N' else x, ap)
                apo = Airport(*ap)
                if apo.faa and apo.faa != '\\N':
                    airport_lookup[apo.faa.lower()] = apo
                if apo.icao and apo.icao != '\\N':
                    airport_lookup[apo.icao.lower()] = apo
        return airport_lookup

    def get_units(self, unitset):
        unitobj = collections.namedtuple("UnitSet", 'wind, dist, temp, intensity, accum, press, time_fmt')
        if unitset == 'us':
            return unitobj('mph', 'mi', 'F', 'in/hr', 'in', 'mbar', '%I:%M:%S%p')
        if unitset == 'si':
            return unitobj('kph', 'km', 'C', 'mm/hr', 'cm', 'hPa', '%H:%M:%S')
        if unitset == 'ca':
            return unitobj('kph', 'km', 'C', 'mm/hr', 'cm', 'hPa', '%H:%M:%S')
        if unitset == 'uk':
            return unitobj('mph', 'km', 'C', 'mm/hr', 'cm', 'hPa', '%H:%M:%S')
        return unitobj('m/s', 'km', 'C', 'mm/hr', 'cm', 'hPa', '%H:%M:%S')

    def match_location(self, username, location):
        name = ""
        lat, lng = 0,0
        match = False
        location = ' '.join(location)

        #db lookup
        if not location:
            user = self.usertable.find_one(user=username)
            if user and user['place'] and user['latitude'] and user['longitude']:
                return user['place'], user['latitude'], user['longitude']

        user = self.usertable.find_one(user=location)
        if user and user['place'] and user['latitude'] and user['longitude']:
            return user['place'], user['latitude'], user['longitude']

        #latlong
        llmatch = re.compile(r'([0-9.-]+),([0-9.-]+)').match(location.lower())
        if llmatch:
            lat, lng = llmatch.groups()
            loc = self.geoloc.reverse((lat, lng), exactly_one=True)
            name = loc.address
            match = True

        airport = self.airport_lookup.get(location)
        if not match and airport:
            match = True
            code = "(%s)" % ('/'.join(filter(lambda x: bool(x), [airport.faa, airport.icao])))
            if airport.name == airport.city:
                name = "%s, %s %s" % (airport.city, airport.country, code)
            elif airport.city in airport.name:
                name = "%s, %s %s" % (airport.name, airport.country, code)
            else:
                name = "%s, %s, %s %s" % (airport.name, airport.city, airport.country, code)
            lat = airport.lat
            lng = airport.long

        if not match:
            try:
                loc = self.geoloc.geocode(location, exactly_one=True)
                name = loc.address
                lat = loc.latitude
                lng = loc.longitude
            except Exception, e:
                raise base.ArgumentError('Location not found')
        self.usertable.upsert(dict(user=username, place=name, latitude=lat, longitude=lng), ['user'])
        return name, lat, lng

    def context(self, msg):
        args = self.parse_args(msg)
        name, lat, lng = self.match_location(msg['sender'], args.location)
        if hasattr(args, 'C') and hasattr(args, 'F'):
            unit_type = 'si' if args.C else 'us' if args.F else 'auto'
        else:
            unit_type = 'auto'
        forecast = forecastio.load_forecast(self.config['forecast_io_secret'], float(lat), float(lng), units=unit_type)
        units = self.get_units(forecast.json['flags']['units'])
        payload = {
            'name': name,
            'lat': lat,
            'lng': lng,
            'forecast': forecast,
            'units': units,
            'args': args,
        }
        return payload


@register(commands=['wf',])
class WeatherForecast(BaseWeather):
    template = u"""
        {{ name|nc }}:
        {% for day in dailies %}
            {{ day.time.strftime('%a')|c('maroon') }}:
            {{ day.summary|ic(day.icon) }}
            (⇑ {{ day.temperatureMax|ctemp }}/⇓ {{ day.temperatureMin|ctemp }})
        {% endfor %}"""

    def context(self, msg):
        payload = super(WeatherForecast, self).context(msg)
        forecast = payload['forecast']
        units = payload['units']
        timezone = pytz.timezone(forecast.json['timezone'])

        daily = forecast.daily().data[:5]
        dailies = []
        for d in daily:
            day = {
               'time': pytz.utc.localize(d.time).astimezone(timezone),
               'icon': d.icon,
               'summary': d.summary,
               'temperatureMin': d.temperatureMin,
               'temperatureMax': d.temperatureMax,
            }
            dailies.append(day)
        payload['dailies'] = dailies
        return payload


@register(commands=['hf',])
class HourlyForecast(BaseWeather):
    template = u"""
        {{ name|nc }}:
        {% for hour in hourlies %}
            {{ (hour.time.strftime('%I')|int|string + hour.time.strftime('%p').lower())|c('maroon') }}:
            {{ hour.summary|ic(hour.icon) }}
            {{ hour.temperature|ctemp }}
        {% endfor %}"""

    def context(self, msg):
        payload = super(HourlyForecast, self).context(msg)
        forecast = payload['forecast']
        units = payload['units']
        timezone = pytz.timezone(forecast.json['timezone'])

        hourly = forecast.hourly().data[:12]
        hourlies = []
        for h in hourly:
            hour = {
               'time': pytz.utc.localize(h.time).astimezone(timezone),
               'icon': h.icon,
               'summary': h.summary,
               'temperature': h.temperature,
            }
            hourlies.append(hour)
        payload['hourlies'] = hourlies
        return payload



@register(commands=['wx',])
class CurrentWeather(BaseWeather):
    template = u"""
    {{ name|nc }}: {{ current.summary|ic(current.icon) }} {{ current.temperature|ctemp }}
    {% if wind_chill %} {{ 'Wind Chill'|c('navy') }}: {{ wind_chill|ctemp }} {% endif %}
    {% if heat_index %} {{ 'Heat Index'|c('red') }}: {{ heat_index|ctemp }} {% endif %}
    {{ 'Winds'|tc }}: {{ windspeed }}
    {{ 'Clouds'|tc }}: {{ clouds }}%
    {{ 'Dewpoint'|tc }}: {{ current.dewPoint|temp }}
    {{ 'Humidity'|tc }}: {{ humidity }}%
    {{ 'Pressure'|tc }}: {{ current.pressure|int }}{{ units.press }}
    {{ 'Sun'|tc }}: {% if sunrise %}☀ {{ sunrise }}{% endif %} ☽ {{ sunset }} {{ daylength }}
    {% if alerts %}{{ 'Alerts'|tc }}: {% for alert, acolor in alerts %}#{{ loop.index }}: {{ alert.title|c(acolor) }} {% endfor %}{% endif %}"""

    def context(self, msg):
        payload = super(CurrentWeather, self).context(msg)
        forecast = payload['forecast']
        units = payload['units']
        timezone = forecast.json['timezone']
        current = forecast.currently()
        payload['current'] = current

        if current.temperature < 50 and current.windSpeed > 3 and units.temp == "F":
            payload['wind_chill'] = wind_chill(current.temperature, current.windSpeed)
        elif current.temperature < 10 and current.windSpeed > 5 and units.temp == "C":
            payload['wind_chill'] = wind_chill_si(current.temperature, current.windSpeed)

        if current.temperature > 80 and current.humidity > .4 and units.temp == "F":
            payload['heat_index'] = heat_index(current.temperature, current.humidity*100)
        elif current.temperature > 26.6 and current.humidity > .4 and units.temp == "C":
            payload['heat_index'] = heat_index_si(current.temperature, current.humidity*100)

        windspeed = current.windSpeed if forecast.json['flags']['units'] != 'si' else current.windSpeed*3.6 #convert m/s to kph
        payload['windspeed'] = '%s%s from %s' % (int(windspeed), units.wind, first_greater_selector(current.windBearing, wind_directions))
        payload['humidity'] = int(current.humidity*100)
        payload['clouds'] = int(current.cloudCover*100)

        sunrisets = forecast.json['daily']['data'][0].get('sunriseTime')
        sunsetts = forecast.json['daily']['data'][0].get('sunsetTime')
        payload['sunrise'] = epoch_tz_dt(sunrisets, timezone).strftime(units.time_fmt).lower() if sunrisets else None
        payload['sunset'] = epoch_tz_dt(sunsetts, timezone).strftime(units.time_fmt).lower() if sunsetts else None

        today = forecast.daily().data[0]
        if today.sunsetTime and today.sunriseTime:
            payload['daylength'] = hms((today.sunsetTime - today.sunriseTime).seconds)
        else:
            north_hemi_summer = 3 < datetime.datetime.now().month <= 9
            lat = payload['lat']
            if (lat > 66.33 and north_hemi_summer) or (lat < -66.33 and not north_hemi_summer):
                payload['daylength'] = '24hr Sun'
            elif (lat > 66.33 and not north_hemi_summer) or (lat < -66.33 and north_hemi_summer):
                payload['daylength'] = '24hr Dark'

        payload['alerts'] = zip(forecast.json.get('alerts', []), map(alert_color, forecast.json.get('alerts', [])))
        return payload


@register(commands=['wxtime', 'sun', 'moon'])
class LocalTime(BaseWeather):
    template = u"""
        {{ name|nc }}: {{ currtime }} ({{ utctime }})
        {{ 'Sun'|tc }}: {% if sunrise %}☀ {{ sunrise }}{% endif %} ☽ {{ sunset }} {{ daylength }}
        {{ 'Moon'|tc }}: {{ moon }}"""

    def context(self, msg):
        payload = super(LocalTime, self).context(msg)
        forecast = payload['forecast']
        units = payload['units']
        timezone = forecast.json['timezone']

        sunrisets = forecast.json['daily']['data'][0].get('sunriseTime')
        sunsetts = forecast.json['daily']['data'][0].get('sunsetTime')
        payload['sunrise'] = epoch_tz_dt(sunrisets, timezone).strftime(units.time_fmt).lower() if sunrisets else None
        payload['sunset'] = epoch_tz_dt(sunsetts, timezone).strftime(units.time_fmt).lower() if sunsetts else None

        today = forecast.daily().data[0]
        if today.sunsetTime and today.sunriseTime:
            payload['daylength'] = hms((today.sunsetTime - today.sunriseTime).seconds)
        else:
            north_hemi_summer = 3 < datetime.datetime.now().month <= 9
            lat = payload['lat']
            if (lat > 66.33 and north_hemi_summer) or (lat < -66.33 and not north_hemi_summer):
                payload['daylength'] = '24hr Sun'
            elif (lat > 66.33 and not north_hemi_summer) or (lat < -66.33 and north_hemi_summer):
                payload['daylength'] = '24hr Dark'

        now = time.time()
        payload['currtime'] = epoch_tz_dt(now, timezone).strftime("%%Y-%%m-%%d %s %%Z (%%z)" % units.time_fmt)
        payload['utctime'] = epoch_tz_dt(now).strftime("%s %%Z" % units.time_fmt)
        payload['moon'] = first_greater_selector(forecast.json['daily']['data'][0]['moonPhase'], moon_phases)
        return payload


@register(commands=['alerts',])
class Alerts(BaseWeather):
    template = u"""
        {% if alerts %}
            {{ 'Alerts'|tc }}:
            {% for alert, acolor in alerts %}#{{ loop.index }}: {{ alert.title|c(acolor) }} {% endfor %}
            ... Use 'alert #' to retrieve alert text
        {% endif %}"""

    def context(self, msg):
        payload = super(Alerts, self).context(msg)
        forecast = payload['forecast']
        payload['alerts'] = zip(forecast.json.get('alerts', []), map(alert_color, forecast.json.get('alerts', [])))
        return payload


@register(commands=['alert',])
class Alert(BaseWeather):
    private_only = True

    def parse_args(self, msg):
        parser = base.IRCArgumentParser()
        parser.add_argument('alert_index', type=int, nargs=1)
        parser.add_argument('location', type=str, default=None, nargs='*')
        return parser.parse_args(msg)

    def run(self, msg):
        try:
            payload = super(Alert, self).context(msg)
        except base.ArgumentError:
            return ['piss']
        forecast = payload['forecast']

        alert_index = payload['args'].alert_index[0]

        lines = []
        if 'alerts' in forecast.json:
            try:
                alert = forecast.json['alerts'][alert_index-1]
            except IndexError, e:
                return []
            lines.append(alert['title'])
            lines.append(alert['uri'])
            for line in alert['description'].split('\n'):
                if line:
                    lines.append(str(line))
            lines.append(datetime.datetime.fromtimestamp(alert['expires']).strftime('Expires: %Y-%m-%d %H:%M'))
        return lines



@register(commands=['radar',])
class Radar(BaseWeather):
    template = "{{ name|nc }}: {{ 'Radar'|tc }}: {{ radarlink }} {{ 'Spark Radar'|tc }}: {{ sparkradarlink }}"

    def context(self, msg):
        payload = super(Radar, self).context(msg)
        timezone = payload['forecast'].json['timezone']
        payload['radarlink'] = 'http://www.srh.noaa.gov/ridge2/ridgenew2/?%s' % (urllib.urlencode({
            'rid': 'NAT', 'pid': 'N0Q', 'lat': payload['lat'], 'lon': payload['lng'], 'frames': 10, 'zoom': 8, 'fs': '1'
        }))
        payload['sparkradarlink'] = 'http://weatherspark.com/forecasts/sparkRadar?%s' % (urllib.urlencode({
            'lat': round(payload['lat'], 3), 'lon': round(payload['lng'] ,3), 'timeZone': timezone, 'unit': payload['units'].dist
        }))
        return payload


@register(commands=['locate', 'find', 'latlng', 'latlong'])
class Locate(BaseWeather):
    elevation_api = "https://maps.googleapis.com/maps/api/elevation/json"
    template = "{{ name|nc }}: {{ lat }}, {{ lng }} {{ 'Elevation'|tc }}: {{ elevation|int }}m ({{ elevation_ft|int }}ft)"

    def get_elevation(self, latlng):
        try:
            req = requests.get(self.elevation_api, params={'locations': ','.join(map(str, latlng))})
            if req.status_code != 200:
                return None
            json = req.json()
            if json['status'] != 'OK':
                return None
            return json['results'][0]['elevation']
        except:
            return None

    def context(self, msg):
        payload = super(Locate, self).context(msg)
        elevation = self.get_elevation((payload['lat'], payload['lng']))
        if elevation:
            payload['elevation'] = elevation
            payload['elevation_ft'] = meters_to_feet(elevation)
        return payload


@register(commands=['eclipse',])
class Eclipse(BaseWeather):
    eclipse_api = "https://www.timeanddate.com/scripts/astroserver.php"
    template = """{{ name|nc }}: {{ 'Apr 8, 2024 Eclipse'|c('maroon') }}:
        {{ 'Start'|tc }}: {{ start }} {{ 'Max'|tc }}: {{ max }} {{ 'End'|tc }}: {{ end }}
        {{ 'Duration'|tc }}: {{ duration }} {{ 'Magnitude'|tc }}: {{ mag }} {{ 'Obscuration'|tc }}: {{ obs }}%
    """

    def get_eclipse_data(self, latlng):
        params = {
            'mode': 'localeclipsejson',
            'n': '@%s' % ','.join(map(str, latlng)),
            'iso': '20240408',
            'zoom': 5,
            'mobile': 0
        }
        try:
            req = requests.get(self.eclipse_api, params=params)
            if req.status_code != 200:
                return None
            json = req.json()
            return json
        except:
            return None

    def context(self, msg):
        payload = super(Locate, self).context(msg)
        eclipse = self.get_eclipse_data((payload['lat'], payload['lng']))

        payload['start'] = eclipse['events'][0]['txt'][15:]
        payload['max'] = eclipse['events'][1]['txt'][15:]
        payload['end'] = eclipse['events'][2]['txt'][15:]
        payload['duration'] = eclipse['duration']['fmt']
        payload['mag'] = eclipse['mag']
        payload['obs'] = eclipse['obs'] * 100
        return payload
