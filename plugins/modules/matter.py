#!/usr/bin/python

DOCUMENTATION = '''
---
module: matter
short_description: Configure Matter support on Shelly devices that expose the Matter component.
version_added: "0.29.3"
description:
  - Reads current Matter configuration via C(Matter.GetConfig).
  - Updates the Matter enable flag when it differs.
  - Devices without a Matter component are silently skipped.
options:
    enable:
        description:
          - Whether Matter should be enabled.
        required: true
        type: bool
author:
    - pschmitt
'''

EXAMPLES = '''
- name: Enable Matter
  enclave.shelly.matter:
    enable: true

- name: Disable Matter
  enclave.shelly.matter:
    enable: false
'''

RETURN = '''
changed:
  description: Whether the Matter setting changed.
  returned: always
  type: bool
restart_required:
  description: Whether the device must be rebooted for the config change to apply.
  returned: always
  type: bool
skipped_unsupported:
  description: True when the device does not expose the Matter component.
  returned: always
  type: bool
'''

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.basic import to_text
from ansible.module_utils.connection import Connection

import ansible_collections.enclave.shelly.plugins.module_utils.helpers as shelly_utils


def has_matter_component(connection):
    methods = connection.send_request(data={"method": "Shelly.ListMethods"}).get("methods", [])
    return "Matter.GetConfig" in methods and "Matter.SetConfig" in methods


def run_module():
    module = AnsibleModule(
        argument_spec={
            "enable": {"type": "bool", "required": True},
        },
        supports_check_mode=True,
    )

    connection = Connection(module._socket_path)
    if shelly_utils.get_device_generation(connection) == 1:
        module.exit_json(changed=False, restart_required=False, skipped_unsupported=True)

    if not has_matter_component(connection):
        module.exit_json(changed=False, restart_required=False, skipped_unsupported=True)

    try:
        current = connection.send_request(data={"method": "Matter.GetConfig"})
    except Exception as exc:
        exc_text = to_text(exc)
        if "No handler" in exc_text or "404" in exc_text:
            module.exit_json(changed=False, restart_required=False, skipped_unsupported=True)
        raise

    desired_enable = module.params["enable"]
    current_enable = current.get("enable")
    changed = current_enable != desired_enable
    result = dict(
        changed=changed,
        restart_required=False,
        skipped_unsupported=False,
        diff={
            "before": {"enable": current_enable},
            "after": {"enable": desired_enable},
        },
    )

    if not changed or module.check_mode:
        module.exit_json(**result)

    response = connection.send_request(
        data={
            "method": "Matter.SetConfig",
            "params": {"config": {"enable": desired_enable}},
        }
    )
    result["restart_required"] = bool(response.get("restart_required", False))
    module.exit_json(**result)


def main():
    run_module()


if __name__ == "__main__":
    main()
