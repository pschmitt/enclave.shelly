#!/usr/bin/python

DOCUMENTATION = '''
---
module: auth
short_description: Configure API authentication on Shelly gen 1+ devices.
version_added: "0.28.0"
description:
  - Reads current authentication state before applying changes.
  - Supports gen 2+ devices through C(Shelly.SetAuth) and gen 1 devices through
    C(/settings/login).
  - If this module is used to enable authentication, then all subsequent module
    calls need to provide the same password via C(ansible_httpapi_password).
options:
    enable:
        description:
          - Set to true to enable authentication, false to disable.
        required: true
        type: bool
    password:
        description:
          - The password to use for the device.
          - Required if enable is set to true.
        required: false
        type: str
author:
    - RustedSkull (@skull132)
'''

EXAMPLES = '''
# Enable authentication, set the password to "abc"
- name: Enable auth.
  enclave.shelly.auth:
    enable: true
    password: abc

# Disable authentication.
- name: Disable auth.
  enclave.shelly.auth:
    enable: false
'''

RETURN = '''
changed:
  description: Whether the auth setting was changed.
  returned: always
  type: bool
restart_required:
  description: Whether the device must be rebooted for the config change to apply.
  returned: always
  type: bool
'''

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.connection import Connection

import ansible_collections.enclave.shelly.plugins.module_utils.helpers as shelly_utils

def run_module():
    module_args = dict(
        enable=dict(type="bool", required=True),
        password=dict(type="str", required=False, no_log=True)
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True,
        required_if=[("enable", True, ("password"), False)]
    )

    result = dict(
        changed=False,
        restart_required=False,
    )

    connection = Connection(module._socket_path)
    desired_enable = module.params["enable"]

    if shelly_utils.get_device_generation(connection) == 1:
        current = connection.send_request(data={"method": "Auth.GetConfig"})
        current_enable = current.get("enabled")
        result["changed"] = current_enable != desired_enable
        result["diff"] = {
            "before": {"enable": current_enable},
            "after": {"enable": desired_enable},
        }
        if not result["changed"] or module.check_mode:
            module.exit_json(**result)

        params = {"enabled": desired_enable}
        if desired_enable:
            params["unprotected"] = False
            params["username"] = "admin"
            params["password"] = module.params["password"]

        connection.send_request(
            data={
                "method": "Auth.SetConfig",
                "params": {"config": params},
            }
        )
        module.exit_json(**result)

    device_info = connection.send_request(data={"method": "Shelly.GetDeviceInfo"})
    current_enable = device_info.get("auth_en")
    result["changed"] = current_enable != desired_enable
    result["diff"] = {
        "before": {"enable": current_enable},
        "after": {"enable": desired_enable},
    }

    if not result["changed"] or module.check_mode:
        module.exit_json(**result)

    realm = device_info["id"]
    if desired_enable:
        ha1 = connection.ha1(realm, module.params["password"])
    else:
        ha1 = None

    connection.send_request(
        data={
            "method": "Shelly.SetAuth",
            "params": {
                "user": "admin",
                "realm": realm,
                "ha1": ha1,
            },
        }
    )

    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()
