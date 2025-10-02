#!/usr/bin/python

from dataclasses import dataclass, asdict
from typing import Optional

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.connection import Connection

import ansible_collections.enclave.shelly.plugins.module_utils.helpers as shelly_utils

@dataclass
class RangeExtenderConfig:
    enable: bool

@dataclass
class ApConfig:
    ssid: Optional[str]
    password: Optional[str]
    is_open: bool
    enable: bool
    range_extender: Optional[RangeExtenderConfig]

@dataclass
class StaConfig:
    ssid: Optional[str]
    password: Optional[str]
    is_open: bool
    enable: bool
    ipv4mode: str
    ip: Optional[str]
    netmask: Optional[str]
    gw: Optional[str]
    nameserver: Optional[str]

@dataclass
class RoamConfig:
    rssi_thr: int
    interval: int

@dataclass
class WifiConfig:
    ap: ApConfig
    sta: StaConfig
    sta1: StaConfig
    roam: RoamConfig

def result_into_wifi_config(result):
    ap_data = result["ap"]
    if "range_extender" in ap_data and ap_data["range_extender"] is not None:
        ap_data["range_extender"] = RangeExtenderConfig(**ap_data["range_extender"])
    
    ap = ApConfig(**ap_data)
    sta = StaConfig(**result["sta"])
    sta1 = StaConfig(**result["sta1"])
    roam = RoamConfig(**result["roam"])

    return WifiConfig(ap, sta, sta1, roam)

def compose_module_args():
    module_args = dict(
        configuring=dict(type="str", required=True, choices=["ap", "sta", "sta1", "roam"]),
        timeout=dict(type="int", required=False, default=5000)
    )
    ap_args = shelly_utils.dataclass_into_ansible_spec(ApConfig)
    ap_args["range_extender"] = dict(type="bool", required=False)
    module_args.update(ap_args)

    sta_args = shelly_utils.dataclass_into_ansible_spec(StaConfig)
    module_args.update(sta_args)

    roaming_args = shelly_utils.dataclass_into_ansible_spec(RoamConfig)
    module_args.update(roaming_args)

    return module_args

def run_module():
    module_args = compose_module_args()

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True,
        required_if=[
            ("configuring", "ap", ("ssid", "password", "is_open", "enable")),
            ("configuring", "sta", ("ssid", "password", "is_open", "enable", "ipv4mode")),
            ("configuring", "sta1", ("ssid", "password", "is_open", "enable", "ipv4mode")),
            ("configuring", "roam", ("rssi_thr", "interval"))
        ]
    )

    result = dict(
        changed=False,
        restart_required=False
    )

    connection = Connection(module._socket_path)
    current_config = connection.send_request(
        data={
            "method": "Wifi.GetConfig"
        }
    )

    if module.params["configuring"] == "ap":
        data = shelly_utils.sanitize_dataclass_args(ApConfig, module.params.copy())
        if "range_extender" in data:
            data["range_extender"] = RangeExtenderConfig(data["range_extender"])
        data = shelly_utils.optional_strs_to_none(data)

        input_args = ApConfig(**data)
        existing_args = ApConfig(current_config["ap"])
    elif module.params["configuring"] == "sta" or module.params["configuring"] == "sta1":
        data = shelly_utils.sanitize_dataclass_args(StaConfig, module.params.copy())
        data = shelly_utils.optional_strs_to_none(data)
        input_args = StaConfig(**data)
        existing_args = StaConfig(current_config[module.params["configuring"]])
    else:
        data = shelly_utils.sanitize_dataclass_args(RoamConfig, module.params.copy())
        data = shelly_utils.optional_strs_to_none(data)
        input_args = RoamConfig(**data)
        existing_args = RoamConfig(current_config["roam"])

    if input_args != existing_args:
        result["changed"] = True

    if module.check_mode:
        if result["changed"]:
            # Most, if not all, changes to Wifi config require a restart.
            result["restart_required"] = True
        return module.exit_json(**result)

    if result["changed"]:
        new_config = current_config.copy()
        new_config[module.params["configuring"]] = asdict(input_args)

        set_result = connection.send_request(
            data={
                "method": "Wifi.SetConfig",
                "params": {
                    "config": new_config
                }
            }
        )

        result["restart_required"] = set_result["restart_required"]

        connection_available = shelly_utils.poll_for_connection(module.params["timeout"], connection)

        if not connection_available:
            module.fail_json(msg="Shelly device did not become available after reconfiguring Wifi interface.", **result)

    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()
