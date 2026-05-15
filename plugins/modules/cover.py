#!/usr/bin/python

DOCUMENTATION = '''
---
module: cover
short_description: Configure cover component settings on a Shelly gen 1+ device.
version_added: "0.20.0"
description:
  - Reads the current configuration for a Shelly cover (roller) component.
  - Updates name, direction inversion, and obstruction detection when they differ.
  - All parameters except C(id) are optional; omitting one leaves it unchanged.
options:
    id:
        description:
          - Numeric cover channel identifier.
        required: true
        type: int
    name:
        description:
          - Desired display name for this cover channel.
        required: false
        type: str
    swap_direction:
        description:
          - Invert the cover movement direction.
        required: false
        type: bool
    obstruction_enable:
        description:
          - Enable obstruction detection.
        required: false
        type: bool
    obstruction_action:
        description:
          - Action to take when obstruction is detected. C(stop) or C(reverse).
        required: false
        type: str
author:
    - pschmitt
'''

EXAMPLES = '''
- name: Configure cover channel 0
  enclave.shelly.cover:
    id: 0
    name: Living Room Cover
    swap_direction: false
    obstruction_enable: true
    obstruction_action: stop
'''

RETURN = '''
changed:
  description: Whether any configuration was changed.
  returned: always
  type: bool
'''

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.connection import Connection


def run_module():
    module = AnsibleModule(
        argument_spec={
            "id": {"type": "int", "required": True},
            "name": {"type": "str", "required": False, "default": None},
            "swap_direction": {"type": "bool", "required": False, "default": None},
            "obstruction_enable": {"type": "bool", "required": False, "default": None},
            "obstruction_action": {"type": "str", "required": False, "default": None},
        },
        supports_check_mode=True,
    )

    connection = Connection(module._socket_path)
    current = connection.send_request(
        data={"method": "Cover.GetConfig", "params": {"id": module.params["id"]}}
    )

    changes = {}
    if module.params["name"] is not None and current.get("name") != module.params["name"]:
        changes["name"] = module.params["name"]
    if module.params["swap_direction"] is not None and current.get("invert_directions") != module.params["swap_direction"]:
        changes["invert_directions"] = module.params["swap_direction"]

    current_obs = current.get("obstruction_detection", {})
    obs_changes = {}
    if module.params["obstruction_enable"] is not None and current_obs.get("enable") != module.params["obstruction_enable"]:
        obs_changes["enable"] = module.params["obstruction_enable"]
    if module.params["obstruction_action"] is not None and current_obs.get("action") != module.params["obstruction_action"]:
        obs_changes["action"] = module.params["obstruction_action"]
    if obs_changes:
        changes["obstruction_detection"] = obs_changes

    diff_before = {}
    diff_after = {}
    for k, v in changes.items():
        if k == "obstruction_detection":
            diff_before[k] = {ck: current_obs.get(ck) for ck in v}
            diff_after[k] = dict(v)
        else:
            diff_before[k] = current.get(k)
            diff_after[k] = v
    diff = {"before": diff_before, "after": diff_after}

    result = dict(changed=bool(changes), diff=diff)

    if not changes or module.check_mode:
        module.exit_json(**result)

    connection.send_request(data={
        "method": "Cover.SetConfig",
        "params": {"id": module.params["id"], "config": changes},
    })
    module.exit_json(**result)


def main():
    run_module()


if __name__ == "__main__":
    main()
