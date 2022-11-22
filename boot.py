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
# led pins (values are inverted, 0 - enabled, 1- disabled)
ESP_LED_PIN = 2
# default config
cfg = {
    # saved_nets: key is ssid and value is password
    "saved_nets": {},
    # custom led pin by default is the same as on esp
    "custom_led_pin": ESP_LED_PIN,
    # relay pins: {"relay_name": {"pin": int, "state": int}, ...}
    "relay_pins": {}
}
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
    if ssid in cfg['saved_nets']:
        msg = 'SSID [%s] already exists. Skipping...' % ssid
        err_code = 406
    else:
        cfg['saved_nets'][ssid] = password
        save_cfg()
        msg = 'SSID [%s] added.' % ssid
        err_code = 201
    print(msg)
    return msg, err_code


def edit_ssid(ssid, password):
    """Change password for saved ssid"""
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
        err_code = 200
    print(msg)
    return msg, err_code


def delete_ssid(ssid):
    """Delete ssid from config"""
    if not ssid in cfg['saved_nets']:
        msg = 'SSID [%s] not found. Skipping...' % ssid
        err_code = 404
    else:
        del cfg['saved_nets'][ssid]
        save_cfg()
        msg = 'SSID [%s] removed.' % ssid
        err_code = 200
    print(msg)
    return msg, err_code


def add_relay(name, pin):
    """Add new relay"""
    name = str(name)
    pin = int(pin)
    state = 0
    if name in cfg['relay_pins']:
        msg = 'Relay [%s] already exists. Skipping...' % name
        err_code = 406
    else:
        try:
            relays[name] = machine.Pin(pin, machine.Pin.OUT, value=state)
        except Exception as e:
            msg = e
            err_code = 500
        else:
            cfg['relay_pins'][name] = {"pin": pin, "state": state}
            save_cfg()
            msg = 'Added relay [%s] pin [%d]' % (name, pin)
            err_code = 201
    print(msg)
    return msg, err_code


def change_relay_pin(name, pin):
    """Change relay pin"""
    name = str(name)
    pin = int(pin)
    if not name in cfg['relay_pins']:
        msg = 'Relay [%s] not found. Skipping...' % name
        err_code = 404
    elif pin == cfg['relay_pins'][name]['pin']:
        msg = 'Relay [%s] pin is already [%d]. Skipping...' % (name, pin)
        err_code = 406
    else:
        try:
            relays[name] = machine.Pin(pin, machine.Pin.OUT,
                                       value=cfg['relay_pins'][name]['state'])
        except Exception as e:
            msg = e
            err_code = 500
        else:
            old_pin = cfg['relay_pins'][name]['pin']
            cfg['relay_pins'][name]['pin'] = pin
            save_cfg()
            machine.Pin(old_pin).value(0)
            machine.Pin(old_pin).init(machine.Pin.IN)
            msg = 'Relay [%s] pin changed to [%d]' % (name, pin)
            err_code = 200
    print(msg)
    return msg, err_code


def delete_relay(name):
    """Delete relay"""
    name = str(name)
    if not name in cfg['relay_pins']:
        msg = 'Relay [%s] not found. Skipping...' % name
        err_code = 404
    else:
        relays[name].value(0)
        relays[name].init(machine.Pin.IN)
        del (relays[name])
        del (cfg['relay_pins'][name])
        save_cfg()
        msg = 'Relay [%s] removed.' % name
        err_code = 200
    print(msg)
    return msg, err_code


def config_led_pin(pin):
    """Change custom led pin"""
    pin = int(pin)
    if pin == cfg['custom_led_pin']:
        msg = 'Custom led pin is already [%d]. Skipping...' % pin
        err_code = 406
    else:
        try:
            machine.Pin(pin).init(machine.Pin.OUT)
        except Exception as e:
            msg = e
            err_code = 500
        else:
            cfg['custom_led_pin'] = pin
            save_cfg()
            msg = 'Custom led pin changed to [%s]' % pin
            err_code = 200
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
        msg = 'Relay [%s] state is already [%d]' % (name, state)
        err_code = 406
    else:
        # change relay state, change config and save json
        relays[name].value(state)
        cfg['relay_pins'][name]['state'] = state
        save_cfg()
        msg = 'Relay [%s] state changed to [%d]' % (name, state)
    print(msg)
    return msg, err_code


print('\nStarting ESP Relay...')

# init esp led and enable it on startup (inverted: 0 is enabled)
esp_led = machine.Pin(ESP_LED_PIN, machine.Pin.OUT, value=0)

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
        print('Loaded config:')

# init custom led and enable it
custom_led = machine.Pin(cfg['custom_led_pin'], machine.Pin.OUT, value=0)

# print current config and init pins
if len(cfg['relay_pins']) > 0:
    print('_'*17+'\n|Relay|Pin|State|')
    for k, v in sorted(cfg['relay_pins'].items()):
        print('|%3s  |%2d |%3d  |' % (k, v['pin'], v['state']))
        relays[k] = machine.Pin(v['pin'], machine.Pin.OUT, value=v['state'])
    print('-'*17)
else:
    print('No relays configured!')

if cfg['custom_led_pin'] != ESP_LED_PIN:
    print('Custom led pin: %d' % cfg['custom_led_pin'])
else:
    print('No custom led pin set')

if len(cfg['saved_nets']) > 0:
    print('Saved nets:')
    for ssid in cfg['saved_nets']:
        print('  %2s' % (ssid))
else:
    print('No saved networks')

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
                esp_led.value(1)
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
