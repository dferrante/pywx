# -*- coding: utf-8 -*- #
import requests
from . import base
from .weather import first_greater_selector, temp_colors
from .registry import register
from jinja2 import pass_context


@pass_context
def color_temp(ctx, temp):
    ct = int(temp)
    color = first_greater_selector(ct, temp_colors)
    bold = True if ct > 100 else False
    return base.irc_color(u"%s°F" % ct, color, bold=bold)


@register(commands=['housewx',])
class RedlinkStatus(base.Command):
    template = u"""
        House is at {{ curtemp|ctemp }},
        {% if switch_name != 'heating' and switch_name != 'cooling' %}
            system is {{ switch_name }},
        {% else %}
            {{ switch_name }},
        {% endif %}
        {% if setpoint %}
            set to {{ setpoint|ctemp }},
        {% endif %}
        {% if setpoint_status %}
            and {{ setpoint_status }}.
        {% endif %}
        Fan is {{ fan_status }}."""

    def load_filters(self):
        super(RedlinkStatus, self).load_filters()
        self.environment.filters['ctemp'] = color_temp

    def context(self, msg):
        if not self.config.get('redlink_pass'):
            return None
        auth = {
            'UserName': self.config['redlink_user'],
            'Password': self.config['redlink_pass'],
            'RememberMe': 'true',
            'timeOffset': 240
        }
        headers = {'X-Requested-With': 'XMLHttpRequest'}
        authreq = requests.post('https://mytotalconnectcomfort.com/portal/', data=auth)
        wxreq = requests.get('https://mytotalconnectcomfort.com/portal/Device/CheckDataSession/398466',
                             cookies=authreq.history[0].cookies,
                             headers=headers)
        json = wxreq.json()
        data = json['latestData']['uiData']
        switch = data['SystemSwitchPosition']
        curtemp = data['DispTemperature']

        switch_names = {0: 'EMERGENCY HEATING', 1: 'heating', 2: 'off', 3: 'cooling', 4: 'autoheating',
                         5: 'autocooling', 6: 'southern away?', 7: 'unknown'}
        setpoint_status = {0: 'on schedule', 1: 'temporarily holding', 2: 'holding', 3: 'in vacation mode'}
        fan_modes = {0: 'on auto', 1: 'on', 2: 'circulating', 3: 'following schedule', 4: 'unknown'}

        switch_name = switch_names.get(switch, 'unknown')

        setpoint = None
        if switch_name == "heating":
            setpoint = data['HeatSetpoint']
        elif switch_name == "cooling":
            setpoint = data['CoolSetpoint']

        payload = {
            'curtemp': curtemp,
            'switch_name': switch_name,
            'setpoint': setpoint,
            'setpoint_status': setpoint_status[0],
            'fan_status': fan_modes[json['latestData']['fanData']['fanMode']],
        }

        return payload


{
    u'deviceLive': True,
    u'latestData': {
        u'uiData': {
            u'HeatSetpoint': 67.0,
            u'VacationHoldUntilTime': 0,
            u'SystemSwitchPosition': 3,
            u'ScheduleHeatSp': 67.0,
            u'OutdoorHumiditySensorNotFault': True,
            u'IndoorHumidity': 128.0,
            u'DispTemperature': 68.0,
            u'OutdoorTemperature': 128.0,
            u'HeatUpperSetptLimit': 90.0,
            u'CoolNextPeriod': 26,
            u'ScheduleCapable': True,
            u'ScheduleCoolSp': 68.0,
            u'DispTemperatureStatus': 0,
            u'TemporaryHoldUntilTime': 0,
            u'DisplayUnits': u'F',
            u'IndoorHumiditySensorNotFault': True,
            u'Commercial': False,
            u'VacationHold': 0,
            u'SetpointChangeAllowed': True,
            u'SwitchCoolAllowed': True,
            u'HeatLowerSetptLimit': 40.0,
            u'OutdoorHumidity': 128.0,
            u'StatusCool': 0,
            u'CurrentSetpointStatus': 0,
            u'SwitchAutoAllowed': False,
            u'OutdoorHumidStatus': 128,
            u'HeatNextPeriod': 26,
            u'CoolUpperSetptLimit': 99.0,
            u'CoolSetpoint': 68.0,
            u'IndoorHumiditySensorAvailable': False,
            u'SwitchHeatAllowed': True,
            u'OutdoorTemperatureAvailable': False,
            u'DeviceID': 398466,
            u'DispTemperatureAvailable': True,
            u'OutdoorTempStatus': 128,
            u'EquipmentOutputStatus': None,
            u'IndoorHumidStatus': 128,
            u'OutdoorTemperatureSensorNotFault': True,
            u'CoolLowerSetptLimit': 50.0,
            u'VacationHoldCancelable': True,
            u'HoldUntilCapable': True,
            u'OutdoorHumidityAvailable': False,
            u'DualSetpointStatus': False,
            u'StatusHeat': 0,
            u'IsInVacationHoldMode': False,
            u'SwitchEmergencyHeatAllowed': False,
            u'SwitchOffAllowed': True,
            u'Deadband': 0.0
        },
        u'fanData': {
            u'fanMode': 3,
            u'fanModeCirculateAllowed': True,
            u'fanModeFollowScheduleAllowed': True,
            u'fanModeAutoAllowed': True,
            u'fanIsRunning': None,
            u'fanModeOnAllowed': True
        },
        u'canControlHumidification': False,
        u'drData': {
            u'Load': None,
            u'CoolSetpLimit': None,
            u'DeltaHeatSP': None,
            u'OptOutable': False,
            u'Phase': -1,
            u'HeatSetpLimit': None,
            u'DeltaCoolSP': None
        },
        u'hasFan': True
    }, u'alerts': u'\r\n\r\n', u'success': True, u'communicationLost': False}
