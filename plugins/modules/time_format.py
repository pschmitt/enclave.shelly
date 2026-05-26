#!/usr/bin/python

DOCUMENTATION = '''
---
module: time_format
short_description: Configure the 12/24-hour time display format on Shelly gen 2+ devices.
version_added: "0.24.0"
description:
  - Reads the current time display format from the C(units) KVS entry.
  - Updates the C(hour_format) field when it differs from the requested value.
  - Shelly gen 1 devices are silently skipped because they do not expose the
    KVS API used by this setting.
options:
    hour_format:
        description:
          - Desired hour display format.
        required: true
        type: int
        choices: [12, 24]
author:
    - pschmitt
'''

EXAMPLES = '''
- name: Force 24-hour time display
  enclave.shelly.time_format:
    hour_format: 24

- name: Switch to 12-hour time display
  enclave.shelly.time_format:
    hour_format: 12
'''

RETURN = '''
changed:
  description: Whether the time display format was changed.
  returned: always
  type: bool
skipped_unsupported:
  description: True when the device does not expose the required KVS setting.
  returned: always
  type: bool
'''

import json

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.connection import Connection

import ansible_collections.enclave.shelly.plugins.module_utils.helpers as shelly_utils


def get_units_entry(connection):
    response = connection.send_request(
        data={
            "method": "KVS.GetMany",
            "params": {"match": "units"},
        }
    )
    for item in response.get("items", []):
        if item.get("key") == "units":
            return item
    return None


def parse_units_value(raw_value):
    if raw_value is None:
        return {}
    if isinstance(raw_value, dict):
        return raw_value.copy()
    if isinstance(raw_value, str):
        parsed = json.loads(raw_value)
        if isinstance(parsed, dict):
            return parsed
    raise ValueError("Unsupported Shelly units value format")


def run_module():
    module = AnsibleModule(
        argument_spec={
            "hour_format": {"type": "int", "required": True, "choices": [12, 24]},
        },
        supports_check_mode=True,
    )

    connection = Connection(module._socket_path)
    if shelly_utils.get_device_generation(connection) == 1:
        module.exit_json(changed=False, skipped_unsupported=True)

    units_entry = get_units_entry(connection)
    current_units = parse_units_value(units_entry.get("value") if units_entry else None)
    desired_hour_format = module.params["hour_format"]
    current_hour_format = current_units.get("hour_format")

    changed = current_hour_format != desired_hour_format
    diff = {
        "before": {"hour_format": current_hour_format},
        "after": {"hour_format": desired_hour_format},
    }
    result = dict(changed=changed, skipped_unsupported=False, diff=diff)

    if not changed or module.check_mode:
        module.exit_json(**result)

    new_units = current_units.copy()
    new_units["hour_format"] = desired_hour_format
    params = {
        "key": "units",
        "value": json.dumps(new_units, separators=(",", ":")),
    }
    if units_entry and units_entry.get("etag"):
        params["etag"] = units_entry["etag"]

    connection.send_request(
        data={
            "method": "KVS.Set",
            "params": params,
        }
    )
    module.exit_json(**result)


def main():
    run_module()


if __name__ == "__main__":
    main()
