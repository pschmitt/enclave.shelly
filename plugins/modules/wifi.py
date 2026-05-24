#!/usr/bin/python

DOCUMENTATION = '''
---
module: wifi
short_description: Configure WiFi station and access-point settings on a Shelly gen 1+ device.
version_added: "0.21.0"
description:
  - Reads current WiFi config via WiFi.GetConfig.
  - Updates sta, sta1, and/or ap sections when the configuration differs.
  - PSK/password comparison is intentionally skipped because devices do not
    expose the stored credential. Passwords are only sent when the SSID
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
    ap:
        description: Access point (AP) and range extender configuration.
        required: false
        type: dict
        suboptions:
            ssid:
                description: SSID for the access point.
                required: false
                type: str
            pass:
                description: >
                  Password for the access point. Only sent when the SSID
                  changes.
                required: false
                type: str
                no_log: true
            enable:
                description: Enable the access point.
                required: false
                type: bool
            range_extender:
                description: Range extender (WiFi repeater) configuration.
                required: false
                type: dict
                suboptions:
                    enable:
                        description: Enable range extender mode.
                        required: true
                        type: bool
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

- name: Enable AP with range extender
  enclave.shelly.wifi:
    ap:
      ssid: shelly-extender
      pass: appassword
      enable: true
      range_extender:
        enable: true

- name: Disable range extender only
  enclave.shelly.wifi:
    ap:
      range_extender:
        enable: false
'''

RETURN = '''
changed:
  description: Whether any WiFi configuration was changed.
  returned: always
  type: bool
restart_required:
  description: Whether the device must be rebooted for changes to take effect.
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
_AP_SPEC = {
    "ssid": {"type": "str", "required": False, "default": None},
    "pass": {"type": "str", "required": False, "default": None, "no_log": True},
    "enable": {"type": "bool", "required": False, "default": None},
    "range_extender": {
        "type": "dict",
        "required": False,
        "default": None,
        "options": {
            "enable": {"type": "bool", "required": True},
        },
    },
}


def _sta_changes(current_sta, desired):
    """Return config dict to send for one STA, or {} if already correct."""
    if desired is None:
        return {}
    changes = {}
    if current_sta.get("ssid") != desired["ssid"]:
        changes["ssid"] = desired["ssid"]
        if desired.get("psk"):
            changes["pass"] = desired["psk"]  # Shelly API field is "pass"
        changes["enable"] = desired.get("enable", True)
    elif current_sta.get("enable") != desired.get("enable", True):
        changes["enable"] = desired.get("enable", True)
    return changes


def _ap_changes(current_ap, desired):
    """Return config dict to send for the AP, or {} if already correct."""
    if desired is None:
        return {}
    changes = {}

    if desired.get("ssid") is not None and current_ap.get("ssid") != desired["ssid"]:
        changes["ssid"] = desired["ssid"]
        if desired.get("pass"):
            changes["pass"] = desired["pass"]

    if desired.get("enable") is not None and current_ap.get("enable") != desired["enable"]:
        changes["enable"] = desired["enable"]

    desired_re = desired.get("range_extender")
    if desired_re is not None:
        current_re = current_ap.get("range_extender") or {}
        if current_re.get("enable") != desired_re["enable"]:
            changes["range_extender"] = {"enable": desired_re["enable"]}

    return changes


def run_module():
    module = AnsibleModule(
        argument_spec={
            "sta": {"type": "dict", "required": False, "default": None, "options": _STA_SPEC},
            "sta1": {"type": "dict", "required": False, "default": None, "options": _STA_SPEC},
            "ap": {"type": "dict", "required": False, "default": None, "options": _AP_SPEC},
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
            diff_before[sta_key] = {k: current_sta.get(k) for k in changes if k != "pass"}
            diff_after[sta_key] = {k: v for k, v in changes.items() if k != "pass"}

    desired_ap = module.params["ap"]
    current_ap = current.get("ap") or {}
    ap_changes = _ap_changes(current_ap, desired_ap)
    if ap_changes:
        all_changes["ap"] = ap_changes
        diff_before["ap"] = {k: current_ap.get(k) for k in ap_changes if k != "pass"}
        diff_after["ap"] = {k: v for k, v in ap_changes.items() if k != "pass"}

    result = dict(
        changed=bool(all_changes),
        restart_required=False,
        diff={"before": diff_before, "after": diff_after},
    )

    if not all_changes or module.check_mode:
        module.exit_json(**result)

    response = connection.send_request(data={
        "method": "WiFi.SetConfig",
        "params": {"config": all_changes},
    })
    result["restart_required"] = bool(response.get("restart_required", False))
    module.exit_json(**result)


def main():
    run_module()


if __name__ == "__main__":
    main()
