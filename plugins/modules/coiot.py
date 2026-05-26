#!/usr/bin/python

DOCUMENTATION = '''
---
module: coiot
short_description: Configure CoIoT settings on Shelly gen 1 devices.
version_added: "0.29.0"
description:
  - Reads current CoIoT configuration via C(CoIoT.GetConfig).
  - Updates the CoIoT enable flag, peer, and update period when they differ.
  - Shelly devices without gen 1 CoIoT support are silently skipped.
options:
    enable:
        description:
          - Whether CoIoT should be enabled.
        required: false
        type: bool
    peer:
        description:
          - CoIoT peer target.
          - Use C(mcast) for multicast discovery.
          - Use C(ip[:port]) for a unicast peer.
        required: false
        type: str
    update_period:
        description:
          - Update period for CoIoT messages in seconds.
        required: false
        type: int
author:
    - pschmitt
'''

EXAMPLES = '''
- name: Enable CoIoT multicast discovery
  enclave.shelly.coiot:
    enable: true
    peer: mcast

- name: Point CoIoT to a unicast peer
  enclave.shelly.coiot:
    peer: 192.0.2.10:5683
'''

RETURN = '''
changed:
  description: Whether any CoIoT setting changed.
  returned: always
  type: bool
restart_required:
  description: Whether the device must be rebooted for the config change to apply.
  returned: always
  type: bool
skipped_unsupported:
  description: True when the device does not expose gen 1 CoIoT settings.
  returned: always
  type: bool
'''

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.connection import Connection

import ansible_collections.enclave.shelly.plugins.module_utils.helpers as shelly_utils


def normalize_peer(value):
    if value in (None, "", "mcast"):
        return "mcast"

    return value


def run_module():
    module = AnsibleModule(
        argument_spec={
            "enable": {"type": "bool", "required": False, "default": None},
            "peer": {"type": "str", "required": False, "default": None},
            "update_period": {"type": "int", "required": False, "default": None},
        },
        supports_check_mode=True,
    )

    connection = Connection(module._socket_path)
    if shelly_utils.get_device_generation(connection) != 1:
        module.exit_json(changed=False, restart_required=False, skipped_unsupported=True)

    current = connection.send_request(data={"method": "CoIoT.GetConfig"})

    desired_enable = module.params["enable"]
    desired_peer = normalize_peer(module.params["peer"])
    desired_update_period = module.params["update_period"]

    changes = {}
    diff_before = {}
    diff_after = {}

    current_enable = current.get("enable")
    if desired_enable is not None and current_enable != desired_enable:
        changes["enable"] = desired_enable
        diff_before["enable"] = current_enable
        diff_after["enable"] = desired_enable

    current_peer = normalize_peer(current.get("peer"))
    if desired_peer is not None and current_peer != desired_peer:
        changes["peer"] = desired_peer
        diff_before["peer"] = current_peer
        diff_after["peer"] = desired_peer

    current_update_period = current.get("update_period")
    if desired_update_period is not None and current_update_period != desired_update_period:
        changes["update_period"] = desired_update_period
        diff_before["update_period"] = current_update_period
        diff_after["update_period"] = desired_update_period

    result = dict(
        changed=bool(changes),
        restart_required=False,
        skipped_unsupported=False,
        diff={"before": diff_before, "after": diff_after},
    )

    if not changes or module.check_mode:
        module.exit_json(**result)

    response = connection.send_request(
        data={
            "method": "CoIoT.SetConfig",
            "params": {"config": changes},
        }
    )
    result["restart_required"] = bool(response.get("restart_required", False))
    module.exit_json(**result)


def main():
    run_module()


if __name__ == "__main__":
    main()
