import requests
import json

UPTIME_ROBOT_API_KEY = 'u104722-8f31d22abb5c6ee0dbda565a' # your key 
UPTIME_ROBOT_RESPONSE_FORMAT = 'json' #valid = json or xml 
UPTIME_ROBOT_RESPONSE_JSON_CALLBACK = 1 #valid = 0 or 1 

class AlertContact(object):
    """mapper for alert contacts """
    def __init__(self, data, *args, **kwargs): 
        self.id     = data.get('id')
        self.value  = data.get('value')
        self.type   = 2 #create them as email always 
        self.status = 2 #set them to active 

class UptimeRequest(object): 
    """
        can be used to create requests to the UptimeRobot API
        entity: required -- the type of request to be sent to the server: etc: getElements, getAlertContacts
        payload: not required -- the params that you want to send to the server 
    """
    def __init__(self, entity, payload, *args, **kwargs): 
        self.apiKey = UPTIME_ROBOT_API_KEY
        self.baseUrl = "http://api.uptimerobot.com/"
        self.entity = entity
        self.payload = payload

    def get(self):
        """builds and executes the request"""
        response = self.send_request(self.build_request_url(self.entity), self.payload)
        response.raise_for_status()
        return response

    def url(self): 
        """
            executes and returns the proper URL 
            TODO: probably shouldn't actually execute the request
        """
        request = self.get()
        return request.url

    def build_request_url(self, entity): 
        """creates a request based on the entity type """
        url = "%s%s" % (self.baseUrl, entity)
        return url

    def send_request(self, url, payload): 
        """appends default information and sends the request"""
        payload['apiKey'] = self.apiKey
        payload['format'] = UPTIME_ROBOT_RESPONSE_FORMAT
        payload['noJsonCallback'] = UPTIME_ROBOT_RESPONSE_JSON_CALLBACK
        
        response = requests.get(url, params=payload)
        return response

class Monitor(object):
    """represents an uptime monitor """
    def __init__(self, data, *args, **kwargs): 
        self.contacts = []
        self.id                 = data.get('id')
        self.friendlyname       = data.get('friendlyname')
        self.url                = data.get('url')
        self.type               = data.get('type')
        self.subtype            = data.get('subtype')
        self.status             = data.get('status')
        self.alltimeuptimeratio = data.get('alltimeuptimeratio')
        self.name = self.friendlyname

        contacts = data.get('alertcontact')

        if contacts: 
            self.set_contacts(contacts)

    def set_contacts(self, data):
        """loops through the data from the system and maps the contacts """
        for datum in data: 
            self.contacts.append(AlertContact(datum))

    def get_status(self): 
        """human-readable version of  the status """
        if int(self.status) == 0: 
            return 'paused'
        if int(self.status) == 1: 
            return 'not checked yet'
        if int(self.status) == 2: 
            return 'up'
        if int(self.status) == 8: 
            return 'seems down'
        if int(self.status) == 9: 
            return 'down'

    def add_contact(self, contact): 
        """
            adds a contact to this monitor
            requires an existing contact 
        """
        self.contacts.append(contact)
        self.save()

    def contacts_string(self):
        """creates a string representation of the contacts"""
        contacts_string = ''

        if self.contacts: 
            for c in self.contacts: 
                contacts_string = contacts_string + str(c.id) + '-'
            contacts_string = contacts_string[:-1]

        return contacts_string

    def save(self): 
        """updates the monitor"""
        entity_url = 'editMonitor'
        payload = {}
        payload['monitorID'] = self.id
        payload['monitorFriendlyName'] = self.name
        payload['monitorURL'] = self.url
        payload['monitorAlertContacts'] = self.contacts_string()

        request = UptimeRequest(entity_url, payload)
        request.get()


    def delete(self): 
        """deletes this monitor"""
        entity_url = 'deleteMonitor'
        payload = {}
        payload['monitorID'] = self.id

        request = UptimeRequest(entity_url, payload)
        request.get()

    def print_monitor(self): 
        """print out the monitor to command line """
        print 'id: %s' % self.id
        print 'name: %s' % self.name
        print 'url: %s' % self.url
        print 'type: %s' % self.type
        print 'subtype: %s' % self.subtype
        print 'status: %s' % self.status
        print 'alltimeuptimeratio: %s' % self.alltimeuptimeratio

        print 'contacts:'
        for contact in self.contacts: 
            print contact.value


class UptimeRobot(object):
    """managing class, handles creation of monitors """
    def __init__(self, *args, **kwargs):
        self.monitors = []
        self.contacts = []

    def load_monitors(self): 
        """fetches available monitors and creates objects representing each of them """
        entity_url = 'getMonitors'
        payload = {
            'showMonitorAlertContacts': 1
        }
        request = UptimeRequest(entity_url, payload)
        print request.url()
        response = request.get()
        data = json.loads(response.content) 

        #get the monitors from the request 
        monitors = data.get('monitors')
        monitor = monitors.get('monitor')

        #loop through the monitors and create them 
        for m in monitor: 
            self.monitors.append(Monitor(m))

    def load_contacts(self): 
        """fetches all existing conatcts -- currently waiting on a response from uptime about a potential bug """
        entity_url = 'getAlertContacts'
        payload = {}
        request = UptimeRequest(entity_url, payload)
        response = request.get()
        data = json.loads(response.content)

        contacts_list = data.get('alertcontacts')
        contacts      = contacts_list.get('alertcontact')

        for c in contacts: 
            self.contacts.append(AlertContact(c))

    def reload_monitors(self): 
        """refreshes monitors"""
        self.monitors = [] 
        self.load_monitors()

    def reload_contacts(self): 
        """refreshes conatcts"""
        self.contacts = []
        self.load_contacts()

    def add_monitor(self, name, url, mon_type=1, mon_interval = 5): 
        """adds a monitor"""
        payload = {}

        payload['monitorFriendlyName'] = name
        payload['monitorURL']          = url
        payload['monitorType']         = mon_type #default to HTTP

        #todo alert contacts on create 
        #monitorAlertContacts

        payload['monitorInterval']     = mon_interval #auto-set 5 minutes 

        entity_url = 'newMonitor'
        request = UptimeRequest(entity_url, payload)
        response = request.get()
        self.reload_monitors()

    def add_contact(self, value): 
        """creates an alert contact based on the email address given"""
        payload = {}
        payload['alertContactValue'] = value
        payload['alertContactType'] = 2

        entity_url = 'newAlertContact'
        request = UptimeRequest(entity_url, payload)
        response = request.get()

        #self.reload_contacts()

    def get_monitor_by_name(self, name):
        """finds the first monitor by the name entered"""
        for m in self.monitors:
            if m.name == name:
                return m
        return None

    def search_monitors(self, search_string):
        """todo"""
        pass

    def print_monitors(self): 
        """prints out basic information about monitors """
        for m in self.monitors: 
            print "%-30s %s" % (m.name, m.get_status())

    def print_contacts(self): 
        """prints out basic information about contacts"""
        for m in self.contacts: 
            print "%-30s %s" % (m.id, m.value)
def test(): 
    uptime = UptimeRobot()

    print "getting monitors and contacts.. "
    uptime.load_monitors()
    #uptime.load_contacts()

    print '\n printing monitors.. '
    uptime.print_monitors()

    monitor = uptime.get_monitor_by_name("trueU Website")

    monitor.print_monitor()

    print monitor.contacts_string()


    #print '\n printing contacts.. '
    #uptime.print_contacts()

test()