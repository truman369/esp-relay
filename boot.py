#!/usr/bin/env micropython

import machine
import esp
import uos
import gc
import time
import network
import ujson
import tinyweb

esp.osdebug(None)
gc.enable()

"""
nets = {'ssid_1': 'password_1', 'ssid_2': 'password_2'}
relay_db = {'1': {'pin': 16, 'state': 0},
            '2': {'pin': 14, 'state': 0},
            '3': {'pin': 12, 'state': 0},
            '4': {'pin': 13, 'state': 0}}
"""

ap_ssid = "Relay 4 WiFi"
ap_password = "relay1234"
ap_authmode = 3  # WPA2
ap_ip = '10.0.0.10'
ap_mask = '255.255.255.0'
ap_gw = '10.0.0.10'
ap_dns = '1.1.1.1'

wlan_ap = network.WLAN(network.AP_IF)
wlan_sta = network.WLAN(network.STA_IF)

wlan_sta.active(False)

# get wifi config from file
with open('nets.bin', 'rb') as f:
    nets = ujson.load(f)

# get relay pins and status from file
with open('relay.bin', 'rb') as f:
    relay_db = ujson.load(f)

# relay init
relays = {}
for r in relay_db:
    relays[r] = machine.Pin(
        relay_db[r]['pin'], machine.Pin.OUT, value=relay_db[r]['state'])


def save_nets():
    with open('nets.bin', 'wb') as f:
        ujson.dump(nets, f)


def save_relay():
    with open('relay.bin', 'wb') as f:
        ujson.dump(relay_db, f)


def add_net(ssid, password):
    nets[ssid] = password
    save_nets()


def delete_net(ssid):
    del nets[ssid]
    save_nets()


def do_connect(ssid, password):
    wlan_ap.active(False)
    wlan_sta.active(True)
    if wlan_sta.isconnected():
        return None
    print('Trying to connect to %s...' % ssid)
    wlan_sta.connect(ssid, password)
    for retry in range(100):
        connected = wlan_sta.isconnected()
        if connected:
            break
        time.sleep(0.1)
        print('.', end='')
    if connected:
        print('\nConnected.\nifconfig: ', wlan_sta.ifconfig())
    else:
        print('\nFailed. Not Connected to: ' + ssid)
    return connected


def try_connection():
    """return a working WLAN(STA_IF) instance or None"""

    # First check if there already is any connection:
    if wlan_sta.isconnected():
        return wlan_sta

    connected = False
    try:
        # ESP connecting to WiFi takes time, wait a bit and try again:
        time.sleep(3)
        if wlan_sta.isconnected():
            return wlan_sta

        # Search WiFis in range
        wlan_ap.active(False)
        wlan_sta.active(True)
        print('Scanning networks...')
        networks = wlan_sta.scan()

        AUTHMODE = {0: "open", 1: "WEP", 2: "WPA-PSK",
                    3: "WPA2-PSK", 4: "WPA/WPA2-PSK"}
        for ssid, bssid, channel, rssi, authmode, hidden in \
                sorted(networks, key=lambda x: x[3], reverse=True):
            ssid = ssid.decode('utf-8')
            encrypted = authmode > 0
            print("ssid: %s chan: %d rssi: %d authmode: %s" %
                  (ssid, channel, rssi, AUTHMODE.get(authmode, '?')))
            if encrypted and ssid in nets:
                password = nets[ssid]
                connected = do_connect(ssid, password)
            if connected:
                break

    except OSError as e:
        print("exception", str(e))

    if not connected:
        print('No known networks found, starting AP mode...')
        connected = start_ap()

    return wlan_sta if connected else None


def start_ap():
    wlan_sta.active(False)
    wlan_ap.active(True)
    wlan_ap.config(essid=ap_ssid, password=ap_password, authmode=ap_authmode)
    wlan_ap.ifconfig((ap_ip, ap_mask, ap_gw, ap_dns))

    print('ssid: ' + ap_ssid + '\npassword: ' + ap_password)
    print('ifconfig: ', wlan_ap.ifconfig())

    return wlan_ap


wlan_if = try_connection()

app = tinyweb.server.webserver()


def check_data(data, value):
    error = None
    if not value in data:
        error = {'message': 'no '+value+' provided'}, 400
    return data.get(value), error


class Config():

    def get(self, data):
        return {'nets': list(nets.keys())}

    def put(self, data):
        ssid, error = check_data(data, 'ssid')
        if error:
            return error

        if not ssid in nets:
            return {'message':
                    'ssid \''+ssid+'\' not found, use post to create'}, 404

        password, error = check_data(data, 'password')
        if error:
            return error

        add_net(ssid, password)
        return {'message': 'password for ssid \''+ssid+'\' modified'}, 200

    def post(self, data):
        ssid, error = check_data(data, 'ssid')
        if error:
            return error

        if ssid in nets:
            return {'message':
                    'ssid \''+ssid+'\' already saved, use put to edit'}, 405

        password, error = check_data(data, 'password')
        if error:
            return error

        add_net(ssid, password)
        return {'message': 'ssid \''+ssid+'\' saved'}, 201

    def delete(self, data):
        ssid, error = check_data(data, 'ssid')
        if error:
            return error

        if not ssid in nets:
            return {'message':
                    'ssid \''+ssid+'\' not found, nothing to delete'}, 404

        delete_net(ssid)
        return {'message': 'ssid \''+data['ssid']+'\' deleted'}, 200


class RelayList():

    def get(self, data):
        return relay_db


class Relay():

    def get(self, data, id):
        if not id in relay_db:
            return {'message': 'relay not found'}, 404
        return relay_db[id]

    def put(self, data, id):
        if not id in relay_db:
            return {'message': 'wrong id'}, 404

        state, error = check_data(data, 'state')
        if error:
            return error

        state = int(bool(int(state)))
        changed = False
        if state != relay_db[id]['state']:
            changed = True
            relay_db[id]['state'] = state
            relays[id].value(state)
            save_relay()
        return {id: relay_db[id], 'changed': changed}


app.add_resource(Config, '/api/config')
app.add_resource(Config, '/api/config/')
app.add_resource(RelayList, '/api/relay')
app.add_resource(RelayList, '/api/relay/')
app.add_resource(Relay, '/api/relay/<id>')

app.run(host='0.0.0.0', port=80)
