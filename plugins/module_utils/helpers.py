#!/usr/bin/python

import asyncio
import dataclasses
import re
import typing

from typing import Any, Optional, Union
from ansible.module_utils.connection import Connection

# Per-model overpower/overcurrent/overvoltage protection maxima, used to
# resolve the magic value "max" to a concrete number.
#
# Gen 1 devices are keyed by their "type" string and only support a Watts
# (power) limit. Gen 2+ devices are keyed by their "app" id and additionally
# support current (A) and voltage (V) limits.
#
# Sources: shelly-api-docs.shelly.cloud and kb.shelly.cloud "Device Smart
# Control" pages. 16A single-phase devices share 4480W/16A/280V; the 8A 1PM
# Mini family shares 2240W/8A/280V.
MODEL_LIMITS = {
    # --- Gen 1 (keyed by device "type"; power only) ---
    "SHSW-PM": {"power": 3500},   # Shelly 1PM
    "SHPLG-S": {"power": 2500},   # Shelly Plug S
    "SHPLG-1": {"power": 3500},   # Shelly Plug
    "SHPLG2-1": {"power": 3500},  # Shelly Plug (rev 2)
    "SHSW-25": {"power": 2300},   # Shelly 2.5 (per channel)
    # --- Gen 2+ (keyed by "app" id) ---
    "Plus1PM": {"power": 4480, "current": 16, "voltage": 280},
    "Pro1PM": {"power": 4480, "current": 16, "voltage": 280},
    "Pro4PM": {"power": 4480, "current": 16, "voltage": 280},
    "S2PMG4": {"power": 2800, "current": 10, "voltage": 280},  # 2PM Gen4 (per channel, fw-enforced)
    "PlusPlugS": {"power": 2500, "current": 12, "voltage": 280},
    "Mini1PMG3": {"power": 2240, "current": 8, "voltage": 280},  # 1PM Mini Gen3
    "Mini1PMG4": {"power": 2240, "current": 8, "voltage": 280},  # 1PM Mini Gen4
}


def device_model_key(device_info: dict[str, Any]) -> Optional[str]:
    """Return the lookup key for MODEL_LIMITS for the given device.

    Gen 2+ devices report an "app" id (e.g. "Plus1PM"); gen 1 devices report
    a "type" (e.g. "SHSW-PM"). Fall back to "model" if "app" is missing.
    """
    return device_info.get("app") or device_info.get("model") or device_info.get("type")


def coerce_limit(value: Any) -> Union[int, float, str, None]:
    """Normalize a user-supplied protection limit.

    - None stays None (meaning "leave unchanged").
    - The case-insensitive string "max" is preserved as a sentinel for later
      per-model resolution.
    - Numeric strings are converted to int/float so that values coming in as
      strings do not cause spurious "changed" results or string payloads.
    - Booleans are rejected (True would otherwise sneak through as 1).
    """
    if value is None:
        return None

    if isinstance(value, bool):
        raise ValueError("protection limits must be a number or 'max', not a boolean")

    if isinstance(value, str):
        stripped = value.strip()
        if stripped.lower() == "max":
            return "max"
        if re.fullmatch(r"-?\d+", stripped):
            return int(stripped)
        try:
            return float(stripped)
        except ValueError:
            raise ValueError(f"invalid protection limit value: {value!r}")

    return value


def resolve_protection_max(
    device_info: dict[str, Any], field: str, value: Any
) -> Union[int, float]:
    """Resolve the "max" sentinel to the device's rated maximum.

    Non-"max" values pass through unchanged. Raises ValueError when the model
    is unknown or the requested field has no documented maximum for it.
    """
    if value != "max":
        return value

    key = device_model_key(device_info)
    limits = MODEL_LIMITS.get(key)
    if limits is None:
        raise ValueError(
            f"cannot resolve '{field}: max' for unknown Shelly model {key!r}; "
            f"add it to MODEL_LIMITS in the enclave.shelly collection"
        )

    if field not in limits:
        raise ValueError(
            f"Shelly model {key!r} has no documented maximum '{field}' protection limit"
        )

    return limits[field]


def optional_strs_to_none(input: dict[str, Any], keys: Optional[str]) -> dict[str, Any]:
    output = input.copy()

    if keys is None:
        for key, value in output.items():
            if type(output[key]) is not str:
                continue

            if len(output[key]) == 0:
                output[key] = None
    else:
        for key in keys:
            if len(output[key]) == 0:
                output[key] = None

    return output


def get_device_info(connection: Connection) -> dict[str, Any]:
    return connection.send_request(
        data={
            "method": "Shelly.GetDeviceInfo"
        }
    )


def get_device_generation(connection: Connection) -> int:
    device_info = get_device_info(connection)
    generation = device_info.get("gen")
    if generation is None and "type" in device_info:
        return 1

    return generation or 2


def dataclass_into_ansible_spec(dataclass: type) -> dict[str, dict]:
    accepted_trivial_types = [str, int, bool, float]
    accepted_optional_types = [Optional[str], Optional[int], Optional[bool], Optional[float]]
    spec = {}
    for field in dataclasses.fields(dataclass):
        if field.type in accepted_trivial_types:
            addition = {
                "type": field.type.__name__,
                "required": True
            }

            spec[field.name] = addition

        if field.type in accepted_optional_types:
            type = typing.get_args(field.type)[0]
            addition = {
                "type": type.__name__,
                "required": False
            }
            if field.default is not None:
                addition["default"] = field.default
            
            spec[field.name] = addition

    return spec        

def sanitize_dataclass_args(dataclass: type, arguments: dict[str, Any]) -> dict[str, Any]:
    args_dictionary = {}
    for field in dataclasses.fields(dataclass):
        if field.name in arguments:
            args_dictionary = arguments[field.name]

    return args_dictionary

def poll_for_connection(timeout: int, connection: Connection) -> bool:
    async def poll():
        waited = 0
        steps = 500

        device_available = False
        while waited < timeout:
            waited += steps
            await asyncio.sleep(steps / 1000)

            try:
                connection.send_request(
                    data={
                        "method": "Shelly.GetStatus"
                    }
                )

                device_available = True
                break
            except:
                pass

        return device_available

    return asyncio.run(poll())
