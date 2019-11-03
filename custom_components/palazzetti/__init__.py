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


_LOGGER = logging.getLogger(__name__)

# The domain of your component. Should be equal to the name of your component.
DOMAIN = "palazzetti"
INTERVAL = timedelta(seconds=60)


CONFIG_SCHEMA = voluptuous.Schema({
    DOMAIN: voluptuous.Schema({
      voluptuous.Required('ip'): cv.string,
    })
}, extra=voluptuous.ALLOW_EXTRA)

@asyncio.coroutine
def async_setup(hass, config):
    _LOGGER.debug("Init of palazzetti component")

    hass.data[DOMAIN] = Palazzetti(hass, config)
        

    # loop for update state of stove
    def update_datas(event_time):        
        asyncio.run_coroutine_threadsafe( hass.data[DOMAIN].refreshMainDatas(), hass.loop)

    async_track_time_interval(hass, update_datas, INTERVAL)
    
    # services
    def setParameters(call):        
        """Handle the service call 'set'"""
        hass.data[DOMAIN].setParameters(call.data)

    hass.services.async_register(DOMAIN, 'set_parms', setParameters)    

        
    # Return boolean to indicate that initialization was successfully.
    return True


# class based on NINA 6kw
# contact me if you have a other model of stove
class Palazzetti(object):
    
    pinged = False
    op = None
    responseJson = None 

    """docstring for Palazzetti"""
    def __init__(self, hass, config):

        self.hass   = hass
        self.ip     = config[DOMAIN].get('ip', None)
        
        _LOGGER.debug('Init of class palazzetti')

        self.codeStatus = {
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

        self.codeFanNina = {
            0 : "off",            
            6 : "high",
            7 : "auto"            
        }
        self.codeFanNinaReversed = {
            "off" : 0,            
            "high" : 6,
            "auto" : 7            
        }

        
        # States are in the format DOMAIN.OBJECT_ID.
        #hass.states.async_set('palazzetti.ip', self.ip)    

    # get main data needed
    async def refreshMainDatas(self):
        await self.getAlls()
        await self.getCNTR()

    async def getAlls(self):        
        """Get All data or almost ;)"""
        self.op = 'GET ALLS'
        await self.getRequest()

    async def getCNTR(self):
        """Get counters"""
        self.op = 'GET CNTR'
        await self.getRequest()            

    async def getRequest(self):

        # params for GET
        params = (
            ('cmd', self.op),
        )

        # request the stove
        response = await self.asyncRequestStove(params)

        if response == False:
            _LOGGER.debug('getRequest() response false for op ' + self.op)
            return False

        # save response in json object
        responseJson = json.loads(response.text)

        #If no response return
        if( responseJson['SUCCESS'] != True ):
            self.hass.states.async_set('palazzetti.stove', 'com error', self.responseJson)
            _LOGGER.error('Error returned by CBox')
            return False

        # merge response with existing dict
        if self.responseJson != None :
            responseJsonCpy = self.responseJson.copy()
            responseJsonCpy.update(responseJson['DATA'])
            self.responseJson = responseJsonCpy
        else:
            self.responseJson = responseJson['DATA']
            
        self.hass.states.async_set('palazzetti.stove', 'online', self.responseJson)        
        await self.changeStates()        

    # send request to stove
    async def asyncRequestStove(self, params):
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
    def requestStove(self, params):
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
        responseJson = json.loads(response.text)

        # error returned by Cbox
        if( responseJson['SUCCESS'] != True ):
            self.hass.states.async_set('palazzetti.stove', 'com error', self.responseJson)                        
            _LOGGER.error('Error returned by CBox')
            return False

        # merge response with existing dict
        if self.responseJson != None :
            responseJsonCpy = self.responseJson.copy()
            responseJsonCpy.update(responseJson['DATA'])
            self.responseJson = responseJsonCpy
        else:
            self.responseJson = responseJson['DATA']
            
        self.hass.states.async_set('palazzetti.stove', 'online', self.responseJson)  

        return response
            
    async def changeStates(self):
        """Change states following result of request"""
        if self.op == 'GET ALLS':       
            self.hass.states.async_set('palazzetti.STATUS', self.codeStatus.get(self.responseJson['STATUS'], self.responseJson['STATUS']))    
            self.hass.states.async_set('palazzetti.F2L', self.codeFanNina.get(self.responseJson['F2L'], self.responseJson['F2L']))
            self.hass.states.async_set('palazzetti.PWR', self.responseJson['PWR'])
            self.hass.states.async_set('palazzetti.SETP', self.responseJson['SETP'])
    
    def getSEPT(self):
        """Get target temperature for climate"""
        if self.responseJson == None or self.responseJson['SETP'] == None:
            return 0

        return self.responseJson['SETP']

    def setParameters(self, datas):
        """set parameters following service call"""
        self.setSEPT(datas.get('SETP', None))       # temperature
        self.setPOWR(datas.get('PWR', None))        # fire power
        self.setRFAN(datas.get('RFAN', None))       # Fan
        self.setStatus(datas.get('STATUS', None))   # status        
        
    def setSEPT(self, value):
        """Set target temperature"""
        
        if value == None or type(value) != int:
            return
                    
        self.op = 'SET SETP'

        # params for GET
        params = (
            ('cmd', self.op + ' ' + str(value)),
        )

        # request the stove
        if self.requestStove(params) == False:            
            return
        
        # change state        
        self.hass.states.set('palazzetti.SETP', self.responseJson['SETP'])      

    def setPOWR(self, value):
        """Set power of fire"""
        
        if value == None or type(value) != int:
            return
                    
        self.op = 'SET POWR'

        # params for GET
        params = (
            ('cmd', self.op + ' ' + str(value)),
        )

        # request the stove
        if self.requestStove(params) == False:            
            return
        
        # change state        
        self.hass.states.set('palazzetti.PWR', self.responseJson['PWR'])     
        
    def setRFAN(self, value):
        """Set fan level"""            
        if value == None:
            return

        # must be str or int
        if type(value) != str and type(value) != int:
            return
        
        # translate if string
        if type(value) is str:
            # is not present in fan dict
            if value not in self.codeFanNinaReversed :                
                return            
            # get the value in reversed dict
            value = self.codeFanNinaReversed.get(value)
                
        self.op = 'SET RFAN'

        # params for GET
        params = (
            ('cmd', self.op + ' ' + str(value)),
        )

        # request the stove
        if self.requestStove(params) == False:            
            return
        
        # change state        
        self.hass.states.async_set('palazzetti.F2L', self.codeFanNina.get(self.responseJson['F2L'], self.responseJson['F2L']))

    def setStatus(self, value):        
        """start or stop stove"""        
        if value == None or type(value) != str :
            return

        # only ON of OFF value allowed
        if value != 'on' and value != 'off':
            return
        
        self.op = 'CMD'

        # params for GET
        params = (
            ('cmd', self.op + ' ' + str(value)),
        )
                
        # request the stove        
        if self.requestStove(params) == False:            
            return
        
        # change state        
        self.hass.states.async_set('palazzetti.STATUS', self.codeStatus.get(self.responseJson['STATUS'], self.responseJson['STATUS']))        
                
            
            