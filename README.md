# Hitron Router Python Module
A Python 3 module to interact with [CGNV4 routers from Hitron Technologies](https://www.hitrontech.com/product/cgnv4/).

## Installation
Simply download hitron.py and import into a Python script:
```
#!/usr/bin/env python3
from hitron import Hitron
```
## Usage
The repository contains "example.py" to demonstrate how you might automatically test or reboot the router, but documentation on how to use specific functions is below.

### Simple connectivity test
```
router = Hitron('ip', 'user', 'pass')
if not router.ping('8.8.8.8'):
  router.rebootAndTest('8.8.8.8')
```
When you run this script, it will:
* Attempt to login to "ip" using HTTP
* Ping 8.8.8.8 to test the router's internet connectivity
* If 0-1 pings fail it exits without doing anything
* If 2-4 pings fail it will:
  * Trigger a reboot
  * Attempt to login until the router comes back online
  * Attempt to ping 8.8.8.8 until they work

### Output
There are several helper functions to obtain information from the router status pages:
```
>>> router.uptime()
'2 hours, 31 minutes & 13 seconds'
```
Specific fields can be obtained from the dashboard of the router:
```
>>> router.sysInfo('wanIp')
'70.80.90.100/24'
>>> router.sysInfo('swVersion')
'4.5.10.201-CD-UPC'
>>> router.sysInfo('nonExistentField')
False
```
You can output more information about how long each command takes to run by setting "times" to "True" like this:
```
>>> router = Hitron('ip', 'user', 'pass', times=True)
Login completed in 1 second
>>> router.ping('8.8.8.8')
0% packet loss over 4 pings to 8.8.8.8 in 4 seconds
>>> router.rebootAndTest('8.8.8.8')
Not logged in yet at 2 seconds
...
Not logged in yet at 1 minute & 59 seconds
Logged in at 2 minutes & 2 seconds
Failed to ping 8.8.8.8 at 2 minutes & 16 seconds
...
Failed to ping 8.8.8.8 at 4 minutes & 32 seconds
GRE tunnel online at 4 minutes & 32 seconds
0% packet loss over 4 pings to 8.8.8.8 in 6 seconds
Successful ping to 8.8.8.8 at 4 minutes & 38 seconds
```

### Virgin Media Business (CGNV44-FX4)
This module was originally written for [Virgin Media Business](https://www.virginmediabusiness.co.uk/help-and-advice/products-and-services/hitron-router-guide/) routers that provide static IPs using GRE tunnels.

If you have one of these routers, your GRE tunnel will negotiate _after_ the DOCSIS connection is up, so you can check the status of your GRE tunnel with this, which will return `False` when down:
```
>>> router.greStatus()
'50.60.70.80/29'
```

## TODO
* HTTPS login, I suspect this fails currently due to the self-signed SSL certificate
* Testing with other models/variants of Hitron router
