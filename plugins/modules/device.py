#!/usr/bin/python

DOCUMENTATION = '''
---
module: device
short_description: A module for restarting a Shelly gen 2+ device.
version_added: "0.0.1"
description:
  - "A module for restarting a Shelly gen 2+ device."
options:
    state:
        description:
          - Used to control the state of the device. Currently only "restarted" is supported.
        required: true
        type: str
        default: restarted
        choices: ["restarted"]
    timeout:
        description:
          - In milliseconds. Determines how long to wait until the module should become available again.
          - If the device is not available after the time specified, the module fails.
        required: false
        type: int
        default: 1000
author:
    - RustedSkull (@skull132)
'''

EXAMPLES = '''
# Restart the shelly device. Wait 2 seconds for it to become available again.
- name: Restart Shelly
  enclave.shelly.device:
    state: restarted
    timeout: 2000
'''

RETURN = '''
restarted:
  description: Set to true if the module issued the restart command to the Shelly device.
  type: bool
  returned: always
'''

import asyncio
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.facts.compat import ansible_facts
from ansible.module_utils.connection import Connection

async def do_restart(module: AnsibleModule) -> bool:
    connection = Connection(module._socket_path)

    _ = connection.send_request(
        data={
            "method": "Shelly.Reboot"
        }
    )

    waited = 0
    steps = 500

    device_available = False
    while waited < module.params["timeout"]:
        waited += steps
        await asyncio.sleep(steps / 1000)

        try:
            _ = connection.send_request(
                data={
                    "method": "Shelly.GetStatus"
                }
            )

            device_available = True
            break
        except:
            pass

    return device_available

def run_module():
    module_args = dict(
        state=dict(type="str", required=True, choices=["restarted"]),
        timeout=dict(type="int", required=False, default=1000)
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )

    result = dict(
        changed=True,
        restarted=False
    )

    if module.check_mode:
        result["restarted"] = True
        return module.exit_json(**result)

    if module.params["state"] == "restarted":
        result["restarted"] = True
        available = asyncio.run(do_restart(module))
        if not available:
            module.fail_json(msg="Shelly device did not become available after restart.", **result)

    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()