import requests

from . import base
from .registry import register

swx_colors = dict(enumerate(['lime', 'yellow', 'yellow', 'orange', 'red', 'red']))


def scale_format(scale, text, unit):
    return (f'{unit}{scale}-{text.title()}', swx_colors[int(scale)]) if text and text != 'none' else (f'{unit}{scale}', swx_colors[int(scale)])


class Space(base.Command):
    noaa_scales_api = "http://services.swpc.noaa.gov/products/noaa-scales.json"
    solar_wind_speed_api = "http://services.swpc.noaa.gov/products/summary/solar-wind-speed.json"
    solar_mag_api = "http://services.swpc.noaa.gov/products/summary/solar-wind-mag-field.json"
    solar_flux_api = "http://services.swpc.noaa.gov/products/summary/10cm-flux.json"

    def swx_scale_parse(self, data):
        radio, solar, geomag = data['R'], data['S'], data['G']

        parts = []
        if radio['Scale']:
            parts.append(scale_format(radio['Scale'], radio['Text'], 'R'))
        if radio['MinorProb']:
            parts.append((f'R1-R2: {radio["MinorProb"]}%', 'yellow'))
        if radio['MajorProb']:
            parts.append((f'R3+: {radio["MajorProb"]}%', 'red'))
        if solar['Scale']:
            parts.append(scale_format(solar['Scale'], solar['Text'], 'S'))
        if solar['Prob']:
            parts.append((f'S1+: {radio["MajorProb"]}%', 'yellow'))
        if geomag['Scale']:
            parts.append(scale_format(geomag['Scale'], geomag['Text'], 'G'))
        return parts


@register(commands=['swx',])
class SpaceWeather(Space):
    template = """
        {{ 'Space'|nc }}:
        {{ 'Current'|tc }}: {% for txt, color in current %}{{ txt|c(color) }}{% if not loop.last %}|{% endif %}{% endfor %}
        {{ "Today's Max"|tc }}: {% for txt, color in today %}{{ txt|c(color) }}{% if not loop.last %}|{% endif %}{% endfor %}
        {{ 'Solar Wind Speed'|tc }}: {{ solar_wind['WindSpeed'] }} km/sec
        {{ 'Magnetic Fields'|tc }}: Bt {{ solar_wind_mag['Bt'] }}nT, Bz {{ solar_wind_mag['Bz'] }}nT
        {{ 'Radio Flux'|tc }}: {{ flux['Flux'] }}sfu"""

    def context(self, msg):
        scales = requests.get(self.noaa_scales_api).json()

        spaceweather = {
            'current': self.swx_scale_parse(scales['0']),
            'today': self.swx_scale_parse(scales['-1']),
            'solar_wind': requests.get(self.solar_wind_speed_api).json(),
            'solar_wind_mag': requests.get(self.solar_mag_api).json(),
            'flux': requests.get(self.solar_flux_api).json(),
        }
        return spaceweather


@register(commands=['swf',])
class SpaceForecast(Space):
    template = """
        {{ 'Space'|nc }}:
        {{ 'Today'|tc }}: {% for txt, color in today %}{{ txt|c(color) }}{% if not loop.last %}|{% endif %}{% endfor %}
        {{ 'Tomorrow'|tc }}: {% for txt, color in tomorrow %}{{ txt|c(color) }}{% if not loop.last %}|{% endif %}{% endfor %}
        {{ "Next Day"|tc }}: {% for txt, color in next_day %}{{ txt|c(color) }}{% if not loop.last %}|{% endif %}{% endfor %}"""

    def context(self, msg):
        scales = requests.get(self.noaa_scales_api).json()

        spaceweather = {
            'today': self.swx_scale_parse(scales['1']),
            'tomorrow': self.swx_scale_parse(scales['2']),
            'next_day': self.swx_scale_parse(scales['3']),
        }
        return spaceweather
