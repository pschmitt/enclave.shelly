#!/usr/bin/python

DOCUMENTATION = '''
---
module: name
short_description: Set the display name of a Shelly gen 1+ device.
version_added: "0.12.0"
description:
  - Reads the current device name via Sys.GetConfig (gen 2+) or /settings (gen 1).
  - Updates the name when it differs from the requested value.
options:
    name:
        description:
          - The desired display name for the device.
        required: true
        type: str
author:
    - pschmitt
'''

EXAMPLES = '''
- name: Set device name
  enclave.shelly.name:
    name: "Living Room Light"
'''

RETURN = '''
changed:
  description: Whether the device name was changed.
  returned: always
  type: bool
previous_name:
  description: The device name before the change.
  returned: always
  type: str
'''

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.connection import Connection


def get_device_name(connection):
    config = connection.send_request(data={"method": "Sys.GetConfig"})
    return config.get("device", {}).get("name")


def set_device_name(name, connection):
    return connection.send_request(
        data={
            "method": "Sys.SetConfig",
            "params": {"config": {"device": {"name": name}}},
        }
    )


def run_module():
    module = AnsibleModule(
        argument_spec={
            "name": {"type": "str", "required": True},
        },
        supports_check_mode=True,
    )

    connection = Connection(module._socket_path)
    current_name = get_device_name(connection)
    desired_name = module.params["name"]

    changed = current_name != desired_name
    diff = {"before": {"name": current_name}, "after": {"name": desired_name}}
    result = dict(changed=changed, previous_name=current_name, diff=diff)

    if not changed or module.check_mode:
        module.exit_json(**result)

    set_device_name(desired_name, connection)
    module.exit_json(**result)


def main():
    run_module()


if __name__ == "__main__":
    main()
