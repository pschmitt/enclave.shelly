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
  - Password rotations while authentication is already enabled must be requested
    explicitly via O(update_password) because the device does not expose the
    current password or hash for comparison.
options:
    username:
        description:
          - Username to use for API authentication.
          - Shelly gen 2+ devices only support C(admin).
        required: false
        type: str
        default: admin
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
    update_password:
        description:
          - Force updating the password even when authentication is already enabled.
          - Use this when rotating the API password.
        required: false
        type: bool
        default: false
author:
    - RustedSkull (@skull132)
'''

EXAMPLES = '''
# Enable authentication, set the password to "abc"
- name: Enable auth.
  enclave.shelly.auth:
    username: admin
    enable: true
    password: abc

# Disable authentication.
- name: Disable auth.
  enclave.shelly.auth:
    enable: false

# Rotate the password while auth is already enabled.
- name: Rotate auth password
  enclave.shelly.auth:
    username: admin
    enable: true
    password: def
    update_password: true
'''

RETURN = '''
changed:
  description: Whether the auth setting changed or the password was rotated.
  returned: always
  type: bool
restart_required:
  description: Whether the device must be rebooted for the config change to apply.
  returned: always
  type: bool
password_updated:
  description: True when the password was rotated while auth stayed enabled.
  returned: always
  type: bool
'''

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.connection import Connection

import ansible_collections.enclave.shelly.plugins.module_utils.helpers as shelly_utils

def run_module():
    module_args = dict(
        username=dict(type="str", required=False, default="admin"),
        enable=dict(type="bool", required=True),
        password=dict(type="str", required=False, no_log=True),
        update_password=dict(type="bool", required=False, default=False),
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True,
        required_if=[("enable", True, ("password",), False)]
    )

    result = dict(
        changed=False,
        restart_required=False,
        password_updated=False,
    )

    connection = Connection(module._socket_path)
    desired_username = module.params["username"]
    desired_enable = module.params["enable"]
    update_password = module.params["update_password"] and desired_enable

    if shelly_utils.get_device_generation(connection) == 1:
        current = connection.send_request(data={"method": "Auth.GetConfig"})
        current_enable = current.get("enabled")
        result["password_updated"] = bool(current_enable and update_password)
        result["changed"] = (
            current_enable != desired_enable
            or result["password_updated"]
            or bool(
                desired_enable
                and current_enable
                and current.get("username") != desired_username
            )
        )
        result["diff"] = {
            "before": {
                "enable": current_enable,
                "username": current.get("username"),
            },
            "after": {
                "enable": desired_enable,
                "username": desired_username if desired_enable else None,
            },
        }
        if not result["changed"] or module.check_mode:
            module.exit_json(**result)

        params = {"enabled": desired_enable}
        if desired_enable:
            params["unprotected"] = False
            params["username"] = desired_username
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
    if desired_enable and desired_username != "admin":
        module.fail_json(
            msg=(
                "Shelly gen2+ devices only support the 'admin' API username. "
                f"Requested username: {desired_username!r}"
            )
        )
    result["password_updated"] = bool(current_enable and update_password)
    result["changed"] = current_enable != desired_enable or result["password_updated"]
    result["diff"] = {
        "before": {"enable": current_enable, "username": "admin"},
        "after": {"enable": desired_enable, "username": "admin" if desired_enable else None},
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
                "user": desired_username,
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
