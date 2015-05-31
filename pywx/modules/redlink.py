
#import requests

#@catch_failure
#@smart_print_return
#def housewx(parseinfo):
    #if not config.get('redlink_pass'):
        #pass
    #auth = {
        #'UserName': config['redlink_user'],
        #'Password': config['redlink_pass'],
        #'RememberMe': 'true',
        #'timeOffset': 240
    #}
    #headers = {'X-Requested-With': 'XMLHttpRequest'}
    #authreq = requests.post('https://rs.alarmnet.com/TotalConnectComfort/', data=auth)
    #wxreq = requests.get('https://rs.alarmnet.com/TotalConnectComfort/Device/CheckDataSession/398466',
                         #cookies=authreq.history[0].cookies,
                         #headers=headers)
    #json = wxreq.json()
    #data = json['latestData']['uiData']
    #switch = data['SystemSwitchPosition']
    #curtemp = data['DispTemperature']

    #switch_name = {0: 'EMERGENCY HEATING', 1: 'heating', 2: 'off', 3: 'cooling', 4: 'autoheating',
                     #5: 'autocooling', 6: 'southern away?', 7: 'unknown'}[switch]
    #setpoint_status = {0: 'on schedule', 1: 'temporarily holding', 2: 'holding', 3: 'in vacation mode'}
    #fan_modes = {0: 'on auto', 1: 'on', 2: 'circulating', 3: 'following schedule', 4: 'unknown'}

    #if switch_name == "off":
        #status = "with the system off."
    #if switch_name == "heating":
        #setpoint = data['HeatSetpoint']
        #status = "with the system heating and set to%s." % pt(setpoint)
    #if switch_name == "cooling":
        #setpoint = data['CoolSetpoint']
        #status = "with the system cooling and set to%s." % pt(setpoint)

    #fan_status = "Fan is %s." % fan_modes[json['latestData']['fanData']['fanMode']]

    #payload = ["House is at%s," % pt(curtemp), status, fan_status]
    #return payload
