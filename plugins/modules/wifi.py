#!/usr/bin/python

DOCUMENTATION = '''
---
module: wifi
short_description: Configure WiFi station settings on a Shelly gen 1+ device.
version_added: "0.21.0"
description:
  - Reads current WiFi station config via WiFi.GetConfig.
  - Updates sta and/or sta1 when the SSID or enable state differs.
  - PSK/password comparison is intentionally skipped because devices do not
    expose the stored credential. The password is only sent when the SSID
    changes. To force a password-only update, change the SSID temporarily or
    reconfigure the device manually.
options:
    sta:
        description: Primary WiFi station (sta) configuration.
        required: false
        type: dict
        suboptions:
            ssid:
                description: SSID of the WiFi network.
                required: true
                type: str
            psk:
                description: Pre-shared key / password.
                required: false
                type: str
                no_log: true
            enable:
                description: Enable this station.
                required: false
                type: bool
                default: true
    sta1:
        description: Fallback WiFi station (sta1) configuration.
        required: false
        type: dict
        suboptions:
            ssid:
                description: SSID of the fallback WiFi network.
                required: true
                type: str
            psk:
                description: Pre-shared key / password.
                required: false
                type: str
                no_log: true
            enable:
                description: Enable this fallback station.
                required: false
                type: bool
                default: true
author:
    - pschmitt
'''

EXAMPLES = '''
- name: Configure primary WiFi only
  enclave.shelly.wifi:
    sta:
      ssid: my-iot-network
      psk: supersecret

- name: Configure primary and fallback WiFi
  enclave.shelly.wifi:
    sta:
      ssid: my-iot-network
      psk: supersecret
    sta1:
      ssid: my-fallback-network
      psk: alsosecret
'''

RETURN = '''
changed:
  description: Whether any WiFi configuration was changed.
  returned: always
  type: bool
'''

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.connection import Connection

_STA_KEYS = ("sta", "sta1")
_STA_SPEC = {
    "ssid": {"type": "str", "required": True},
    "psk": {"type": "str", "required": False, "default": None, "no_log": True},
    "enable": {"type": "bool", "required": False, "default": True},
}


def _sta_changes(current_sta, desired):
    """Return config dict to send for one STA, or {} if already correct."""
    if desired is None:
        return {}
    changes = {}
    if current_sta.get("ssid") != desired["ssid"]:
        changes["ssid"] = desired["ssid"]
        if desired.get("psk"):
            changes["psk"] = desired["psk"]
        changes["enable"] = desired.get("enable", True)
    elif current_sta.get("enable") != desired.get("enable", True):
        changes["enable"] = desired.get("enable", True)
    return changes


def run_module():
    module = AnsibleModule(
        argument_spec={
            "sta": {"type": "dict", "required": False, "default": None, "options": _STA_SPEC},
            "sta1": {"type": "dict", "required": False, "default": None, "options": _STA_SPEC},
        },
        supports_check_mode=True,
    )

    connection = Connection(module._socket_path)
    current = connection.send_request(data={"method": "WiFi.GetConfig"})

    all_changes = {}
    diff_before = {}
    diff_after = {}

    for sta_key in _STA_KEYS:
        desired = module.params[sta_key]
        current_sta = current.get(sta_key, {})
        changes = _sta_changes(current_sta, desired)
        if changes:
            all_changes[sta_key] = changes
            diff_before[sta_key] = {k: current_sta.get(k) for k in changes if k != "psk"}
            diff_after[sta_key] = {k: v for k, v in changes.items() if k != "psk"}

    result = dict(changed=bool(all_changes), diff={"before": diff_before, "after": diff_after})

    if not all_changes or module.check_mode:
        module.exit_json(**result)

    connection.send_request(data={
        "method": "WiFi.SetConfig",
        "params": {"config": all_changes},
    })
    module.exit_json(**result)


def main():
    run_module()


if __name__ == "__main__":
    main()
