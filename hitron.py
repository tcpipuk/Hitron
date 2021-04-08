#!/usr/bin/env python3
"""Provides class to interact with CGNV4 routers from Hitron Technologies.

Router class logs in to router's web GUI over HTTP and provides interface
to test connection and reboot device. Currently this module only tested on
Hitron CGNV4 routers customised for Virgin Media Business, but project goal
is to support as many models as possible.
"""

from datetime import datetime
import requests
from time import sleep

__author__ = "Tom Black"
__copyright__ = "Copyright 2020, Tom Black"
__credits__ = ["Tom Black"]
__license__ = "GPL"
__version__ = "0.2.0"
__maintainer__ = "Tom Black"
__email__ = "tom@tcpip.uk"
__status__ = "Production"

class Hitron:
  def __init__(self, host, usr, pwd, retry=2, https=False, times=False):
    # Store variables
    self.host = host
    self.usr = usr
    self.pwd = pwd
    # Disable SSL verification for HTTPS sessions
    if https:
      self.protocol = 'https'
      self.session = requests.Session()
      self.session.verify = False
      requests.packages.urllib3.disable_warnings()
    # No workarounds required for HTTP sessions
    else:
      self.protocol = 'http'
      self.session = requests.Session()
    # Times to attempt login if it fails
    self.retry = retry
    # Whether to output time taken for each command
    self.times = times
    # Set run environment
    self.baseUrl = self.protocol + '://' + self.host + '/'
    self.loggedIn = False
    # Whether VMB GRE tunnel configured
    self.vmbGre = False
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
        response = self.session.post(self.baseUrl + 'goform/login', data=payload, timeout=3)
      # Fail when no response within timeout
      except:
        self.loggedIn = False
        return False
      # Success when login session provided
      if response.cookies.get('sessionindex'):
        self.loggedIn = True
        # Check whether VMB GRE tunnel configured
        self.vmbGreExists()
        # Return successful connection
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

  # Retrieve list of active DOCSIS channels
  def docsisChannels(self):
    d_response = self.session.get(self.baseUrl + 'data/dsinfo.asp').json()
    u_response = self.session.get(self.baseUrl + 'data/usinfo.asp').json()
    # Create output list and insert channels into it
    output = []
    # Not finished yet

  # Retrieve DOCSIS provisioning status
  def docsisInfo(self, field=False):
    response = self.session.get(self.baseUrl + 'data/getCMInit.asp').json()[0]
    # If no fields returned, return False
    if len(response) < 1:
      return False
    # If field requested that doesn't exist, return false
    elif field and field not in response:
      return False
    # Remove useless entries
    [ response.pop(k) for k in ['eaeStatus', 'networkAccess', 'timeOfday', 'trafficStatus'] ]
    # Convert fields to true/false values
    for name,value in response.items():
      if value in [ 'Enable', 'Permitted', 'Success' ]:
        response[name] = True
      elif value in [ '', 'Processing...' ]:
        response[name] = False
    # If field exists, return the value directly
    if field:
      return response[field]
    # Otherwise, return all fields
    else:
      return response

  # Interpret docsisInfo to explain current connection status
  def docsisStatus(self):
    info = self.docsisInfo()
    if not info or len(info) < 2:
      # No info to provide
      return False, 'No DOCSIS information to report'
    # Summarised from DOCSIS tutorials on https://volpefirm.com
    if 'registration' in info and info['registration'] == True:
      return True, 'Modem registered, service online'
    if 'downloadCfg' in info and info['downloadCfg'] == True:
      return False, 'Config file downloaded, registering on network and bonding channels'
    if 'dhcp' in info and info['dhcp'] == True:
      return False, 'Obtained DHCP, downloading DOCSIS config file'
    if 'ranging' in info and info['ranging'] == True:
      return False, 'DOCSIS ranging complete, requesting time slot to broadcast for DHCP'
    if 'findDownstream' in info and info['findDownstream'] == True:
      return False, 'Downstream DOCSIS channel locked, ranging transmit power'
    if 'hwInit' in info and info['hwInit'] == True:
      return False, 'DOCSIS modem alive, searching downstream channels for CMTS broadcast'
    else:
      return False, 'No DOCSIS information to report'

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

  # Reboot and monitor the connection returning to service
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
        if n > 50 and not failedOnce:
          print("Router does not appear to be rebooting, try manually removing power to device")
          return False
      # If failed to connect, record downtime has begun
      else:
        if not failedOnce:
          print('Confirmed router has gone down for reboot')
          print('Reboot normally takes ~2 minutes, waiting to begin testing')
          sleep(120)
        elif self.times:
          print('Not logged in yet at ' + self.timediff(startTime))
        failedOnce = True
    # Attempt to narrate DOCSIS status
    old_docsis = str()
    for n in range(100):
      current_docsis = self.docsisStatus()
      # Output current status when it's changed
      if current_docsis[1] != old_docsis:
        print(current_docsis[1] + ' at ' + self.timediff(startTime))
        old_docsis = current_docsis[1]
      # If router registered, output status and break loop
      if current_docsis[0] == True:
        break
    # Wait for VMB GRE tunnel if configured
    if self.vmbGre:
      print('VMB GRE tunnel configured, testing that it comes online')
      old_vmbgre = str()
      for n in range(200):
        current_vmbgre = self.vmbGreStatus()
        if current_vmbgre[1] != old_vmbgre:
          print(current_vmbgre[1] + ' at ' + self.timediff(startTime))
          old_vmbgre = current_vmbgre[1]
        if current_vmbgre[0] == True:
          break
        else:
          sleep(1)
    # Now router should be booted but not online yet, so loop ping tests
    for n in range(30):
      if self.ping(dst):
        print('Reboot completed and connectivity appears to be restored at ' + self.timediff(startTime))
        return True
      elif self.times:
        print("Failed to ping " + dst + ' at ' + self.timediff(startTime))
        self.vmbGreStatus()
    if self.loggedIn:
      print('Reboot completed but unable to ping ' + dst + ' - investigate a potential line fault!')
      return False
    else:
      print('Unable to reach router after reboot, try manually removing power to device')
      return False

  # Summary of router status
  def status(self):
    print('Device booted ' + self.uptime() + ' ago')
    # Check DOCSIS
    docsisStatus = self.docsisStatus()
    if docsisStatus:
      if docsisStatus[0]:
        print('DOCSIS appears online, ' + docsisStatus[1])
      else:
        print('DOCSIS appears offline, ' + docsisStatus[1])
    else:
      print('Error reading DOCSIS status')
    # Output device WAN IP
    wanIp = self.sysInfo('wanIp')
    if wanIp:
      print('WAN connected to exchange with IP ' + wanIp)
    else:
      print('Device does not appear to have a WAN IP')
    # Output GRE tunnel status
    if self.vmbGre:
      greIp = self.vmbGreStatus()
      if greIp[0]:
        print('VMB GRE tunnel configured and online with range ' + greIp[1])
      else:
        print('VMB GRE tunnel configured but currently down')
  
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
  
  # Check whether VMB GRE tunnel is configured
  def vmbGreExists(self):
    response = self.session.get(self.baseUrl + 'data/getVMBAccountInfo.asp').json()[0]
    if 'Username' in response and response['Username']:
      self.vmbGre = True
      return True
    else:
      self.vmbGre = False
      return False
  
  # Check status of GRE tunnel for IP connectivity
  def vmbGreStatus(self):
    response = self.session.get(self.baseUrl + 'data/vmb_service_info.asp').json()[0]
    if 'Radius' in response and response['Radius'] == 'Init':
      return False, 'Tunnel is attempting to start RADIUS authentication'
    if 'Radius' in response and response['Radius'] == 'Authentication Start':
      return False, 'Tunnel is currently negotiating RADIUS'
    if 'GRETunnel' in response and response['GRETunnel'] == 'Established':
      return False, 'Tunnel established, awaiting DHCP message'
    if 'GRETunnel' in response and response['GRETunnel'] == 'DHCP Success':
      return True, 'Tunnel has IP range ' + response['WanIp']
    if 'GRETunnel' in response and response['GRETunnel'] == 'PING Success':
      return True, 'Tunnel is testing online with IP range ' + response['WanIp']
    if 'Radius' in response and response['Radius'] == 'Authentication Success':
      return False, 'Tunnel has authenticated, bringing up connectivity'
    else:
      return False, 'Tunnel appears to be down'

