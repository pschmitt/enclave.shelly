#!/usr/bin/python

DOCUMENTATION = '''
---
module: switch
short_description: Configure switch component settings on a Shelly gen 2+ device.
version_added: "0.10.0"
description:
  - Reads the current configuration for a Shelly switch component.
  - Updates the switch input mode when it differs from the requested value.
options:
    id:
        description:
          - Numeric switch/input channel identifier.
        required: true
        type: int
    in_mode:
        description:
          - Desired Shelly switch input mode.
          - Common values include C(flip), C(follow), and C(detached).
        required: true
        type: str
author:
    - Copilot
'''

EXAMPLES = '''
- name: Set Shelly switch 0 to flip mode
  enclave.shelly.switch:
    id: 0
    in_mode: flip
'''

RETURN = '''
previous_in_mode:
  description: Previously configured switch input mode on the Shelly device.
  returned: always
  type: str
in_mode:
  description: Requested switch input mode on the Shelly device.
  returned: always
  type: str
restart_required:
  description: Set to true if Shelly device should be restarted for the changes to take full effect.
  returned: always
  type: bool
'''

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.connection import Connection


def get_switch_config(channel_id, connection):
    return connection.send_request(
        data={
            "method": "Switch.GetConfig",
            "params": {
                "id": channel_id
            }
        }
    )


def set_switch_input_mode(channel_id, in_mode, connection):
    return connection.send_request(
        data={
            "method": "Switch.SetConfig",
            "params": {
                "id": channel_id,
                "config": {
                    "in_mode": in_mode
                }
            }
        }
    )


def run_module():
    module = AnsibleModule(
        argument_spec={
            "id": {"type": "int", "required": True},
            "in_mode": {"type": "str", "required": True},
        },
        supports_check_mode=True,
    )

    connection = Connection(module._socket_path)
    current_config = get_switch_config(module.params["id"], connection)
    current_in_mode = current_config.get("in_mode")

    if current_in_mode is None:
        module.fail_json(
            msg=f"Shelly switch {module.params['id']} did not return an in_mode field.",
            config=current_config,
        )

    result = dict(
        changed=False,
        previous_in_mode=current_in_mode,
        in_mode=module.params["in_mode"],
        restart_required=False,
    )

    if current_in_mode == module.params["in_mode"]:
        module.exit_json(**result)

    result["changed"] = True

    if module.check_mode:
        module.exit_json(**result)

    set_result = set_switch_input_mode(module.params["id"], module.params["in_mode"], connection)
    result["restart_required"] = set_result.get("restart_required", False)
    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()
