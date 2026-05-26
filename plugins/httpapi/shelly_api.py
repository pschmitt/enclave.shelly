DOCUMENTATION = """
---
author: RustedSkull (@skull132)
httpapi: shelly
short_description: A network OS to interface with Shelly gen 1+ home automation devices.
description: 
  - This HttpApi plugin provides a way of talking to Shelly devices over HTTP.
  - Shelly gen 2+ devices use the JSON-RPC API on C(/rpc).
  - Shelly gen 1 devices use the legacy REST-like HTTP endpoints.
"""

FACTS_MODULES = ["enclave.shelly.shelly_api_facts"]
# Funny story, this does nothing.

import json
import hashlib
import secrets
from urllib.parse import urlencode

from ansible.plugins.httpapi import HttpApiBase
from ansible.errors import AnsibleConnectionFailure
from ansible.module_utils.basic import to_text
from ansible.module_utils.common.parameters import remove_values

from http.client import HTTPResponse

def hash_string(string: str) -> str:
    return hashlib.sha256(string.encode("utf-8")).hexdigest()

class HttpApi(HttpApiBase):
    def __init__(self, connection):
        super().__init__(connection)

        self._request_id = 0
        self._shelly_password = None
        self._device_info = None
        self._device_generation = None

    @property
    def request_id(self):
        self._request_id += 1
        return self._request_id

    def login(self, username, password):
        """
        This function is called in the httpapi.Connection class during initialization.
        The password parameter corresponds to the value of ansible_httpapi_password.
        We can override this function to store the password and use it later for API authentication.
        """
        self._shelly_password = password

    def client_nonce(self):
        return secrets.token_hex(16)

    def ha1(self, realm, password=None):
        if password is None:
            password = self._shelly_password

        return hash_string(f"admin:{realm}:{password}")

    def ha2(self):
        return hash_string("dummy_method:dummy_uri")

    def auth_available(self):
        if self._shelly_password is not None:
            return True
        else:
            return False

    def process_authenticate_header(self, header):
        header = header.split(", ")
        header_dict = {}
        for header_subset in header:
            header_subset = header_subset.split("=")
            key = header_subset[0]
            value = header_subset[1]
            value = value[1:-1]
            header_dict[key] = value

        return header_dict

    @property
    def device_info(self):
        if self._device_info is None:
            self._device_info = self._load_device_info()

        return self._device_info

    @property
    def device_generation(self):
        if self._device_generation is None:
            generation = self.device_info.get("gen")
            if generation is None and "type" in self.device_info:
                generation = 1

            self._device_generation = generation or 2

        return self._device_generation

    def _load_device_info(self):
        try:
            device_info = self._send_rpc_request(
                data={
                    "method": "Shelly.GetDeviceInfo"
                }
            )
        except Exception as exc:
            exc_text = to_text(exc)
            if "Not Found" not in exc_text and "HTTP 404" not in exc_text:
                raise

            device_info = self._send_json_request("/shelly", method="GET")

        if "gen" not in device_info and "type" in device_info:
            device_info["gen"] = 1

        return device_info

    def _send_json_request(self, path, data="", method="GET"):
        response, response_data = self.connection.send(path, data, method=method)
        value = to_text(response_data.getvalue())

        if response.getcode() < 200 or response.getcode() >= 300:
            raise ConnectionError(
                f"Shelly API returned HTTP {response.getcode()} for {path}: {value}"
            )

        if not value:
            return {}

        try:
            return json.loads(value)
        except ValueError:
            raise ConnectionError("Invalid JSON response: %s" % value)

    def _normalize_legacy_mqtt_config(self, settings):
        mqtt_settings = settings.get("mqtt", {})
        result = {
            "enable": mqtt_settings.get("enable"),
            "server": mqtt_settings.get("server"),
            "client_id": mqtt_settings.get("id"),
            "user": mqtt_settings.get("user"),
        }
        result.update(
            {
                "ssl_ca": None,
                "rpc_ntf": True,
                "status_ntf": False,
                "use_client_cert": False,
                "enable_control": True,
            }
        )

        return result

    def _normalize_legacy_mqtt_status(self, status):
        return status.get("mqtt", {})

    def _normalize_legacy_switch_config(self, relay_settings):
        btn_type = relay_settings.get("btn_type")
        in_mode = {
            "toggle": "follow",
            "edge": "flip",
            "detached": "detached",
        }.get(btn_type, btn_type)

        result = relay_settings.copy()
        result["in_mode"] = in_mode

        # Gen1 stores auto timers as float seconds (0 = disabled).
        # Normalise to gen2 bool + delay fields so modules can treat
        # both generations identically.
        for key in ("auto_on", "auto_off"):
            delay_key = f"{key}_delay"
            raw = relay_settings.get(key, 0.0)
            if isinstance(raw, (int, float)):
                result[key] = raw > 0
                result[delay_key] = float(raw) if raw > 0 else 60.0

        # Map gen1 default_state to gen2 initial_state.
        default_state = relay_settings.get("default_state")
        if default_state is not None:
            result["initial_state"] = {
                "last": "restore_last",
                "switch": "match_input",
            }.get(default_state, default_state)

        return result

    def _legacy_scalar(self, value):
        if value is None:
            return ""

        if isinstance(value, bool):
            return "true" if value else "false"

        return str(value)

    def _send_legacy_request(self, data):
        method = data["method"]

        if method == "Shelly.GetDeviceInfo":
            return self.device_info

        if method == "Shelly.GetStatus":
            return self._send_json_request("/status", method="GET")

        if method == "Shelly.Reboot":
            return self._send_json_request("/reboot", method="GET")

        if method == "MQTT.GetConfig":
            return self._normalize_legacy_mqtt_config(
                self._send_json_request("/settings", method="GET")
            )

        if method == "MQTT.GetStatus":
            return self._normalize_legacy_mqtt_status(
                self._send_json_request("/status", method="GET")
            )

        if method == "MQTT.SetConfig":
            config = data.get("params", {}).get("config", {})
            field_map = {
                "enable": "mqtt_enable",
                "server": "mqtt_server",
                "client_id": "mqtt_id",
                "user": "mqtt_user",
                "pass": "mqtt_pass",
            }
            query = {}
            for source_key, target_key in field_map.items():
                if source_key in config:
                    query[target_key] = self._legacy_scalar(config[source_key])

            if query:
                self._send_json_request(
                    f"/settings?{urlencode(query)}",
                    method="GET",
                )

            return {
                "restart_required": bool(query)
            }

        if method == "Switch.GetConfig":
            switch_id = data.get("params", {}).get("id")
            return self._normalize_legacy_switch_config(
                self._send_json_request(f"/settings/relay/{switch_id}", method="GET")
            )

        if method == "Switch.SetConfig":
            switch_id = data.get("params", {}).get("id")
            config = data.get("params", {}).get("config", {})
            query = {}

            if "name" in config:
                query["name"] = config["name"]

            if "in_mode" in config:
                btn_type = {
                    "follow": "toggle",
                    "flip": "edge",
                    "detached": "detached",
                }.get(config["in_mode"])
                if btn_type is None:
                    raise ConnectionError(
                        f"Shelly gen1 devices do not support switch input mode '{config['in_mode']}'."
                    )
                query["btn_type"] = btn_type

            if "initial_state" in config:
                query["default_state"] = {
                    "restore_last": "last",
                    "match_input": "switch",
                }.get(config["initial_state"], config["initial_state"])

            if "auto_on" in config:
                query["auto_on"] = config["auto_on_delay"] if config["auto_on"] else 0

            if "auto_off" in config:
                query["auto_off"] = config["auto_off_delay"] if config["auto_off"] else 0

            if query:
                self._send_json_request(
                    f"/settings/relay/{switch_id}?{urlencode(query)}",
                    method="GET",
                )
            return {"restart_required": False}

        if method == "Input.GetConfig":
            channel_id = data.get("params", {}).get("id", 0)
            settings = self._send_json_request("/settings", method="GET")
            try:
                relay = self._send_json_request(f"/settings/relay/{channel_id}", method="GET")
            except Exception:
                relay = {}
            btn_type = relay.get("btn_type")
            return {
                "id": channel_id,
                "enable": (btn_type != "detached") if btn_type is not None else True,
                "factory_reset": settings.get("pon_wifi_reset", False),
            }

        if method == "Input.SetConfig":
            channel_id = data.get("params", {}).get("id", 0)
            config = data.get("params", {}).get("config", {})
            if "factory_reset" in config:
                self._send_json_request(
                    f"/settings?{urlencode({'pon_wifi_reset': self._legacy_scalar(config['factory_reset'])})}",
                    method="GET",
                )
            if "enable" in config:
                try:
                    relay = self._send_json_request(f"/settings/relay/{channel_id}", method="GET")
                except Exception:
                    relay = {}
                if "btn_type" in relay:
                    btn_type = "toggle" if config["enable"] else "detached"
                    self._send_json_request(
                        f"/settings/relay/{channel_id}?{urlencode({'btn_type': btn_type})}",
                        method="GET",
                    )
            return {}

        if method == "Sys.GetConfig":
            settings = self._send_json_request("/settings", method="GET")
            device = {
                "name": settings.get("name"),
                "discoverable": settings.get("discoverable"),
                "eco_mode": settings.get("eco_mode_enabled"),
                "profile": None,
            }
            if "led_status_disable" in settings or "led_power_disable" in settings:
                leds = {}
                if "led_status_disable" in settings:
                    leds["status"] = not settings["led_status_disable"]
                if "led_power_disable" in settings:
                    leds["power"] = not settings["led_power_disable"]
                device["leds"] = leds
            return {
                "device": device,
                "location": {
                    "tz": settings.get("timezone"),
                    "lat": settings.get("lat"),
                    "lon": settings.get("lng"),
                },
                "sntp": {
                    "server": settings.get("sntp", {}).get("server"),
                },
                "ui_data": {
                    "consumption_types": [
                        r.get("appliance_type") for r in settings.get("relays", [])
                    ],
                },
                "rpc_udp": {
                    "dst_addr": None,
                    "listen_port": None,
                },
            }

        if method == "Sys.SetConfig":
            config = data.get("params", {}).get("config", {})
            device_cfg = config.get("device", {})
            query = {}
            if "name" in device_cfg:
                query["name"] = device_cfg["name"]
            if "discoverable" in device_cfg:
                query["discoverable"] = self._legacy_scalar(device_cfg["discoverable"])
            if "eco_mode" in device_cfg:
                query["eco_mode_enabled"] = self._legacy_scalar(device_cfg["eco_mode"])
            leds = device_cfg.get("leds", {})
            if "status" in leds:
                query["led_status_disable"] = self._legacy_scalar(not leds["status"])
            if "power" in leds:
                query["led_power_disable"] = self._legacy_scalar(not leds["power"])
            location_cfg = config.get("location", {})
            if "tz" in location_cfg:
                query["timezone"] = location_cfg["tz"]
                query["tzautodetect"] = self._legacy_scalar(False)
            if "lat" in location_cfg:
                query["lat"] = self._legacy_scalar(location_cfg["lat"])
                query["tzautodetect"] = self._legacy_scalar(False)
            if "lon" in location_cfg:
                query["lng"] = self._legacy_scalar(location_cfg["lon"])
                query["tzautodetect"] = self._legacy_scalar(False)
            sntp_cfg = config.get("sntp", {})
            if "server" in sntp_cfg:
                query["sntp_server"] = sntp_cfg["server"]
            if query:
                self._send_json_request(f"/settings?{urlencode(query)}", method="GET")
            consumption_types = config.get("ui_data", {}).get("consumption_types")
            if consumption_types:
                for i, ct in enumerate(consumption_types):
                    if ct is not None:
                        self._send_json_request(
                            f"/settings/relay/{i}?{urlencode({'appliance_type': ct})}",
                            method="GET",
                        )
            return {"restart_required": False}

        if method == "Cloud.GetConfig":
            cloud = self._send_json_request("/settings/cloud", method="GET")
            return {
                "enable": cloud.get("enabled"),
            }

        if method == "Cloud.SetConfig":
            config = data.get("params", {}).get("config", {})
            query = {}
            if "enable" in config:
                query["enabled"] = self._legacy_scalar(config["enable"])
            if query:
                self._send_json_request(
                    f"/settings/cloud?{urlencode(query)}",
                    method="GET",
                )
            return {"restart_required": False}

        if method == "Ws.GetConfig":
            raise ConnectionError(
                "Shelly gen1 devices do not support outbound websocket configuration."
            )

        if method == "Ws.SetConfig":
            raise ConnectionError(
                "Shelly gen1 devices do not support outbound websocket configuration."
            )

        if method == "Auth.GetConfig":
            login = self._send_json_request("/settings/login", method="GET")
            return {
                "enabled": login.get("enabled"),
                "unprotected": login.get("unprotected"),
                "username": login.get("username"),
            }

        if method == "Auth.SetConfig":
            config = data.get("params", {}).get("config", {})
            query = {}
            if "enabled" in config:
                query["enabled"] = self._legacy_scalar(config["enabled"])
            if "unprotected" in config:
                query["unprotected"] = self._legacy_scalar(config["unprotected"])
            if "username" in config:
                query["username"] = config["username"]
            if "password" in config:
                query["password"] = config["password"]
            if query:
                self._send_json_request(
                    f"/settings/login?{urlencode(query)}",
                    method="GET",
                )
            return {"restart_required": False}

        if method == "WiFi.GetConfig":
            settings = self._send_json_request("/settings", method="GET")
            result = {"ap": {}}
            for gen1_key, gen2_key in (("wifi_sta", "sta"), ("wifi_sta1", "sta1")):
                sta = settings.get(gen1_key)
                if sta is not None:
                    result[gen2_key] = {
                        "ssid": sta.get("ssid"),
                        "enable": sta.get("enabled", False),
                        "is_open": not bool(sta.get("key", "")),
                    }
            return result

        if method == "WiFi.SetConfig":
            config = data.get("params", {}).get("config", {})
            if config.get("ap"):
                raise ConnectionError(
                    "Shelly gen1 devices do not support WiFi AP or range extender configuration."
                )
            sta = config.get("sta", {})
            if sta:
                query = {}
                if "enable" in sta:
                    query["enabled"] = self._legacy_scalar(sta["enable"])
                if "ssid" in sta:
                    query["ssid"] = sta["ssid"]
                if "pass" in sta:
                    query["key"] = sta["pass"]
                if query:
                    self._send_json_request(f"/settings/sta?{urlencode(query)}", method="GET")
            sta1 = config.get("sta1", {})
            if sta1:
                query1 = {}
                if "enable" in sta1:
                    query1["enabled"] = self._legacy_scalar(sta1["enable"])
                if "ssid" in sta1:
                    query1["ssid"] = sta1["ssid"]
                if "pass" in sta1:
                    query1["key"] = sta1["pass"]
                if query1:
                    self._send_json_request(f"/settings/sta1?{urlencode(query1)}", method="GET")
            return {"restart_required": False}

        if method == "Cover.GetConfig":
            roller_id = data.get("params", {}).get("id", 0)
            roller = self._send_json_request(f"/settings/roller/{roller_id}", method="GET")
            obs_action = roller.get("obstacle_action", "stop")
            return {
                "id": roller_id,
                "name": roller.get("name"),
                "invert_directions": roller.get("swap_inputs", False) or roller.get("swap_outputs", False),
                "obstruction_detection": {
                    "enable": roller.get("obstacle_power", 0) > 0,
                    "action": "reverse" if obs_action == "back" else obs_action,
                    "power_thr": roller.get("obstacle_power", 0),
                },
            }

        if method == "Cover.SetConfig":
            roller_id = data.get("params", {}).get("id", 0)
            config = data.get("params", {}).get("config", {})
            query = {}
            if "name" in config:
                query["name"] = config["name"]
            if "invert_directions" in config:
                v = self._legacy_scalar(config["invert_directions"])
                query["swap_inputs"] = v
                query["swap_outputs"] = v
            obs = config.get("obstruction_detection", {})
            if "action" in obs:
                query["obstacle_action"] = "back" if obs["action"] == "reverse" else obs["action"]
            if "power_thr" in obs:
                query["obstacle_power"] = self._legacy_scalar(obs["power_thr"])
            if query:
                self._send_json_request(
                    f"/settings/roller/{roller_id}?{urlencode(query)}",
                    method="GET",
                )
            return {"restart_required": False}

        if method == "Script.List":
            return {
                "scripts": []
            }

        raise ConnectionError(
            f"Shelly gen1 devices do not support the '{method}' API method."
        )

    def _send_rpc_request(self, data):
        request_data = {
            "id": self.request_id,
            "method": data["method"],
            "params": None
        }

        if "params" in data.keys():
            request_data["params"] = data["params"]

        if "auth" in data.keys():
            request_data["auth"] = data["auth"]

        response: HTTPResponse
        response, response_data = self.connection.send(
            "/rpc", json.dumps(request_data, ensure_ascii=False), method="POST"
        )

        if response.getcode() == 401:
            if "auth" in data:
                raise ConnectionError("Shelly API requires auth, currently provided credentials did not work. This is a library or device bug.")

            if not self.auth_available():
                raise ConnectionError("Shelly API requires auth, but no ansible_httpapi_password was provided for host.")
            
            authenticate_request = response.getheader("WWW-Authenticate")
            if authenticate_request is None:
                raise ConnectionError("Shelly API requires auth, but did not populate WWW-Authenticate header.")
            
            headers = self.process_authenticate_header(authenticate_request)
            nonce = headers["nonce"]
            realm = headers["realm"]
            client_nonce = self.client_nonce()
            data["auth"] = {
                "realm": realm,
                "username": "admin",
                "nonce": nonce,
                "cnonce": client_nonce,
                # nc = 1 because it's only asked over WS.
                "response": hash_string(f"{self.ha1(realm)}:{nonce}:1:{client_nonce}:auth:{self.ha2()}"),
                "algorithm": "SHA-256"
            }

            return self._send_rpc_request(data)

        value = to_text(response_data.getvalue())
        try:
            json_data = json.loads(value) if value else {}
            # JSONDecodeError only available on Python 3.5+
        except ValueError:
            raise ConnectionError("Invalid JSON response: %s" % value)
        
        if "error" in json_data:
            raise ConnectionError(
                "REST API returned %s when sending %s"
                    % (
                        json_data["error"],
                        remove_values(
                            data,
                            [
                                self.connection.get_option("password"),
                            ],
                        ),
                    )
                )
        
        if "result" in json_data:
            json_data = json_data["result"]
        
        return json_data

    def send_request(self, data, **message_kwargs):
        try:
            if self.device_generation == 1:
                return self._send_legacy_request(data)

            return self._send_rpc_request(data)
        except AnsibleConnectionFailure as e:
            e_text = to_text(e.message)
            if to_text("Could not connect to") in e_text:
                raise
            else:
                raise ConnectionError(f"Shelly API connection errored: {e_text}.")
        except ConnectionError as e:
            raise e
        except Exception as e:
            raise e

    def handle_httperror(self, exc):
        return exc
