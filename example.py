#!/usr/bin/env python3

# Update to match your router login details
rtrUser = 'admin'
rtrPass = 'password'
rtrHost = '192.168.0.1'

from hitron import Hitron

# Attempt login to router
router = Hitron(rtrHost, rtrUser, rtrPass, retry=2, times=True)

# Test if login was successful
if not router.loggedIn:
  print('Failed to login')
  exit()

# Output device uptime
print('Device booted ' + router.uptime() + ' ago')

# Output device WAN IP
wanIp = router.sysInfo('wanIp')
if wanIp:
  print('WAN connected to exchange with IP ' + wanIp)
else:
  print('Device does not appear to have a WAN IP')

# Output GRE tunnel status
greIp = router.greStatus()
if greIp:
  print('GRE tunnel for ' + greIp + ' online')
else:
  print('GRE tunnel down or not configured')

# Carry out ping tests
if not router.ping('1.1.1.1') and not router.ping('8.8.8.8') and not router.ping('203.180.230.36'):
  print("All ping tests failed, attempting reboot")
  router.rebootAndTest('8.8.8.8')
  print("Reboot complete")
else:
  print("At least one ping test succeeded, exiting")
