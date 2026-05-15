#!/usr/bin/python

DOCUMENTATION = '''
---
module: mqtt
short_description: A module for controlling the MQTT settings of a Shelly gen 2+ device.
version_added: "0.0.1"
description:
  - "A module for controlling the MQTT settings of a Shelly gen 2+ device."
options:
    enable:
        description:
          - Controls whether the MQTT interface is enabled or not.
        required: true
        type: bool
    server:
        description:
          - The URL of the MQTT server to connect to.
          - Required if enable is set to true.
          - Set to an empty string ("") if you want to set this to null.
        required: false
        type: str
    client_id:
        description:
          - The client ID used to identify the device by the MQTT broker.
          - Required if enable is set to true.
          - Set to an empty string ("") if you want to set this to null. If set to null, the Shelly uses its own device ID for this value.
        required: false
        type: str
    user:
        description:
          - Username for authenticating with the MQTT broker.
          - Required if enable is set to true.
          - Set to an empty string ("") if you want to set this to null.
        required: false
        type: str
    pass:
        description:
          - Password for authenticating with the MQTT broker.
          - Set to an empty string ("") if you want to set this to null.
        required: false
        type: str
    ssl_ca:
        description:
          - Determines the type of TCP socket the Shelly uses for connecting to the MQTT broker.
          - Required if enable is set to true.
          - Options are:
          - "none" - Plain TCP connection.
          - "*" - TLS with disabled certificate validation.
          - "user_ca.pem" - TLS connection verified by the user-provided CA
          - "ca.pem" - TLS connection verified by the built-in CA bundle
        required: false
        type: str
        choices: ["none", "*", "user_ca.pem", "ca.pem"]
    topic_prefix:
        description:
          - Prefix of the topics on which device publish/subscribe. Limited to 300 characters. Could not start with $ and #, +, %, ? are not allowed.
          - Required if enable is set to true.
          - Set to an empty string ("") if you want to set this to null. If set to null, the Shelly uses its own device ID for this value. 
        required: false
        type: str
    rpc_ntf:
        description:
          - Enabled RPC notifications to be publised to the MQTT network.
        required: false
        type: bool
        default: true
    rpc_ntf:
        description:
          - Enabled RPC notifications to be publised to the MQTT network.
        required: false
        type: bool
        default: true
    rpc_ntf:
        description:
          - Enabled RPC notifications to be publised to the MQTT network.
        required: false
        type: bool
        default: true
    status_ntf:
        description:
          - Enables publishing the complete component status on the MQTT network.
        required: false
        type: bool
        default: false
    use_client_cert:
        description:
          - Enable or diable usage of client certifactes to use MQTT with encription.
        required: false
        type: bool
        default: false
    enable_control:
        description:
          - Allows the Shelly device to be controlled via MQTT messages.
        required: false
        type: bool
        default: true
author:
    - RustedSkull (@skull132)
'''

EXAMPLES = '''
# Disable MQTT on the device.
- name: Disable MQTT
  enclave.shelly.mqtt:
    enable: false

# Configure an MQTT server connection.
- name: Enable MQTT
  enclave.shelly.mqtt:
    enable: true
    server: mqtt_server.lan:8883
    client_id: "" # Use the shelly's own device_id
    user: "" # no username required
    pass: "" # no password required
    ssl_ca: "*" # Accept any serverside SSL certificate.
    topic_prefix: "home/v1/room/device_1"
'''

RETURN = '''
restart_required:
  description: Set to true if Shelly device should be restarted for the changes to take full effect.
  type: bool
  returned: always
'''

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.connection import Connection

import ansible_collections.enclave.shelly.plugins.module_utils.helpers as shelly_utils
import re


GEN1_UNSUPPORTED_KEYS = {
    "ssl_ca",
    "topic_prefix",
    "rpc_ntf",
    "status_ntf",
    "use_client_cert",
    "enable_control",
}


