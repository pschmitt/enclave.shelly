#!/usr/bin/python

DOCUMENTATION = '''
---
module: reboot
short_description: Reboot a Shelly device.
version_added: "0.20.0"
description:
  - Sends a reboot command to a Shelly device.
  - Always reports changed. Skipped in check mode.
options: {}
author:
    - pschmitt
'''

EXAMPLES = '''
- name: Reboot Shelly device
  enclave.shelly.reboot:
'''

RETURN = '''
changed:
  description: Always true unless in check mode.
  returned: always
  type: bool
'''

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.connection import Connection


def run_module():
    module = AnsibleModule(
        argument_spec={},
        supports_check_mode=True,
    )
    result = dict(changed=True)
    if module.check_mode:
        module.exit_json(**result)
    connection = Connection(module._socket_path)
    connection.send_request(data={"method": "Shelly.Reboot"})
    module.exit_json(**result)


def main():
    run_module()


if __name__ == "__main__":
    main()
