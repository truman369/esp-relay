# ESP Relay

> Simple API for chinese ESP12F relay modules. Written in [micropython](https://micropython.org), depends on [tinyweb](https://github.com/belyalov/tinyweb).

## Supported hardware
Tested with [ESP12F_Relay_X1](/assets/x1.webp?raw=true) and [ESP12F_Relay_X4](/assets/x4.webp?raw=true) modules, but can be used with any others (just setup proper relay pins in config).

## Installation

### Preparations
- Download pre-build micropython firmware with tinyweb library from [here](https://github.com/belyalov/tinyweb/releases).
  > For ESP12F you need ESP8266 version.
- I use `esptool` for flashing firmware and `ampy` for uploading micropython files. So, install them if needed:
  ```shell
  pip install --user adafruit-ampy esptool
  ```
- Connect `RX`, `TX` and `GND` pins to your favorite USB-UART converter. You can also get `5V` from usb, either use an external power supply.

### Flashing firmware
- Short `IO0` and `GND` pins on the board and reboot it.
- Erase old firmware and upload new using `esptool`:
  ```shell
  esptool.py --port /dev/ttyACM0 erase_flash
  esptool.py --port /dev/ttyACM0 --baud 460800 write_flash --flash_size=detect 0 firmware_esp8266-v1.3.5.bin
  ```
  > Don't forget to change port and filename to yours.
- Remove jumper between `IO0` and `GND` pins

### Installing app files
- Upload files using `ampy`:
  ```shell
  ampy -p /dev/ttyACM0 put boot.py
  ampy -p /dev/ttyACM0 put main.py
  ampy -p /dev/ttyACM0 put config.json
  ```
  > Don't forget to change port with yours.
  
  > File `config.json` is optional to upload. You can change all the settings later via the API, but it is more convenient to load them in a file. You can find in repo examples for [X1](/config_x1_example.json) and [X4](/config_x4_example.json) relays.
- Installation is complete. Now you can reboot the board and watch the startup process on UART console via `minicom` or `picocom`.

## Configuration

### WiFi setup
By default, ESP will start in Access Point mode if no network is configured, or if it fails to connect to any of the configured networks.
> The default SSID is `ESP Relay xxx`, where `xxx` is the default password (as well as the ESP's MAC address).
> The default IP address is `10.0.0.10/24`.

After connecting to the ESP's AP, you can add new networks via API:
```shell
curl -s -X POST 10.0.0.10/api/config/nets -d "ssid=my_network" -d "password=my_secret"
```
You can also add networks at the stage of uploading `config.json` file:
```json
    "saved_nets": {
        "my_network": "my_secret",
        "my_another_network": "secret_password"
    },
```
As the networks are configured, you can reboot the board using `RST` button, or just via API:
```shell
curl -s -X POST 10.0.0.10/api/system/reboot
```
During startup, ESP will scan for networks and connect to the first available network from the list. ESP will get an IP address via DHCP, you can find it in UART console. 
> For easy management it would be nice to set static lease for ESP in your DHCP server config.

### Relay pins
On the board, the relay control pins are located near the ESP pins, which allows you to connect them with jumpers.

![ESP12F_X4_Relay pins](/assets/pins.webp)
> On the `ESP12F_Relay_X4` model, `RY1` is near `IO16`, but during ESP initialization, this pin is always HIGH. Therefore, the relay will be switched on briefly each time at boot. To prevent it, I use `IO4` pin for `RY1` in my configuration, just connected them with a short wire.

> On the `ESP12F_Relay_X1` model, the relay pin is connected to `IO5` by default, so you do not need to set any jumpers.

You can add relay pins via API:
```shell
curl -s -X POST 10.0.0.10/api/config/relays -d "name=1" -d "pin=5"
```
or via `config.json`:
```json
    "relay_pins": {
        "1": {
            "pin": 5,
            "state": 0
        }
    },
```

### Board led
In addition to relay status leds, there are another two. One is located directly on ESP, the other on the board. They are used to indicate startup status during the boot:

- Immediately after switching on, the ESP led lights up.
- After loading the config, the board led lights up.
- After connecting to a WiFi network, the ESP led goes out.
- After starting the API server, the board led goes out.
> On the `ESP12F_Relay_X1` model, board led is connected to `IO16` pin.

> On the `ESP12F_Relay_X4` model, board led is connected to `IO5` pin.

You can configure the board led pin via API:
```shell
curl -s -X POST 10.0.0.10/api/config/led -d "pin=16"
```
or in `config.json`:
```json
    "custom_led_pin": 16,
```

## API endpoints
Endpoint            |Methods
--------------------|-------
`/api/relay`        |[GET](#get-apirelay)
`/api/relay/:name`  |[GET](#get-apirelayname), [PUT](#put-apirelayname)
`/api/config/nets`  |[GET](#get-apiconfignets), [POST](#post-apiconfignets), [PUT](#put-apiconfignets), [DELETE](#delete-apiconfignets)
`/api/config/relays`|[POST](#post-apiconfigrelays), [PUT](#put-apiconfigrelays), [DELETE](#delete-apiconfigrelays)
`/api/config/led`   |[POST](#post-apiconfigled)
`/api/system/reboot`|[POST](#post-apisystemreboot)

### `GET` /api/relay
> Get list of configured relays with names and statuses
#### Example request:
```shell
curl -s -X GET 10.0.0.10/api/relay
```
#### Example response:
```json
{
  "1": {
    "pin": 4,
    "state": 1
  },
  "4": {
    "pin": 13,
    "state": 0
  },
  "3": {
    "pin": 12,
    "state": 0
  },
  "2": {
    "pin": 14,
    "state": 0
  }
}
```
[↑](#api-endpoints)
### `GET` /api/relay/:name
> Get status of the relay with name `:name`.
#### Example request:
```shell
curl -s -X GET 10.0.0.10/api/relay/1
```
#### Example response:
```json
{
  "pin": 4,
  "state": 1
}
```
[↑](#api-endpoints)
### `PUT` /api/relay/:name
> Change status of the relay with name `:name`.
#### Request data required:
Attribute|Type|Description
---------|----|-----------
`state`  |int |0 or 1
#### Example request:
```shell
curl -s -X PUT -d "state=0" 10.0.0.10/api/relay/1
```
#### Example response:
```json
{
  "message": "Relay [1] state changed to [0]"
}
```
[↑](#api-endpoints)
### `GET` /api/config/nets
> Get list of saved networks
#### Example request:
```shell
curl -s -X GET 10.0.0.10/api/config/nets
```
#### Example response:
```json
{
  "saved_nets": [
    "Example SSID 1",
    "Example SSID 2"
  ]
}
```
[↑](#api-endpoints)
### `POST` /api/config/nets
> Add new wireless network
#### Request data required:
Attribute |Type|Description
----------|----|-----------
`ssid`    |str |SSID
`password`|str |Password
#### Example request:
```shell
curl -s -X POST 10.0.0.10/api/config/nets -d "ssid=Test Net" -d "password=supersecret"
```
#### Example response:
```json
{
  "message": "SSID [Test Net] added."
}
```
[↑](#api-endpoints)
### `PUT` /api/config/nets
> Change password of existing network
#### Request data required:
Attribute |Type|Description
----------|----|-----------
`ssid`    |str |SSID
`password`|str |New password
#### Example request:
```shell
curl -s -X POST 10.0.0.10/api/config/nets -d "ssid=Test Net" -d "password=newsupersecret"
```
#### Example response:
```json
{
  "message": "Password for [Test Net] changed."
}
```
[↑](#api-endpoints)
### `DELETE` /api/config/nets
> Remove existing network
#### Request data required:
Attribute |Type|Description
----------|----|-----------
`ssid`    |str |SSID
#### Example request:
```shell
curl -s -X DELETE 10.0.0.10/api/config/nets -d "ssid=Test Net"
```
#### Example response:
```json
{
  "message": "SSID [Test Net] removed."
}
```
[↑](#api-endpoints)
### `POST` /api/config/relays
> Add new relay pin
#### Request data required:
Attribute |Type|Description
----------|----|-----------
`name`    |str |Relay name
`pin`     |int |ESP pin
#### Example request:
```shell
curl -s -X POST 10.0.0.10/api/config/relays -d "name=5" -d "pin=15"
```
#### Example response:
```json
{
  "message": "Added relay [5] pin [15]"
}
```
[↑](#api-endpoints)
### `PUT` /api/config/relays
> Change existing relay pin
#### Request data required:
Attribute |Type|Description
----------|----|-----------
`name`    |str |Relay name
`pin`     |int |New ESP pin
#### Example request:
```shell
curl -s -X PUT 10.0.0.10/api/config/relays -d "name=5" -d "pin=16"
```
#### Example response:
```json
{
  "message": "Relay [5] pin changed to [16]"
}
```
[↑](#api-endpoints)
### `DELETE` /api/config/relays
> Remove existing relay
#### Request data required:
Attribute |Type|Description
----------|----|-----------
`name`    |str |Relay name
#### Example request:
```shell
curl -s -X DELETE 10.0.0.10/api/config/relays -d "name=5"
```
#### Example response:
```json
{
  "message": "Relay [5] removed."
}
```
[↑](#api-endpoints)
### `POST` /api/config/led
> Setup board led pin
#### Request data required:
Attribute |Type|Description
----------|----|-----------
`pin`     |int |ESP pin
#### Example request:
```shell
curl -s -X POST 10.0.0.10/api/config/led -d "pin=5"
```
#### Example response:
```json
{
  "message": "Custom led pin changed to [5]"
}
```
[↑](#api-endpoints)
### `POST` /api/system/reboot
> Reboot the board
#### Example request:
```shell
curl -s -X POST 10.0.0.10/api/system/reboot
```
#### Example response:
```json
{
  "message": "Reboot initiated"
}
```
[↑](#api-endpoints)
## Debug mode
After connecting to a WiFi network, you have 3 seconds to press Ctrl+C in the UART console to cancel the API server starting and get into the REPL for debugging. If you press Ctrl+C after API server start, this will trigger watchdog to reboot the board.