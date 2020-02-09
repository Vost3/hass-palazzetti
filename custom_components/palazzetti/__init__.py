"""
The "palazzetti" custom component.
Configuration:
To use the palazzetti component you will need to add the following to your
configuration.yaml file.
palazzetti:
  ip: your_ip (without quote)
"""
import logging, asyncio, requests, json, voluptuous
from datetime import timedelta

from homeassistant.helpers.event import async_track_time_interval
import homeassistant.helpers.config_validation as cv

import time

_LOGGER = logging.getLogger(__name__)

# The domain of your component. Should be equal to the name of your component.
DOMAIN = "palazzetti"
INTERVAL = timedelta(seconds=60)


CONFIG_SCHEMA = voluptuous.Schema({
    DOMAIN: voluptuous.Schema({
      voluptuous.Required('ip'): cv.string,
    })
}, extra=voluptuous.ALLOW_EXTRA)


async def async_setup(hass, config):
    _LOGGER.debug("Init of palazzetti component")

    hass.data[DOMAIN] = Palazzetti(hass, config)


    # loop for update state of stove
    def update_datas(event_time):
        asyncio.run_coroutine_threadsafe( hass.data[DOMAIN].refresh_main_datas(), hass.loop)

    async_track_time_interval(hass, update_datas, INTERVAL)

    # services
    def set_parameters(call):
        """Handle the service call 'set'"""
        hass.data[DOMAIN].set_parameters(call.data)

    hass.services.async_register(DOMAIN, 'set_parms', set_parameters)

    # Return boolean to indicate that initialization was successfully.
    return True


