#!/usr/bin/python

DOCUMENTATION = '''
---
module: led
short_description: Configure LED indicator settings on a Shelly device.
version_added: "0.18.0"
description:
  - Reads the current LED state via Sys.GetConfig (gen 1+).
  - Updates the LED settings when they differ from the requested values.
  - Devices that do not expose LED settings are silently skipped.
  - C(status) controls the status indicator LED.
  - C(power) controls the power indicator LED (supported on gen 1 Plug S).
options:
    status:
        description:
          - Whether the status LED should be enabled.
          - When omitted the current value is left unchanged.
        required: false
        type: bool
    power:
        description:
          - Whether the power LED should be enabled.
          - When omitted the current value is left unchanged.
        required: false
        type: bool
author:
    - pschmitt
'''

EXAMPLES = '''
- name: Disable both LEDs
  enclave.shelly.led:
    status: false
    power: false

- name: Enable status LED only
  enclave.shelly.led:
    status: true
    power: false
'''

RETURN = '''
changed:
  description: Whether LED settings were changed.
  returned: always
  type: bool
skipped_unsupported:
  description: True when the device does not expose LED settings.
  returned: always
  type: bool
'''

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.connection import Connection


def run_module():
    module = AnsibleModule(
        argument_spec={
            "status": {"type": "bool", "required": False, "default": None},
            "power": {"type": "bool", "required": False, "default": None},
        },
        supports_check_mode=True,
    )

    connection = Connection(module._socket_path)
    config = connection.send_request(data={"method": "Sys.GetConfig"})
    current_leds = config.get("device", {}).get("leds")

    if current_leds is None:
        module.exit_json(changed=False, skipped_unsupported=True)

    desired = {}
    if module.params["status"] is not None:
        desired["status"] = module.params["status"]
    if module.params["power"] is not None:
        desired["power"] = module.params["power"]

    if not desired:
        module.exit_json(changed=False, skipped_unsupported=False)

    changes = {k: v for k, v in desired.items() if current_leds.get(k) != v}

    diff = {
        "before": {k: current_leds.get(k) for k in changes},
        "after": dict(changes),
    }
    result = dict(changed=bool(changes), skipped_unsupported=False, diff=diff)

    if not changes or module.check_mode:
        module.exit_json(**result)

    connection.send_request(
        data={
            "method": "Sys.SetConfig",
            "params": {"config": {"device": {"leds": changes}}},
        }
    )
    module.exit_json(**result)


def main():
    run_module()


if __name__ == "__main__":
    main()