def is_default_client_id(client_id: str) -> bool:
    return re.match(r"^shelly[a-z0-9-]+-[0-9a-f]+$", client_id) is not None


def derive_gen1_client_id(params):
    if params["client_id"] is not None:
        return params["client_id"]

    topic_prefix = params.get("topic_prefix")
    if topic_prefix is None:
        return None

    topic_prefix = topic_prefix.rstrip("/")
    if topic_prefix.startswith("shellies/"):
        return topic_prefix.removeprefix("shellies/")

    return topic_prefix


def validate_required_settings(module, params, is_gen1):
    if params["enable"] is not True:
        return

    required_keys = ["server"]
    if not is_gen1:
        required_keys.append("topic_prefix")

    missing_keys = [key for key in required_keys if params.get(key) is None]
    if missing_keys:
        module.fail_json(
            msg=(
                "Missing required MQTT settings for this Shelly device generation: "
                + ", ".join(missing_keys)
            )
        )


def run_module():
    module_args = {
        "enable": dict(type="bool", required=True),
        "server": dict(type="str", required=False),
        "client_id": dict(type="str", required=False),
        "user": dict(type="str", required=False),
        "pass": dict(type="str", required=False, no_log=True),
        "ssl_ca": dict(type="str", required=False, choices=["none", "*", "user_ca.pem", "ca.pem"]),
        "topic_prefix": dict(type="str", required=False),
        "rpc_ntf": dict(type="bool", required=False, default=True),
        "status_ntf": dict(type="bool", required=False, default=False),
        "use_client_cert": dict(type="bool", required=False, default=False),
        "enable_control": dict(type="bool", required=False, default=True)
    }

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True,
    )

    result = dict(
        changed=False,
        restart_required=False
    )

    connection = Connection(module._socket_path)
    device_generation = shelly_utils.get_device_generation(connection)
    is_gen1 = device_generation == 1

    params = module.params.copy()
    default_client_id_requested = params["client_id"] == ""

    if params["enable"] is True:
        params = shelly_utils.optional_strs_to_none(
            params,
            ["server", "client_id", "user", "pass", "topic_prefix"],
        )

        if is_gen1:
            params["client_id"] = derive_gen1_client_id(params)

    if params["ssl_ca"] == "none":
        params["ssl_ca"] = None

    validate_required_settings(module, params, is_gen1)

    current_config = connection.send_request(
        data={
            "method": "MQTT.GetConfig"
        }
    )

    current_status = connection.send_request(
        data={
            "method": "MQTT.GetStatus"
        }
    )

    new_config = current_config.copy()
    keys_to_compare = params.keys()
    if is_gen1:
        keys_to_compare = [
            key for key in params.keys()
            if key not in GEN1_UNSUPPORTED_KEYS
        ]

    for key in keys_to_compare:
        desired_value = params[key]
        if key == "pass" and key not in current_config:
            if desired_value is not None:
                # The Shelly API accepts the MQTT password in SetConfig but
                # does not return it from GetConfig. Re-send it only when the
                # broker connection is currently down, or as part of another
                # config update below.
                new_config[key] = desired_value
                if not current_status.get("connected", False):
                    result["changed"] = True
            continue

        if key not in current_config:
            new_config[key] = desired_value
            result["changed"] = True
            continue

        current_value = current_config[key]

        if key == "client_id" and default_client_id_requested and is_default_client_id(current_value):
            continue

        if desired_value != current_value:
            new_config[key] = desired_value
            result["changed"] = True

    if module.check_mode:
        if result["changed"]:
            # Most, if not all, changes to MQTT config require a restart.
            result["restart_required"] = True
        return module.exit_json(**result)

    if result["changed"]:
        set_result = connection.send_request(
            data={
                "method": "MQTT.SetConfig",
                "params": {
                    "config": new_config
                }
            }
        )

        result["restart_required"] = set_result["restart_required"]

    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()
