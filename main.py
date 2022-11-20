# main.py
import tinyweb
import uasyncio as asyncio

# init web server
api = tinyweb.webserver()

# init asyncio loop
loop = asyncio.get_event_loop()


def fmt_msg(msg, err_code=200):
    """Format message to json"""
    return {'message': msg}, err_code


def required_fields(fields):
    """Decorator to check required fields in data payload"""
    def decorator(func):
        def wrapper(self, data, *args, **kwargs):
            for field in fields:
                if field not in data:
                    msg = 'Field [%s] not provided.' % field
                    err_code = 400
                    return fmt_msg(msg, err_code)
            return func(self, data, *args, **kwargs)
        return wrapper
    return decorator


async def do_wdt():
    """Watchdog task"""
    print('Starting watchdog...')
    # on ESP8266 watchdog timeout is fixed at 2 seconds
    wdt = machine.WDT()
    while True:
        await asyncio.sleep_ms(500)
        wdt.feed()


async def do_reboot():
    """Reboot task"""
    await asyncio.sleep(1)
    reboot()


class SavedNets():
    """API endpoint for saved nets"""

    def get(self, _):
        return {'saved_nets': list(cfg['saved_nets'])}

    @required_fields(['ssid', 'password'])
    def post(self, data):
        msg, err_code = add_ssid(data['ssid'], data['password'])
        return fmt_msg(msg, err_code)

    @required_fields(['ssid', 'password'])
    def put(self, data):
        msg, err_code = edit_ssid(data['ssid'], data['password'])
        return fmt_msg(msg, err_code)

    @required_fields(['ssid'])
    def delete(self, data):
        msg, err_code = delete_ssid(data['ssid'])
        return fmt_msg(msg, err_code)


class Relay():
    """API endpoint for relay management"""

    def get(self, _, name):
        if not name in cfg['relay_pins']:
            return fmt_msg('Relay not found', 404)
        return cfg['relay_pins'][name]

    @required_fields(['state'])
    def put(self, data, name):
        if not name in cfg['relay_pins']:
            return fmt_msg('Relay not found', 404)
        msg, err_code = set_relay(name, data['state'])
        return fmt_msg(msg, err_code)


@api.resource('/api/relay')
@api.resource('/api/relay/')
def get_relay_list(_):
    """Relay list endpoint"""
    return cfg['relay_pins']


@api.resource('/api/system/reboot', method='POST')
@api.resource('/api/system/reboot/', method='POST')
def exec_system_reboot(_):
    """Reboot endpoint"""
    loop.create_task(do_reboot())
    return fmt_msg('Reboot initiated', 202)


# add api endpoints
api.add_resource(SavedNets, '/api/config/nets')
api.add_resource(Relay, '/api/relay/<name>')

# add watchdog task
loop.create_task(do_wdt())

# ability to start REPL for debugging
try:
    t = 3
    print('To start REPL press Ctrl+C within %ss' % t, end='')
    while t > 0:
        t -= 1
        time.sleep(1)
        print('\b\b%ss' % t, end='')
    print('\r', end='')
except KeyboardInterrupt:
    import sys
    sys.exit()

print('Starting web api server...')
# disable board led
board_led.value(1)
# exec loop.run_forever() inside api web server run
api.run(host='0.0.0.0', port=80, loop_forever=True)
