# boot.py
import binascii
import esp
import gc
import json
import machine
import network
import os
import time


# disable esp debug messages in uart
esp.osdebug(None)

# enable auto garbage collection
gc.enable()

# file for saving config and relay state
CFG_FILE = 'config.json'
cfg = {
    # saved_nets: key is ssid and value is password
    "saved_nets": {},
    "relay_pins": {'1': {'pin': 4, 'state': 0},
                   '2': {'pin': 14, 'state': 0},
                   '3': {'pin': 12, 'state': 0},
                   '4': {'pin': 13, 'state': 0}}
}
# led pins (values are inverted, 0 - enabled, 1- disabled)
WIFI_LED_PIN = 2
BOARD_LED_PIN = 5
# dict with machine pins
relays = {}


def save_cfg():
    """Save config to json file"""
    try:
        with open(CFG_FILE, 'w') as f:
            json.dump(cfg, f)
    except Exception as e:
        print('[ERROR] Failed to save config: %s', e)


def reboot():
    """Simple alias for reboot"""
    print('Rebooting system...')
    time.sleep(1)
    machine.reset()


def add_ssid(ssid, password):
    """Add new net to config"""
    msg = ''
    err_code = 200
    if ssid in cfg['saved_nets']:
        msg = 'SSID [%s] already exists. Skipping...' % ssid
        err_code = 406
    else:
        cfg['saved_nets'][ssid] = password
        save_cfg()
        msg = 'SSID [%s] added.' % ssid
    print(msg)
    return msg, err_code


def edit_ssid(ssid, password):
    """Change password for saved ssid"""
    msg = ''
    err_code = 200
    if not ssid in cfg['saved_nets']:
        msg = 'SSID [%s] not found. Skipping...' % ssid
        err_code = 404
    elif cfg['saved_nets'][ssid] == password:
        msg = 'Password for [%s] is the same. Skipping...' % ssid
        err_code = 406
    else:
        cfg['saved_nets'][ssid] = password
        save_cfg()
        msg = 'Password for [%s] changed.' % ssid
    print(msg)
    return msg, err_code


def delete_ssid(ssid):
    """Delete ssid from config"""
    msg = ''
    err_code = 200
    if not ssid in cfg['saved_nets']:
        msg = 'SSID [%s] not found. Skipping...' % ssid
        err_code = 404
    else:
        del cfg['saved_nets'][ssid]
        save_cfg()
        msg = 'SSID [%s] removed.' % ssid
    print(msg)
    return msg, err_code


def set_relay(name, state):
    """Set relay state"""
    msg = ''
    err_code = 200
    # convert arguments type if needed
    name = str(name)
    state = int(state)
    if not name in cfg['relay_pins']:
        msg = 'Relay [%s] not found' % name
        err_code = 404
    elif relays[name].value() == state:
        # nothing to change
        msg = 'Relay [%s] state is already [%s]' % (name, state)
        err_code = 406
    else:
        # change relay state, change config and save json
        relays[name].value(state)
        cfg['relay_pins'][name]['state'] = state
        save_cfg()
        msg = 'Relay [%s] state changed to [%s]' % (name, state)
    print(msg)
    return msg, err_code


print('\nStarting ESP Relay...')
# init leds, enable both leds on startup (inverted: 0 is enabled)
board_led = machine.Pin(BOARD_LED_PIN, machine.Pin.OUT, value=0)
wifi_led = machine.Pin(WIFI_LED_PIN, machine.Pin.OUT, value=0)
# load config from file or create default
if not CFG_FILE in os.listdir():
    print('[WARN] Config file not found, creating default...')
    save_cfg()
else:
    # try to load config
    try:
        with open(CFG_FILE, 'r') as f:
            data = json.load(f)
    except Exception as e:
        print('[ERROR] Failed to load config: ', e)
    else:
        cfg = data
# print current config and init pins
print('_'*17+'\n|Relay|Pin|State|')
for k, v in sorted(cfg['relay_pins'].items()):
    print('|%3s  |%2s |%3s  |' % (k, v['pin'], v['state']))
    relays[k] = machine.Pin(v['pin'], machine.Pin.OUT, value=v['state'])
if len(cfg['saved_nets']) > 0:
    print('-'*17+'\nSaved nets:')
    for ssid in cfg['saved_nets']:
        print('  %2s' % (ssid))

# init wlan interfaces
wlan_ap = network.WLAN(network.AP_IF)
wlan_sta = network.WLAN(network.STA_IF)

# try to connect to saved nets
connected = False
if len(cfg['saved_nets']) > 0:
    print('Scanning networks...')
    wlan_sta.active(True)
    # scan and sort by rssi
    for ssid, _, _, rssi, authmode, _ in sorted(
            wlan_sta.scan(), key=lambda x: x[3], reverse=True):
        # convert ssid from bytes to string
        ssid = ssid.decode('utf-8')
        if authmode > 0 and ssid in cfg['saved_nets']:
            print('Trying to connect to %s...' % ssid)
            wlan_sta.connect(ssid, cfg['saved_nets'][ssid])
            # wait for connection established
            for retry in range(500):
                time.sleep(0.1)
                stat = wlan_sta.status()
                if stat == network.STAT_CONNECTING:
                    # print multiline progress bar
                    print('.', end='')
                    if (retry+1) % 60 == 0:
                        print('\r')
                elif stat == network.STAT_WRONG_PASSWORD:
                    print(' WRONG PASSWORD')
                    break
                elif stat == network.STAT_CONNECT_FAIL:
                    print(' FAIL')
                    break
                elif stat == network.STAT_GOT_IP:
                    print(' OK')
                    connected = True
                    break
            else:
                print(' TIMEOUT')
            # stop on first connected network
            if connected:
                # disable wifi led
                wifi_led.value(1)
                wlan_ap.active(False)
                print('\nConnected to [%s]' % ssid)
                print('\nIP:%17s\nNET:%16s\nGW:%17s\nDNS:%16s\n' %
                      wlan_sta.ifconfig())
                break

# otherwise run ap mode
if not connected:
    print('Starting AP mode...')
    wlan_ap.active(True)
    # default AP password - esp mac address
    password = binascii.hexlify(network.WLAN().config('mac')).decode()
    ssid = 'ESP Relay %s' % password
    # authmode: 3 - WPA2
    wlan_ap.config(essid=ssid, password=password, authmode=3)
    wlan_ap.ifconfig(('10.0.0.10', '255.255.255.0', '0.0.0.0', '1.1.1.1'))
    print('\nSSID: %s\nPass: %s' % (ssid, password))
    print('\nIP:%18s\nNET:%17s\nGW:%18s\nDNS:%17s\n' % wlan_ap.ifconfig())
