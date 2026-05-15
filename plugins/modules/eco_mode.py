#!/usr/bin/python

DOCUMENTATION = '''
---
module: eco_mode
short_description: Configure eco mode on a Shelly gen 1+ device.
version_added: "0.16.0"
description:
  - Reads the current eco mode state via Sys.GetConfig (gen 2+) or /settings
    (gen 1, C(eco_mode_enabled) field).
  - Updates the setting when it differs from the requested value.
  - Devices that do not support eco mode are silently skipped (the setting
    is absent from their config response).
options:
    enabled:
        description:
          - Whether eco mode should be enabled.
        required: true
        type: bool
author:
    - pschmitt
'''

EXAMPLES = '''
- name: Enable eco mode
  enclave.shelly.eco_mode:
    enabled: true

- name: Disable eco mode
  enclave.shelly.eco_mode:
    enabled: false
'''

RETURN = '''
changed:
  description: Whether eco mode was changed.
  returned: always
  type: bool
skipped_unsupported:
  description: True when the device does not expose an eco mode setting.
  returned: always
  type: bool
'''

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.connection import Connection


def run_module():
    module = AnsibleModule(
        argument_spec={
            "enabled": {"type": "bool", "required": True},
        },
        supports_check_mode=True,
    )

    connection = Connection(module._socket_path)
    config = connection.send_request(data={"method": "Sys.GetConfig"})
    current = config.get("device", {}).get("eco_mode")

    if current is None:
        module.exit_json(changed=False, skipped_unsupported=True)

    desired = module.params["enabled"]
    changed = current != desired
    diff = {"before": {"eco_mode": current}, "after": {"eco_mode": desired}}
    result = dict(changed=changed, skipped_unsupported=False, diff=diff)

    if not changed or module.check_mode:
        module.exit_json(**result)

    connection.send_request(
        data={
            "method": "Sys.SetConfig",
            "params": {"config": {"device": {"eco_mode": desired}}},
        }
    )
    module.exit_json(**result)


def main():
    run_module()


if __name__ == "__main__":
    main()
