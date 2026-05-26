#!/usr/bin/python

DOCUMENTATION = '''
---
module: ble
short_description: Configure Bluetooth Low Energy settings on Shelly gen 2+ devices.
version_added: "0.27.0"
description:
  - Reads current BLE configuration via C(BLE.GetConfig).
  - Updates the BLE enable and RPC-over-BLE flags when they differ.
  - Shelly gen 1 devices and gen 2+ devices without a BLE component are
    silently skipped.
options:
    enable:
        description:
          - Whether BLE should be enabled.
        required: false
        type: bool
    rpc_enable:
        description:
          - Whether RPC over BLE should be enabled.
        required: false
        type: bool
author:
    - pschmitt
'''

EXAMPLES = '''
- name: Enable BLE and RPC over BLE
  enclave.shelly.ble:
    enable: true
    rpc_enable: true

- name: Disable RPC over BLE only
  enclave.shelly.ble:
    rpc_enable: false
'''

RETURN = '''
changed:
  description: Whether any BLE setting changed.
  returned: always
  type: bool
restart_required:
  description: Whether the device must be rebooted for the config change to apply.
  returned: always
  type: bool
skipped_unsupported:
  description: True when the device does not expose the BLE component.
  returned: always
  type: bool
'''

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.basic import to_text
from ansible.module_utils.connection import Connection

import ansible_collections.enclave.shelly.plugins.module_utils.helpers as shelly_utils


def has_ble_component(connection):
    methods = connection.send_request(data={"method": "Shelly.ListMethods"}).get("methods", [])
    return "BLE.GetConfig" in methods and "BLE.SetConfig" in methods


def run_module():
    module = AnsibleModule(
        argument_spec={
            "enable": {"type": "bool", "required": False, "default": None},
            "rpc_enable": {"type": "bool", "required": False, "default": None},
        },
        supports_check_mode=True,
    )

    connection = Connection(module._socket_path)
    if shelly_utils.get_device_generation(connection) == 1:
        module.exit_json(changed=False, restart_required=False, skipped_unsupported=True)

    if not has_ble_component(connection):
        module.exit_json(changed=False, restart_required=False, skipped_unsupported=True)

    try:
        current = connection.send_request(data={"method": "BLE.GetConfig"})
    except Exception as exc:
        exc_text = to_text(exc)
        if "No handler" in exc_text or "404" in exc_text:
            module.exit_json(changed=False, restart_required=False, skipped_unsupported=True)
        raise

    desired_enable = module.params["enable"]
    desired_rpc_enable = module.params["rpc_enable"]

    changes = {}
    diff_before = {}
    diff_after = {}

    if desired_enable is not None and current.get("enable") != desired_enable:
        changes["enable"] = desired_enable
        diff_before["enable"] = current.get("enable")
        diff_after["enable"] = desired_enable

    current_rpc = current.get("rpc", {})
    if desired_rpc_enable is not None and current_rpc.get("enable") != desired_rpc_enable:
        changes["rpc"] = {"enable": desired_rpc_enable}
        diff_before["rpc_enable"] = current_rpc.get("enable")
        diff_after["rpc_enable"] = desired_rpc_enable

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
            "method": "BLE.SetConfig",
            "params": {"config": changes},
        }
    )
    result["restart_required"] = bool(response.get("restart_required", False))
    module.exit_json(**result)


def main():
    run_module()


if __name__ == "__main__":
    main()