# If called from CLI, parse arguments and follow them
if __name__ == "__main__":
  # Handle input and provide help function
  import argparse, sys
  from getpass import getpass
  parser = argparse.ArgumentParser(prog='hitronTest', description='Communicates with Hitron CGNV4 router')
  # Commands section in help
  parser_cmds = parser.add_argument_group('Commands', 'Provide one or more of these to run on the device')
  parser_cmds.add_argument('--reboot', action='store_true', default=False, help='Trigger reboot')
  parser_cmds.add_argument('--status', action='store_true', default=False, help='Show router status')
  parser_cmds.add_argument('--test', type=str, default=False, help='Ping test to <destination-ip>')
  # Router details section in help
  parser_rtr = parser.add_argument_group('Router details', 'Any missing will be prompted on launch')
  parser_rtr.add_argument('--host', type=str, default=False, help='IP or hostname of Hitron router')
  parser_rtr.add_argument('--user', type=str, default=False, help='Username for admin account on Hitron router')
  parser_rtr.add_argument('--pw', type=str, default=False, help='Password for admin account on Hitron router')
  # Options section in help
  parser_opts = parser.add_argument_group('Options', 'Modify output of commands')
  parser_opts.add_argument('--force', action='store_true', default=False, help='Forces --reboot without testing')
  parser_opts.add_argument('--https', action='store_true', default=False, help='Use HTTPS instead of default HTTP')
  parser_opts.add_argument('--retry', type=int, default=2, help='Attempts to login (default: 2)')
  parser_opts.add_argument('--verbose', action='store_true', default=True, help='Increase verbosity of other commands')
  # Import options, output help if none provided
  args = vars(parser.parse_args(args=None if sys.argv[1:] else ['--help']))
  # Fields to prompt for when False
  prompt_for = {
    'host': 'Hostname or IP of router: ',
    'user': 'Username for admin account: ',
    'pw': 'Password for admin account: '
  }
  # Interate through fields and prompt for missing ones
  if 'help' not in args:
    for field,prompt in prompt_for.items():
      if str(field) not in args or not args[field]:
        if field is 'pw':
          args[field] = getpass(prompt)
        else:
          args[field] = input(prompt)
  # Launch Hitron module
  router = Hitron(args['host'], args['user'], args['pw'], retry=args['retry'], https=args['https'], times=args['verbose'])
  # Exit early if router login failed
  if not router.loggedIn:
    print('Router login failed')
    exit()
  # Functions to run
  if args['status']:
    router.status()
  # Variations of reboot/test order
  if args['reboot'] and args['test']:
    testResults = router.ping(args['test'])
    if not testResults:
      print('Ping test failed, attempting reboot')
      router.rebootAndTest(args['test'])
    elif args['force']:
      print('Ping test succeeded, but forced reboot requested')
      router.rebootAndTest(args['test'])      
    else:
      print('Ping test succeeded, skipping reboot')
  elif args['reboot']:
    if args['force']:
      print('Forced reboot requested without testing')
      router.reboot()
      print('Reboot requested')
    else:
      print('Please run with --force to permit reboot without testing')
  elif args['test']:
    if not router.ping(args['test']):
      print('All ping tests failed, you may want to "--reboot"')
    else:
      print('Ping test completed successfully')
