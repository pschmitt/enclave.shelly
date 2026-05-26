#!/usr/bin/python

DOCUMENTATION = '''
---
module: sys_config
short_description: Configure Shelly system settings on gen 1+ devices.
version_added: "0.28.0"
description:
  - Reads current system configuration via C(Sys.GetConfig).
  - Updates the SNTP server, timezone, location, and RPC-over-UDP settings
    when they differ from the requested values.
  - Supports daylight saving mode on Shelly gen 1 devices and skips it on
    newer devices that do not expose manual DST control.
options:
    sntp_server:
        description:
          - Desired SNTP server hostname.
        required: false
        type: str
    timezone:
        description:
          - Desired timezone identifier.
        required: false
        type: str
    daylight_saving:
        description:
          - Desired daylight saving mode.
          - C(auto) uses the device's automatic DST behavior.
          - C(on) forces DST on.
          - C(off) forces DST off.
        required: false
        type: str
        choices: [on, off, auto]
    latitude:
        description:
          - Desired latitude in decimal degrees.
        required: false
        type: float
    longitude:
        description:
          - Desired longitude in decimal degrees.
        required: false
        type: float
    rpc_udp_listen_port:
        description:
          - Port for inbound RPC-over-UDP.
          - Set to null to disable RPC-over-UDP.
        required: false
        type: int
    rpc_udp_dst_addr:
        description:
          - Outbound destination for RPC-over-UDP notifications.
          - Set to null to disable outbound RPC-over-UDP notifications.
        required: false
        type: str
author:
    - pschmitt
'''

EXAMPLES = '''
- name: Set Shelly system defaults
  enclave.shelly.sys_config:
    sntp_server: time.cloudflare.com
    timezone: Europe/Berlin
    daylight_saving: auto
    latitude: 52.0
    longitude: 13.0
    rpc_udp_listen_port:
    rpc_udp_dst_addr:
'''

RETURN = '''
changed:
  description: Whether any system setting changed.
  returned: always
  type: bool
restart_required:
  description: Whether the device must be rebooted for the config change to apply.
  returned: always
  type: bool
skipped_unsupported:
  description: True when the requested DST setting is unsupported on the device.
  returned: always
  type: bool
'''

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.connection import Connection

import ansible_collections.enclave.shelly.plugins.module_utils.helpers as shelly_utils


def float_differs(current, desired, tolerance=0.00001):
    if current is None or desired is None:
        return current != desired

    return abs(float(current) - float(desired)) > tolerance


def run_module():
    module = AnsibleModule(
        argument_spec={
            "sntp_server": {"type": "str", "required": False, "default": None},
            "timezone": {"type": "str", "required": False, "default": None},
            "daylight_saving": {
                "type": "str",
                "required": False,
                "default": None,
                "choices": ["on", "off", "auto"],
            },
            "latitude": {"type": "float", "required": False, "default": None},
            "longitude": {"type": "float", "required": False, "default": None},
            "rpc_udp_listen_port": {"type": "int", "required": False, "default": None},
            "rpc_udp_dst_addr": {"type": "str", "required": False, "default": None},
        },
        supports_check_mode=True,
    )

    connection = Connection(module._socket_path)
    current = connection.send_request(data={"method": "Sys.GetConfig"})
    is_gen1 = shelly_utils.get_device_generation(connection) == 1

    changes = {}
    diff_before = {}
    diff_after = {}
    skipped_unsupported = False

    location = current.get("location", {})
    if module.params["timezone"] is not None and location.get("tz") != module.params["timezone"]:
        changes.setdefault("location", {})["tz"] = module.params["timezone"]
        diff_before["timezone"] = location.get("tz")
        diff_after["timezone"] = module.params["timezone"]
    if module.params["latitude"] is not None and float_differs(location.get("lat"), module.params["latitude"]):
        changes.setdefault("location", {})["lat"] = module.params["latitude"]
        diff_before["latitude"] = location.get("lat")
        diff_after["latitude"] = module.params["latitude"]
    if module.params["longitude"] is not None and float_differs(location.get("lon"), module.params["longitude"]):
        changes.setdefault("location", {})["lon"] = module.params["longitude"]
        diff_before["longitude"] = location.get("lon")
        diff_after["longitude"] = module.params["longitude"]

    sntp = current.get("sntp", {})
    if module.params["sntp_server"] is not None and sntp.get("server") != module.params["sntp_server"]:
        changes.setdefault("sntp", {})["server"] = module.params["sntp_server"]
        diff_before["sntp_server"] = sntp.get("server")
        diff_after["sntp_server"] = module.params["sntp_server"]

    desired_daylight_saving = module.params["daylight_saving"]
    if desired_daylight_saving is not None:
        if is_gen1:
            current_daylight_saving = "auto"
            if not location.get("dst_auto", False):
                current_daylight_saving = "on" if location.get("dst", False) else "off"

            if current_daylight_saving != desired_daylight_saving:
                changes.setdefault("location", {})
                if desired_daylight_saving == "auto":
                    changes["location"]["dst_auto"] = True
                else:
                    changes["location"]["dst_auto"] = False
                    changes["location"]["dst"] = desired_daylight_saving == "on"
                diff_before["daylight_saving"] = current_daylight_saving
                diff_after["daylight_saving"] = desired_daylight_saving
        else:
            skipped_unsupported = True

    rpc_udp = current.get("rpc_udp", {})
    desired_listen_port = module.params["rpc_udp_listen_port"]
    desired_dst_addr = module.params["rpc_udp_dst_addr"]
    if rpc_udp.get("listen_port") != desired_listen_port:
        changes.setdefault("rpc_udp", {})["listen_port"] = desired_listen_port
        diff_before["rpc_udp_listen_port"] = rpc_udp.get("listen_port")
        diff_after["rpc_udp_listen_port"] = desired_listen_port
    if rpc_udp.get("dst_addr") != desired_dst_addr:
        changes.setdefault("rpc_udp", {})["dst_addr"] = desired_dst_addr
        diff_before["rpc_udp_dst_addr"] = rpc_udp.get("dst_addr")
        diff_after["rpc_udp_dst_addr"] = desired_dst_addr

    result = dict(
        changed=bool(changes),
        restart_required=False,
        skipped_unsupported=skipped_unsupported,
        diff={"before": diff_before, "after": diff_after},
    )

    if not changes or module.check_mode:
        module.exit_json(**result)

    response = connection.send_request(
        data={
            "method": "Sys.SetConfig",
            "params": {"config": changes},
        }
    )
    result["restart_required"] = bool(response.get("restart_required", False))
    module.exit_json(**result)


def main():
    run_module()


if __name__ == "__main__":
    main()
