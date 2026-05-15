#!/usr/bin/python

DOCUMENTATION = '''
---
module: input
short_description: Configure input component settings on a Shelly gen 1+ device.
version_added: "0.11.0"
description:
  - Reads the current configuration for a Shelly input component.
  - Updates enable and/or factory_reset when they differ from the requested values.
  - On gen 1 devices C(factory_reset) maps to the C(pon_wifi_reset) setting
    (factory reset by power-toggling five times). C(enable) maps to C(btn_type)
    on devices that expose it; devices without a configurable button (e.g.
    Plug S) silently ignore C(enable).
options:
    id:
        description:
          - Numeric input channel identifier.
        required: true
        type: int
    enable:
        description:
          - Whether the input is enabled.
          - When omitted the current value is left unchanged.
        required: false
        type: bool
    factory_reset:
        description:
          - Whether the input is allowed to trigger a factory reset.
          - When omitted the current value is left unchanged.
        required: false
        type: bool
author:
    - pschmitt
'''

EXAMPLES = '''
- name: Disable factory reset on input 0
  enclave.shelly.input:
    id: 0
    factory_reset: false

- name: Disable input 0 and prevent factory reset
  enclave.shelly.input:
    id: 0
    enable: false
    factory_reset: false
'''

RETURN = '''
changed:
  description: Whether the input configuration was changed.
  returned: always
  type: bool
previous_config:
  description: Input configuration before the change.
  returned: always
  type: dict
'''

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.connection import Connection


def get_input_config(channel_id, connection):
    return connection.send_request(
        data={
            "method": "Input.GetConfig",
            "params": {"id": channel_id},
        }
    )


def set_input_config(channel_id, config, connection):
    return connection.send_request(
        data={
            "method": "Input.SetConfig",
            "params": {"id": channel_id, "config": config},
        }
    )


def run_module():
    module = AnsibleModule(
        argument_spec={
            "id": {"type": "int", "required": True},
            "enable": {"type": "bool", "required": False, "default": None},
            "factory_reset": {"type": "bool", "required": False, "default": None},
        },
        supports_check_mode=True,
    )

    connection = Connection(module._socket_path)
    current = get_input_config(module.params["id"], connection)

    if "code" in current:
        module.fail_json(
            msg=f"Input.GetConfig for id {module.params['id']} failed: {current}",
            response=current,
        )

    desired = {}
    if module.params["enable"] is not None:
        desired["enable"] = module.params["enable"]
    if module.params["factory_reset"] is not None:
        desired["factory_reset"] = module.params["factory_reset"]

    if not desired:
        module.exit_json(changed=False, previous_config=current)

    changes = {k: v for k, v in desired.items() if current.get(k) != v}

    result = dict(changed=bool(changes), previous_config=current)

    if not changes or module.check_mode:
        module.exit_json(**result)

    set_input_config(module.params["id"], changes, connection)
    module.exit_json(**result)


def main():
    run_module()


if __name__ == "__main__":
    main()
