#!/usr/bin/python

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.facts.compat import ansible_facts
from ansible.module_utils.connection import Connection


def run_module():
    module_args = dict(
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )

    connection = Connection(module._socket_path)

    status = connection.send_request(
        data={
            "method": "Shelly.GetStatus"
        }
    )

    result = dict(
        changed=False
    )

    device_info = connection.send_request(
        data={
            "method": "Shelly.GetDeviceInfo"
        }
    )

    result["ansible_facts"] = {
        "shelly": {
            "device": device_info,
            "status": status
        }
    }

    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()
