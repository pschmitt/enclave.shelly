#!/usr/bin/python

DOCUMENTATION = '''
---
module: cors
short_description: Configure HTTP CORS on Shelly devices that expose the setting.
version_added: "0.29.5"
description:
  - Reads the current CORS state via C(Sys.GetConfig).
  - Updates the setting when it differs from the requested value.
  - Devices that do not expose the setting are silently skipped.
options:
    enabled:
        description:
          - Whether cross-origin requests should be allowed.
        required: true
        type: bool
author:
    - pschmitt
'''

EXAMPLES = '''
- name: Disable Shelly CORS
  enclave.shelly.cors:
    enabled: false
'''

RETURN = '''
changed:
  description: Whether the CORS setting changed.
  returned: always
  type: bool
skipped_unsupported:
  description: True when the device does not expose a CORS setting.
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
    current = config.get("web", {}).get("allow_cross_origin")

    if current is None:
        module.exit_json(changed=False, skipped_unsupported=True)

    desired = module.params["enabled"]
    changed = current != desired
    diff = {"before": {"allow_cross_origin": current}, "after": {"allow_cross_origin": desired}}
    result = dict(changed=changed, skipped_unsupported=False, diff=diff)

    if not changed or module.check_mode:
        module.exit_json(**result)

    connection.send_request(
        data={
            "method": "Sys.SetConfig",
            "params": {"config": {"web": {"allow_cross_origin": desired}}},
        }
    )
    module.exit_json(**result)


def main():
    run_module()


if __name__ == "__main__":
    main()
