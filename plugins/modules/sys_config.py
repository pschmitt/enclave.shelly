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
'''

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.connection import Connection


def run_module():
    module = AnsibleModule(
        argument_spec={
            "sntp_server": {"type": "str", "required": False, "default": None},
            "timezone": {"type": "str", "required": False, "default": None},
            "latitude": {"type": "float", "required": False, "default": None},
            "longitude": {"type": "float", "required": False, "default": None},
            "rpc_udp_listen_port": {"type": "int", "required": False, "default": None},
            "rpc_udp_dst_addr": {"type": "str", "required": False, "default": None},
        },
        supports_check_mode=True,
    )

    connection = Connection(module._socket_path)
    current = connection.send_request(data={"method": "Sys.GetConfig"})

    changes = {}
    diff_before = {}
    diff_after = {}

    location = current.get("location", {})
    if module.params["timezone"] is not None and location.get("tz") != module.params["timezone"]:
        changes.setdefault("location", {})["tz"] = module.params["timezone"]
        diff_before["timezone"] = location.get("tz")
        diff_after["timezone"] = module.params["timezone"]
    if module.params["latitude"] is not None and location.get("lat") != module.params["latitude"]:
        changes.setdefault("location", {})["lat"] = module.params["latitude"]
        diff_before["latitude"] = location.get("lat")
        diff_after["latitude"] = module.params["latitude"]
    if module.params["longitude"] is not None and location.get("lon") != module.params["longitude"]:
        changes.setdefault("location", {})["lon"] = module.params["longitude"]
        diff_before["longitude"] = location.get("lon")
        diff_after["longitude"] = module.params["longitude"]

    sntp = current.get("sntp", {})
    if module.params["sntp_server"] is not None and sntp.get("server") != module.params["sntp_server"]:
        changes.setdefault("sntp", {})["server"] = module.params["sntp_server"]
        diff_before["sntp_server"] = sntp.get("server")
        diff_after["sntp_server"] = module.params["sntp_server"]

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
