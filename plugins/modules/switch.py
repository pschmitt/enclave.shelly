#!/usr/bin/python

DOCUMENTATION = '''
---
module: switch
short_description: Configure switch component settings on a Shelly gen 1+ device.
version_added: "0.10.0"
description:
  - Reads the current configuration for a Shelly switch (or relay) component.
  - Updates any combination of in_mode, auto_on/off timers when they differ
    from the requested values.
  - All parameters except C(id) are optional; omitting one leaves it unchanged.
options:
    id:
        description:
          - Numeric switch/input channel identifier.
        required: true
        type: int
    in_mode:
        description:
          - Desired switch input mode.
          - Common values are C(flip), C(follow), and C(detached).
        required: false
        type: str
    auto_on:
        description:
          - Enable the auto-on timer (switches the output on after C(auto_on_delay) seconds).
        required: false
        type: bool
    auto_on_delay:
        description:
          - Seconds to wait before auto-on fires. Only relevant when C(auto_on) is true.
        required: false
        type: float
    auto_off:
        description:
          - Enable the auto-off timer (switches the output off after C(auto_off_delay) seconds).
        required: false
        type: bool
    auto_off_delay:
        description:
          - Seconds to wait before auto-off fires. Only relevant when C(auto_off) is true.
        required: false
        type: float
author:
    - Copilot
    - pschmitt
'''

EXAMPLES = '''
- name: Set switch 0 to flip mode with a 30-second auto-off
  enclave.shelly.switch:
    id: 0
    in_mode: flip
    auto_off: true
    auto_off_delay: 30.0

- name: Disable auto-off on switch 0
  enclave.shelly.switch:
    id: 0
    auto_off: false
'''

RETURN = '''
changed:
  description: Whether any configuration was changed.
  returned: always
  type: bool
restart_required:
  description: Set to true if the device should be restarted for changes to take effect.
  returned: always
  type: bool
'''

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.connection import Connection

SWITCH_KEYS = ("in_mode", "auto_on", "auto_on_delay", "auto_off", "auto_off_delay")


def run_module():
    module = AnsibleModule(
        argument_spec={
            "id": {"type": "int", "required": True},
            "in_mode": {"type": "str", "required": False, "default": None},
            "auto_on": {"type": "bool", "required": False, "default": None},
            "auto_on_delay": {"type": "float", "required": False, "default": None},
            "auto_off": {"type": "bool", "required": False, "default": None},
            "auto_off_delay": {"type": "float", "required": False, "default": None},
        },
        supports_check_mode=True,
    )

    connection = Connection(module._socket_path)
    current = connection.send_request(
        data={"method": "Switch.GetConfig", "params": {"id": module.params["id"]}}
    )

    desired = {k: module.params[k] for k in SWITCH_KEYS if module.params[k] is not None}

    if not desired:
        module.exit_json(changed=False, restart_required=False)

    # Carry the current delay alongside auto_on/off so gen1 translation
    # always has the delay value when deciding the float to write.
    for prefix in ("auto_on", "auto_off"):
        delay_key = f"{prefix}_delay"
        if prefix in desired and delay_key not in desired and delay_key in current:
            desired[delay_key] = current[delay_key]

    changes = {k: v for k, v in desired.items() if current.get(k) != v}

    result = dict(changed=bool(changes), restart_required=False)

    if not changes or module.check_mode:
        module.exit_json(**result)

    set_result = connection.send_request(
        data={
            "method": "Switch.SetConfig",
            "params": {"id": module.params["id"], "config": changes},
        }
    )
    result["restart_required"] = set_result.get("restart_required", False)
    module.exit_json(**result)


def main():
    run_module()


if __name__ == "__main__":
    main()
