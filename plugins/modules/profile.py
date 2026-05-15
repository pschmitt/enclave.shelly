#!/usr/bin/python

DOCUMENTATION = '''
---
module: profile
short_description: Configure the device operating profile on a Shelly device.
version_added: "0.20.0"
description:
  - Reads the current device profile from Sys.GetConfig.
  - Sets the profile via Sys.SetConfig when it differs.
  - Skips silently on devices that do not expose a profile field (e.g. gen 1,
    or single-function gen 2+ devices).
  - A restart is required for profile changes to take effect.
options:
    profile:
        description:
          - Desired device profile. Common values are C(cover) and C(switch).
        required: true
        type: str
author:
    - pschmitt
'''

EXAMPLES = '''
- name: Set device to cover profile
  enclave.shelly.profile:
    profile: cover
'''

RETURN = '''
changed:
  description: Whether the profile was changed.
  returned: always
  type: bool
restart_required:
  description: Whether a device restart is required for the change to take effect.
  returned: always
  type: bool
skipped_unsupported:
  description: True when the device does not expose a configurable profile field.
  returned: always
  type: bool
'''

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.connection import Connection


def run_module():
    module = AnsibleModule(
        argument_spec={"profile": {"type": "str", "required": True}},
        supports_check_mode=True,
    )
    connection = Connection(module._socket_path)
    config = connection.send_request(data={"method": "Sys.GetConfig"})
    current = config.get("device", {}).get("profile")
    if current is None:
        module.exit_json(changed=False, restart_required=False, skipped_unsupported=True)
    desired = module.params["profile"]
    changed = current != desired
    diff = {"before": {"profile": current}, "after": {"profile": desired}}
    result = dict(changed=changed, restart_required=False, skipped_unsupported=False, diff=diff)
    if not changed or module.check_mode:
        module.exit_json(**result)
    connection.send_request(data={
        "method": "Sys.SetConfig",
        "params": {"config": {"device": {"profile": desired}}},
    })
    result["restart_required"] = True
    module.exit_json(**result)


def main():
    run_module()


if __name__ == "__main__":
    main()