# class based on NINA 6kw
# contact me if you have a other model of stove
class Palazzetti(object):

    pinged = False
    op = None
    response_json = None

    last_op = None
    last_params = None

    """docstring for Palazzetti"""
    def __init__(self, hass, config):

        self.hass   = hass
        self.ip     = config[DOMAIN].get('ip', None)

        _LOGGER.debug('Init of class palazzetti')

        self.code_status = {
            0 : "OFF",
            1 : "OFF TIMER",
            2 : "TESTFIRE",
            3 : "HEATUP",
            4 : "FUELIGN",
            5 : "IGNTEST",
            6 : "BURNING",
            9 : "COOLFLUID",
            10 : "FIRESTOP",
            11 : "CLEANFIRE",
            12 : "COOL",
            241 : "CHIMNEY ALARM",
            243 : "GRATE ERROR",
            244 : "NTC2 ALARM",
            245 : "NTC3 ALARM",
            247 : "DOOR ALARM",
            248 : "PRESS ALARM",
            249 : "NTC1 ALARM",
            250 : "TC1 ALARM",
            252 : "GAS ALARM",
            253 : "NOPELLET ALARM"
        }

        self.code_fan_nina = {
            0 : "off",
            6 : "high",
            7 : "auto"
        }
        self.code_fan_nina_reversed = {
            "off" : 0,
            "high" : 6,
            "auto" : 7
        }


        # States are in the format DOMAIN.OBJECT_ID.
        #hass.states.async_set('palazzetti.ip', self.ip)

    # get main data needed
    async def refresh_main_datas(self):
        await self.get_alls()
        await self.get_cntr()

    async def get_alls(self):
        """Get All data or almost ;)"""
        self.op = 'GET ALLS'
        await self.get_request()

    async def get_cntr(self):
        """Get counters"""
        self.op = 'GET CNTR'
        await self.get_request()

    async def get_request(self):

        # params for GET
        params = (
            ('cmd', self.op),
        )

        # request the stove
        response = await self.async_request_stove(params)

        if response == False:
            _LOGGER.debug('get_request() response false for op ' + self.op)
            return False

        # save response in json object
        response_json = json.loads(response.text)

        #If no response return
        if response_json['SUCCESS'] != True :
            self.hass.states.async_set('palazzetti.stove', 'com error', self.response_json)
            _LOGGER.error('Error returned by CBox')
            return False

        # merge response with existing dict
        if self.response_json != None :
            response_merged = self.response_json.copy()
            response_merged.update(response_json['DATA'])
            self.response_json = response_merged
        else:
            self.response_json = response_json['DATA']

        self.hass.states.async_set('palazzetti.stove', 'online', self.response_json)
        await self.change_states()

    # send request to stove
    async def async_request_stove(self, params):
        _LOGGER.debug('request stove ' + self.op)

        if self.op is None:
            return False

        queryStr = 'http://'+self.ip+'/cgi-bin/sendmsg.lua'

        # let's go baby
        try:
            response = requests.get(queryStr, params=params, timeout=30)
        except requests.exceptions.ReadTimeout:
            # timeout ( can happend when wifi is used )
            _LOGGER.error('Timeout reach for request : ' + queryStr)
            _LOGGER.info('Please check if you can ping : ' + self.ip)
            self.hass.states.async_set('palazzetti.stove', 'offline')
            return False
        except requests.exceptions.ConnectTimeout:
            # equivalent of ping
            _LOGGER.error('Please check parm ip : ' + self.ip)
            self.hass.states.async_set('palazzetti.stove', 'offline')
            return False

        return response

    # send request to stove
    def request_stove(self, op, params):
        _LOGGER.debug('request stove ' + op)

        if op is None:
            return False       

        # save
        self.last_op = op
        self.last_params = str(params)

        queryStr = 'http://'+self.ip+'/cgi-bin/sendmsg.lua'        

        retry = 0
        success = False
        # error returned by Cbox
        while not success :
            # let's go baby
            try:
                response = requests.get(queryStr, params=params, timeout=30)
            except requests.exceptions.ReadTimeout:
                # timeout ( can happend when wifi is used )
                _LOGGER.error('Timeout reach for request : ' + queryStr)
                _LOGGER.info('Please check if you can ping : ' + self.ip)
                self.hass.states.set('palazzetti.stove', 'offline')
                return False
            except requests.exceptions.ConnectTimeout:
                # equivalent of ping
                _LOGGER.error('Please check parm ip : ' + self.ip)
                self.hass.states.set('palazzetti.stove', 'offline')
                return False

            if response == False:
                return False

            # save response in json object
            response_json = json.loads(response.text)
            success = response_json['SUCCESS']

            # cbox return error
            if not success:
                self.hass.states.async_set('palazzetti.stove', 'com error', self.response_json)
                _LOGGER.error('Error returned by CBox - retry in 2 seconds (' +op+')')
                time.sleep(2)
                retry = retry + 1

                if retry == 3 :
                     _LOGGER.error('Error returned by CBox - stop retry after 3 attempt (' +op+')')
                     break
            
            

        # merge response with existing dict
        if self.response_json != None :
            response_merged = self.response_json.copy()
            response_merged.update(response_json['DATA'])
            self.response_json = response_merged
        else:
            self.response_json = response_json['DATA']

        self.hass.states.async_set('palazzetti.stove', 'online', self.response_json)

        return response

    async def change_states(self):
        """Change states following result of request"""
        if self.op == 'GET ALLS':
            self.hass.states.async_set('palazzetti.STATUS', self.code_status.get(self.response_json['STATUS'], self.response_json['STATUS']))
            self.hass.states.async_set('palazzetti.F2L', int(self.response_json['F2L']))
            self.hass.states.async_set('palazzetti.PWR', self.response_json['PWR'])
            self.hass.states.async_set('palazzetti.SETP', self.response_json['SETP'])

    def get_sept(self):
        """Get target temperature for climate"""
        if self.response_json == None or self.response_json['SETP'] == None:
            return 0

        return self.response_json['SETP']

    def set_parameters(self, datas):
        """set parameters following service call"""
        self.set_sept(datas.get('SETP', None))       # temperature
        self.set_powr(datas.get('PWR', None))        # fire power
        self.set_rfan(datas.get('RFAN', None))       # Fan
        self.set_status(datas.get('STATUS', None))   # status

    def set_sept(self, value):
        """Set target temperature"""

        if value == None or type(value) != int:
            return

        op = 'SET SETP'

        # params for GET
        params = (
            ('cmd', op + ' ' + str(value)),
        )

        # avoid multiple request
        if op == self.last_op and str(params) == self.last_params :
            _LOGGER.debug('retry for op :' +op+' avoided')
            return

        # request the stove
        if self.request_stove(op, params) == False:
            return

        # change state
        self.hass.states.set('palazzetti.SETP', self.response_json['SETP'])

    def set_powr(self, value):
        """Set power of fire"""
        if value is None :
            return
		
        op = 'SET POWR'

        # params for GET
        params = (
            ('cmd', op + ' ' + str(value)),
        )

		# avoid multiple request
        if op == self.last_op and str(params) == self.last_params :
            _LOGGER.debug('retry for op :' +op+' avoided')
            return

        # request the stove
        if self.request_stove(op, params) == False:
            return

        # change state
        self.hass.states.set('palazzetti.PWR', self.response_json['PWR'])

    def set_rfan(self, value):
        """Set fan level"""

        if value == None:
            return

        # must be str or int
        if type(value) != str and type(value) != int:
            return

        op = 'SET RFAN'

        # params for GET
        params = (
            ('cmd', op + ' ' + str(value)),
        )

       	# avoid multiple request
        if op == self.last_op and str(params) == self.last_params :
            _LOGGER.debug('retry for op :' +op+' avoided')
            return           

        # request the stove
        if self.request_stove(op, params) == False:
            return

        # change state
        self.hass.states.async_set('palazzetti.F2L', self.response_json['F2L'])

    def set_status(self, value):
        """start or stop stove"""
        if value == None or type(value) != str :
            return

        # only ON of OFF value allowed
        if value != 'on' and value != 'off':
            return

        op = 'CMD'

        # params for GET
        params = (
            ('cmd', op + ' ' + str(value)),
        )

        # request the stove
        if self.request_stove(op, params) == False:
            return

        # change state
        self.hass.states.async_set('palazzetti.STATUS', self.code_status.get(self.response_json['STATUS'], self.response_json['STATUS']))

    def get_datas(self):
        return self.response_json
