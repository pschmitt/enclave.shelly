#!/usr/bin/python

DOCUMENTATION = '''
---
module: protection
short_description: Configure overload protection limits on a Shelly switch channel.
version_added: "0.30.0"
description:
  - Sets the overpower (Watts), overcurrent (Amperes) and overvoltage (Volts)
    protection limits for a single Shelly switch/relay channel.
  - On gen 1 devices only the power limit is supported (mapped to the legacy
    C(max_power) relay setting); requesting a current or voltage limit on gen 1
    fails.
  - Each limit accepts a number, the magic value C(max) (which resolves to the
    device's rated maximum), or C(0) to disable that limit. Omitting a limit
    leaves it unchanged.
options:
    id:
        description:
          - Numeric switch/relay channel identifier.
        required: true
        type: int
    power_limit:
        description:
          - Overpower limit in Watts.
          - Accepts a number, C(max) (rated maximum for the device model), or
            C(0) to disable. Omit to leave unchanged.
          - On gen 1 a value above the rated maximum is clamped (with a warning)
            to avoid idempotency drift, since gen 1 silently clamps.
        required: false
        type: raw
    current_limit:
        description:
          - Overcurrent limit in Amperes. Gen 2+ only.
          - Accepts a number, C(max), or C(0) to disable. Omit to leave unchanged.
        required: false
        type: raw
    voltage_limit:
        description:
          - Overvoltage limit in Volts. Gen 2+ only.
          - Accepts a number, C(max), or C(0) to disable. Omit to leave unchanged.
        required: false
        type: raw
author:
    - pschmitt
'''

EXAMPLES = '''
- name: Cap channel 0 at the device's rated maximum power
  enclave.shelly.protection:
    id: 0
    power_limit: max

- name: Set explicit limits on a gen 2+ device
  enclave.shelly.protection:
    id: 0
    power_limit: 3000
    current_limit: 12
    voltage_limit: 260

- name: Disable the power protection on channel 0
  enclave.shelly.protection:
    id: 0
    power_limit: 0
'''

RETURN = '''
changed:
  description: Whether any protection limit was changed.
  returned: always
  type: bool
restart_required:
  description: Set to true if the device should be restarted for changes to take effect.
  returned: always
  type: bool
'''

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.connection import Connection

import ansible_collections.enclave.shelly.plugins.module_utils.helpers as shelly_utils

# (RPC/config key, friendly field name used for "max" resolution).
FIELDS = (
    ("power_limit", "power"),
    ("current_limit", "current"),
    ("voltage_limit", "voltage"),
)


def run_module():
    module = AnsibleModule(
        argument_spec={
            "id": {"type": "int", "required": True},
            "power_limit": {"type": "raw", "required": False, "default": None},
            "current_limit": {"type": "raw", "required": False, "default": None},
            "voltage_limit": {"type": "raw", "required": False, "default": None},
        },
        supports_check_mode=True,
    )

    connection = Connection(module._socket_path)

    # Coerce raw inputs (reject bools, parse numeric strings, keep "max").
    try:
        provided = {
            key: shelly_utils.coerce_limit(module.params[key])
            for key, _field in FIELDS
            if module.params[key] is not None
        }
    except ValueError as exc:
        module.fail_json(msg=str(exc))

    if not provided:
        module.exit_json(changed=False, restart_required=False)

    device_info = shelly_utils.get_device_info(connection)
    generation = device_info.get("gen")
    if generation is None:
        generation = 1 if "type" in device_info else 2

    # Gen 1 only exposes a Watts (power) limit.
    if generation == 1 and ("current_limit" in provided or "voltage_limit" in provided):
        module.fail_json(
            msg="Shelly gen1 supports only a power (Watts) limit; "
            "current/voltage protection is unavailable."
        )

    # Resolve the "max" sentinel to the device's rated maximum.
    field_for_key = dict(FIELDS)
    try:
        desired = {
            key: shelly_utils.resolve_protection_max(device_info, field_for_key[key], value)
            for key, value in provided.items()
        }
    except ValueError as exc:
        module.fail_json(msg=str(exc))

    # Gen 1 silently clamps over-rated values, which would flap "changed" on
    # every run. Clamp ourselves (with a warning) when we know the rated max.
    if generation == 1 and "power_limit" in desired:
        limits = shelly_utils.MODEL_LIMITS.get(
            shelly_utils.device_model_key(device_info)
        ) or {}
        rated = limits.get("power")
        if rated is not None and desired["power_limit"] > rated:
            module.warn(
                f"power_limit {desired['power_limit']} exceeds the rated maximum "
                f"{rated} for this device; clamping to {rated}."
            )
            desired["power_limit"] = rated

    current = connection.send_request(
        data={"method": "Switch.GetConfig", "params": {"id": module.params["id"]}}
    )

    # Compare in "0 = disabled" space: an unset/null limit reads back as
    # missing or null, which we normalize to 0.
    def current_value(key):
        value = current.get(key)
        return 0 if value is None else value

    changes = {
        key: value for key, value in desired.items() if current_value(key) != value
    }

    diff = {
        "before": {key: current_value(key) for key in changes},
        "after": dict(changes),
    }

    result = dict(changed=bool(changes), restart_required=False, diff=diff)

    if not changes or module.check_mode:
        module.exit_json(**result)

    # Gen 2+ disables a limit with JSON null; gen 1 uses a native 0 (max_power=0).
    if generation != 1:
        payload = {key: (None if value == 0 else value) for key, value in changes.items()}
    else:
        payload = dict(changes)

    set_result = connection.send_request(
        data={
            "method": "Switch.SetConfig",
            "params": {"id": module.params["id"], "config": payload},
        }
    )
    result["restart_required"] = set_result.get("restart_required", False)
    module.exit_json(**result)


def main():
    run_module()


if __name__ == "__main__":
    main()
