#!/usr/bin/python

DOCUMENTATION = '''
---
module: auto_update
short_description: Manage scheduled firmware auto-updates on Shelly devices that support them.
version_added: "0.29.4"
description:
  - Reads current scheduled auto-update jobs via C(Schedule.List).
  - Ensures there is at most one matching auto-update job that calls C(Shelly.Update).
  - Devices without schedule or firmware update support are silently skipped.
options:
    enable:
        description:
          - Whether firmware auto-update should be enabled.
        required: true
        type: bool
    channel:
        description:
          - Firmware update channel to use when auto-update is enabled.
        required: false
        type: str
        choices:
          - stable
          - beta
        default: stable
author:
    - pschmitt
'''

EXAMPLES = '''
- name: Enable auto-update to stable firmware
  enclave.shelly.auto_update:
    enable: true

- name: Enable auto-update to beta firmware
  enclave.shelly.auto_update:
    enable: true
    channel: beta

- name: Disable firmware auto-update
  enclave.shelly.auto_update:
    enable: false
'''

RETURN = '''
changed:
  description: Whether the auto-update schedule changed.
  returned: always
  type: bool
restart_required:
  description: Whether the device must be rebooted for the config change to apply.
  returned: always
  type: bool
skipped_unsupported:
  description: True when the device does not expose the required schedule/update methods.
  returned: always
  type: bool
'''

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.connection import Connection

AUTO_UPDATE_TIMESPEC = "0 0 0 * * 0,1,2,3,4,5,6"


def has_auto_update_support(connection):
    methods = set(connection.send_request(data={"method": "Shelly.ListMethods"}).get("methods", []))
    required = {
        "Schedule.List",
        "Schedule.Create",
        "Schedule.Delete",
        "Shelly.Update",
    }
    return required.issubset(methods)


def extract_auto_update_jobs(jobs):
    auto_jobs = []
    for job in jobs:
        if not job.get("enable", False):
            continue

        calls = job.get("calls", [])
        if len(calls) != 1:
            continue

        call = calls[0]
        if str(call.get("method", "")).lower() != "shelly.update":
            continue

        if call.get("origin") != "shelly_service":
            continue

        stage = call.get("params", {}).get("stage")
        if stage not in ("stable", "beta"):
            continue

        auto_jobs.append(
            {
                "id": job.get("id"),
                "stage": stage,
                "timespec": job.get("timespec"),
            }
        )

    return auto_jobs


def run_module():
    module = AnsibleModule(
        argument_spec={
            "enable": {"type": "bool", "required": True},
            "channel": {
                "type": "str",
                "required": False,
                "default": "stable",
                "choices": ["stable", "beta"],
            },
        },
        supports_check_mode=True,
    )

    connection = Connection(module._socket_path)
    if not has_auto_update_support(connection):
        module.exit_json(changed=False, restart_required=False, skipped_unsupported=True)

    schedules = connection.send_request(data={"method": "Schedule.List"})
    current_jobs = extract_auto_update_jobs(schedules.get("jobs", []))

    desired_enable = module.params["enable"]
    desired_channel = module.params["channel"]

    diff_before = {"jobs": current_jobs}
    diff_after = {
        "jobs": (
            [{"stage": desired_channel, "timespec": AUTO_UPDATE_TIMESPEC}]
            if desired_enable
            else []
        )
    }

    changed = False
    to_delete = []
    create_job = False

    if not desired_enable:
        to_delete = [job["id"] for job in current_jobs if job.get("id") is not None]
        changed = bool(to_delete)
    else:
        matching_jobs = [
            job for job in current_jobs
            if job.get("stage") == desired_channel and job.get("timespec") == AUTO_UPDATE_TIMESPEC
        ]
        keep_job_id = matching_jobs[0]["id"] if matching_jobs else None
        to_delete = [
            job["id"] for job in current_jobs
            if job.get("id") is not None and job.get("id") != keep_job_id
        ]
        create_job = keep_job_id is None
        changed = bool(to_delete) or create_job

    result = dict(
        changed=changed,
        restart_required=False,
        skipped_unsupported=False,
        diff={"before": diff_before, "after": diff_after},
    )

    if not changed or module.check_mode:
        module.exit_json(**result)

    for job_id in to_delete:
        connection.send_request(
            data={
                "method": "Schedule.Delete",
                "params": {"id": job_id},
            }
        )

    if create_job:
        connection.send_request(
            data={
                "method": "Schedule.Create",
                "params": {
                    "timespec": AUTO_UPDATE_TIMESPEC,
                    "calls": [
                        {
                            "method": "Shelly.Update",
                            "params": {"stage": desired_channel},
                            "origin": "shelly_service",
                        }
                    ],
                },
            }
        )

    module.exit_json(**result)


def main():
    run_module()


if __name__ == "__main__":
    main()
