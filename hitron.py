#!/usr/bin/env python3
"""Provides class to interact with CGNV4 routers from Hitron Technologies.

Router class logs in to router's web GUI over HTTP and provides interface
to test connection and reboot device. Currently this module only tested on
Hitron CGNV4 routers, but aspires to support as many models as possible.
"""

from datetime import datetime
from requests import Session
from time import sleep

__author__ = "Tom Black"
__credits__ = ["Tom Black"]
__license__ = "GPL"
__version__ = "0.1.0"
__maintainer__ = "Tom Black"
__email__ = "tom@tcpip.uk"
__status__ = "Production"

class Hitron:
  def __init__(self, host, usr, pwd, retry=2, times=False):
    # Store variables
    self.host = host
    self.usr = usr
    self.pwd = pwd
    # Protocol for web GUI, https is not yet tested
    self.protocol = 'http'
    # Times to attempt login if it fails
    self.retry = retry
    # Whether to output time taken for each command
    self.times = times
    # Set run environment
    self.baseUrl = self.protocol + '://' + self.host + '/'
    self.session = Session()
    # Run connect
    if self.times:
      startTime = self.timestamp()
    for i in range(self.retry):
      if self.connect():
        if self.times:
          print('Login completed in ' + self.timediff(startTime))
        # Stop looping when logged in
        break
      elif self.times:
        print('Login failed in ' + self.timediff(startTime))

  # Create admin session on router
  def connect(self):
    # Attempt login (must be >=2 times to get session then use to login)
    for n in range(2):
      payload = { 'usr': self.usr,
                  'pwd': self.pwd,
                  'forcelogoff': 1,
                  'preSession': self.session.cookies.get('preSession') }
      try:
        response = self.session.post(self.baseUrl + 'goform/login', data=payload, timeout=5)
      # Fail when no response within timeout
      except:
        self.loggedIn = False
        return False
      # Success when login session provided
      if response.cookies.get('sessionindex'):
        self.loggedIn = True
        return True
    # If all attempts failed to get a login session
    return False

  # Retrieve CSRF token
  def csrf(self):
    # Attempt to get token up to 2 times
    for n in range(2):
      # Request new token, store as JSON
      response = self.session.get(self.baseUrl + 'data/getCsrf.asp').json()
      # Return token on success
      if len(response) > 0:
        return response['Csrf_token']
      # If failed, try restarting session
      else:
        self.connect()

  # Check status of GRE tunnel for IP connectivity
  def greStatus(self):
    response = self.session.get(self.baseUrl + 'data/vmb_service_info.asp').json()[0]
    if 'GRETunnel' in response and 'Success' in response['GRETunnel']:
      return response['WanIp']
    else:
      return False

  # Convert seconds to human readable time
  def humanTime(self, seconds):
    # Reference lists for intervals
    INTERVALS = [ 1, 60, 3600, 86400, 604800, 2419200, 29030400]
    NAMES = [('second', 'seconds'),
             ('minute', 'minutes'),
             ('hour', 'hours'),
             ('day', 'days'),
             ('week', 'weeks'),
             ('month', 'months'),
             ('year', 'years')]
    # Create list of units
    result = []
    for i in range(len(NAMES)-1, -1, -1):
      a = int(seconds / INTERVALS[i])
      if a > 0:
        result.append(str(a) + ' ' + NAMES[i][int(1 % a)])
        seconds -= a * INTERVALS[i]
    # Combine to string and return
    if len(result) > 1:
      return ', '.join(result[:-1]) + ' & ' + result[-1]
    elif len(result) == 1:
      return result[0]
    else:
      return '0 seconds'

  # Ping test, router only accepts IPs, returns true when <=25% loss
  def ping(self, dst):
    # Generate test
    model = '{"testtype":"IPv4","testflag":1,"testmode":1,"testurl":"","testipaddr":"' + dst + '"}'
    payload = { 'model': model, 'CsrfToken': self.csrf(), 'CsrfTokenFlag': 1 }
    if self.times:
      startTime = self.timestamp()
    response = self.session.post(self.baseUrl + 'goform/TestDiag', data=payload)
    # Loop to ensure data captured
    for n in range(8):
      # Wait a few seconds for results
      sleep(1)
      # Request update on testing results, convert to JSON
      try:
        response = self.session.get(self.baseUrl + 'data/getAdminDiag.asp').json()
      # Return false if unable to connect
      except:
        return False
      # If response exists, filter to text result, convert lines to list
      if len(response) > 0:
        response = response[0]['testresult']
      if len(response) > 0:
        response = response.replace("#","\n").strip().splitlines()
      # If list over 3 lines long, check for packet loss result
      if len(response) > 3 and 'packet loss' in response[-2]:
         # Filter packet loss rating to the number
         result = int(''.join(_ for _ in response[-2][42:] if _.isnumeric()))
         # Output timer if required
         if self.times:
           print(str(result) + '% packet loss over 4 pings to ' + dst + ' in ' + self.timediff(startTime))
         # Acceptable amount of packet loss
         if result < 30:
           return True
         else:
           return False
    # If response incomplete after 10 seconds, also return false
    return False

  # Request hardware reboot
  def reboot(self):
    payload = { 'model': '{"reboot":"1"}', 'CsrfToken': self.csrf(), 'CsrfTokenFlag': 1 }
    if self.times:
      startTime = self.timestamp()
    # Request reboot
    response = self.session.post(self.baseUrl + 'goform/Reboot', data=payload)

  def rebootAndTest(self, dst='8.8.8.8'):
    # Benchmark reboot and reconnection times
    if self.times:
      startTime = self.timestamp()
    # Trigger reboot
    self.reboot()
    # Login succeeds once before it reboots, so here's a workaround
    failedOnce = False
    # Loop connection tests until router comes up
    for n in range(100):
      if self.connect():
        # Exit loop early if logged in after downtime
        if failedOnce:
          if self.times:
            print('Logged in at ' + self.timediff(startTime))
          break
        # Exit early if router doesn't appear to be rebooting
        if n > 30 and not failedOnce:
          print("Router does not appear to be rebooting, try manually removing power to device")
          return False
      # If failed to connect, record downtime has begun
      else:
        if self.times:
          print('Not logged in yet at ' + self.timediff(startTime))
        failedOnce = True
    # Now router should be booted but not online yet, so loop ping tests
    for n in range(100):
      if self.times and self.greStatus():
        print('GRE tunnel online at ' + self.timediff(startTime))
      if self.ping(dst):
        print('Successful ping to ' + dst + ' at ' + self.timediff(startTime))
        return True
      elif self.times:
        print("Failed to ping " + dst + ' at ' + self.timediff(startTime))
    if self.loggedIn:
      print('Reboot complete, router logged in, but unable to ping ' + dst)
      return False
    else:
      print('Unable to login, router may require a manual reboot')
      return False

  # Output fields from system info dashboard
  def sysInfo(self, field=False):
    response = self.session.get(self.baseUrl + 'data/getSysInfo.asp').json()[0]
    # If no fields returned, return False
    if len(response) < 1:
      return False
    # If field requested that doesn't exist, return false
    elif field and field not in response:
      return False
    # If field exists, return the value directly
    elif field:
      return response[field]
    # Otherwise, return all fields
    else:
      return response

  # Compare one UNIX timestamp with another (default to present)
  def timediff(self, start, finish=False):
    # Default to current time if none provided
    if not finish:
      finish = self.timestamp()
    # Compare timestamps
    return self.humanTime(abs(finish - start))

  # Generate UNIX timestamp
  def timestamp(self):
    return int(datetime.now().timestamp())

  # Provide system uptime in human readable format
  def uptime(self):
    sysInfo = self.sysInfo()
    # If uptime not available, return False
    if not sysInfo or 'systemUptime' not in sysInfo:
      return False
    # Loop through fields adding to total
    for n,value in enumerate(sysInfo['systemUptime'].split(',')):
      values = value.split(' ')
      # Add seconds to total for each value
      if 'total' not in locals():
        total = 0
      if values[1] == 'Days':
        total += int(values[0]) * 86400
      elif values[1] == 'Hours':
        total += int(values[0]) * 3600
      elif values[1] == 'Minutes':
        total += int(values[0]) * 60
      elif values[1] == 'Seconds':
        total += int(values[0])
    # Convert to human readable and return
    return self.humanTime(total)
