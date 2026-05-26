#!/usr/bin/python

DOCUMENTATION = '''
---
module: cloud
short_description: Configure Shelly cloud connectivity on gen 1+ devices.
version_added: "0.28.0"
description:
  - Reads current cloud connectivity configuration via C(Cloud.GetConfig).
  - Updates the cloud enable flag when it differs from the requested value.
options:
    enable:
        description:
          - Whether Shelly Cloud connectivity should be enabled.
        required: true
        type: bool
author:
    - pschmitt
'''

EXAMPLES = '''
- name: Disable Shelly Cloud
  enclave.shelly.cloud:
    enable: false
'''

RETURN = '''
changed:
  description: Whether the cloud setting was changed.
  returned: always
  type: bool
restart_required:
  description: Whether the device must be rebooted for the config change to apply.
  returned: always
  type: bool
'''

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.connection import Connection


def run_module():
    module = AnsibleModule(
        argument_spec={
            "enable": {"type": "bool", "required": True},
        },
        supports_check_mode=True,
    )

    connection = Connection(module._socket_path)
    current = connection.send_request(data={"method": "Cloud.GetConfig"})
    desired = module.params["enable"]
    current_enable = current.get("enable")

    changed = current_enable != desired
    result = dict(
        changed=changed,
        restart_required=False,
        diff={
            "before": {"enable": current_enable},
            "after": {"enable": desired},
        },
    )

    if not changed or module.check_mode:
        module.exit_json(**result)

    response = connection.send_request(
        data={
            "method": "Cloud.SetConfig",
            "params": {"config": {"enable": desired}},
        }
    )
    result["restart_required"] = bool(response.get("restart_required", False))
    module.exit_json(**result)


def main():
    run_module()


if __name__ == "__main__":
    main()
