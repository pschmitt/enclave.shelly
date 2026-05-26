#!/usr/bin/python

DOCUMENTATION = '''
---
module: ws
short_description: Configure Shelly outbound websocket settings on gen 2+ devices.
version_added: "0.28.0"
description:
  - Reads current outbound websocket configuration via C(Ws.GetConfig).
  - Updates the enable flag when it differs from the requested value.
  - Shelly gen 1 devices and devices without outbound websocket support are
    silently skipped.
options:
    enable:
        description:
          - Whether outbound websocket connectivity should be enabled.
        required: true
        type: bool
author:
    - pschmitt
'''

EXAMPLES = '''
- name: Disable outbound websocket
  enclave.shelly.ws:
    enable: false
'''

RETURN = '''
changed:
  description: Whether the outbound websocket setting was changed.
  returned: always
  type: bool
restart_required:
  description: Whether the device must be rebooted for the config change to apply.
  returned: always
  type: bool
skipped_unsupported:
  description: True when the device does not expose outbound websocket configuration.
  returned: always
  type: bool
'''

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.basic import to_text
from ansible.module_utils.connection import Connection

import ansible_collections.enclave.shelly.plugins.module_utils.helpers as shelly_utils


def run_module():
    module = AnsibleModule(
        argument_spec={
            "enable": {"type": "bool", "required": True},
        },
        supports_check_mode=True,
    )

    connection = Connection(module._socket_path)
    if shelly_utils.get_device_generation(connection) == 1:
        module.exit_json(changed=False, restart_required=False, skipped_unsupported=True)

    try:
        current = connection.send_request(data={"method": "Ws.GetConfig"})
    except Exception as exc:
        exc_text = to_text(exc)
        if "No handler" in exc_text or "404" in exc_text or "not support" in exc_text:
            module.exit_json(changed=False, restart_required=False, skipped_unsupported=True)
        raise

    desired = module.params["enable"]
    current_enable = current.get("enable")
    changed = current_enable != desired
    result = dict(
        changed=changed,
        restart_required=False,
        skipped_unsupported=False,
        diff={
            "before": {"enable": current_enable},
            "after": {"enable": desired},
        },
    )

    if not changed or module.check_mode:
        module.exit_json(**result)

    response = connection.send_request(
        data={
            "method": "Ws.SetConfig",
            "params": {"config": {"enable": desired}},
        }
    )
    result["restart_required"] = bool(response.get("restart_required", False))
    module.exit_json(**result)


def main():
    run_module()


if __name__ == "__main__":
    main()
