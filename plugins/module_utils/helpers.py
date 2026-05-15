#!/usr/bin/python

import asyncio
import dataclasses
import typing

from typing import Any, Optional
from ansible.module_utils.connection import Connection

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
