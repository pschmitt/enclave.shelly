#!/usr/bin/python

DOCUMENTATION = '''
---
module: consumption_type
short_description: Set the consumption (appliance) type for a Shelly switch channel.
version_added: "0.18.0"
description:
  - Reads the current consumption type via Sys.GetConfig (gen 2+) or from the
    relay's C(appliance_type) field (gen 1).
  - Updates the type when it differs from the requested value.
  - Devices that do not expose consumption type settings are silently skipped.
options:
    id:
        description:
          - Numeric channel identifier.
        required: true
        type: int
    consumption_type:
        description:
          - Desired consumption type.
          - Common values are C(light), C(switch), C(socket), C(outlet).
        required: true
        type: str
author:
    - pschmitt
'''

EXAMPLES = '''
- name: Set channel 0 as a light circuit
  enclave.shelly.consumption_type:
    id: 0
    consumption_type: light

- name: Set channel 0 as a socket
  enclave.shelly.consumption_type:
    id: 0
    consumption_type: socket
'''

RETURN = '''
changed:
  description: Whether the consumption type was changed.
  returned: always
  type: bool
skipped_unsupported:
  description: True when the device does not expose consumption type settings.
  returned: always
  type: bool
'''

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.connection import Connection


def run_module():
    module = AnsibleModule(
        argument_spec={
            "id": {"type": "int", "required": True},
            "consumption_type": {"type": "str", "required": True},
        },
        supports_check_mode=True,
    )

    connection = Connection(module._socket_path)
    config = connection.send_request(data={"method": "Sys.GetConfig"})

    # ui_data absent entirely means the device doesn't support this at all
    if "ui_data" not in config:
        module.exit_json(changed=False, skipped_unsupported=True)

    channel_id = module.params["id"]
    desired = module.params["consumption_type"].lower()

    current_types = config.get("ui_data", {}).get("consumption_types") or []
    current_raw = current_types[channel_id] if channel_id < len(current_types) else None
    current = current_raw.lower() if current_raw is not None else None

    changed = current != desired
    diff = {"before": {"consumption_type": current}, "after": {"consumption_type": desired}}
    result = dict(changed=changed, skipped_unsupported=False, diff=diff)

    if not changed or module.check_mode:
        module.exit_json(**result)

    new_types = list(current_types)
    while len(new_types) <= channel_id:
        new_types.append(None)
    new_types[channel_id] = desired

    connection.send_request(
        data={
            "method": "Sys.SetConfig",
            "params": {"config": {"ui_data": {"consumption_types": new_types}}},
        }
    )
    module.exit_json(**result)


def main():
    run_module()


if __name__ == "__main__":
    main()
