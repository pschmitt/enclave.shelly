#!/usr/bin/python

DOCUMENTATION = '''
---
module: discoverable
short_description: Configure Shelly device discoverability on a gen 1+ device.
version_added: "0.26.0"
description:
  - Reads the current discoverable state via Sys.GetConfig.
  - Updates the setting when it differs from the requested value.
  - Devices that do not expose the setting are silently skipped.
options:
    enabled:
        description:
          - Whether the device should be discoverable.
        required: true
        type: bool
author:
    - pschmitt
'''

EXAMPLES = '''
- name: Enable Shelly discoverability
  enclave.shelly.discoverable:
    enabled: true

- name: Disable Shelly discoverability
  enclave.shelly.discoverable:
    enabled: false
'''

RETURN = '''
changed:
  description: Whether the discoverable setting was changed.
  returned: always
  type: bool
skipped_unsupported:
  description: True when the device does not expose a discoverable setting.
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
    current = config.get("device", {}).get("discoverable")

    if current is None:
        module.exit_json(changed=False, skipped_unsupported=True)

    desired = module.params["enabled"]
    changed = current != desired
    diff = {"before": {"discoverable": current}, "after": {"discoverable": desired}}
    result = dict(changed=changed, skipped_unsupported=False, diff=diff)

    if not changed or module.check_mode:
        module.exit_json(**result)

    connection.send_request(
        data={
            "method": "Sys.SetConfig",
            "params": {"config": {"device": {"discoverable": desired}}},
        }
    )
    module.exit_json(**result)


def main():
    run_module()


if __name__ == "__main__":
    main()
