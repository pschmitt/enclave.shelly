DOCUMENTATION = """
---
author: RustedSkull (@skull132)
httpapi: shelly
short_description: A network OS to interface with Shelly gen 2+ home automation devices.
description: 
  - This HttpApi plugin provides a way of talking to a Shelly gen 2+ home automation device via its JSONRPCv2 API over POST.
"""

FACTS_MODULES = ["enclave.shelly.shelly_api_facts"]
# Funny story, this does nothing.

import json
import hashlib
import secrets

from ansible.plugins.httpapi import HttpApiBase
from ansible.errors import AnsibleConnectionFailure
from ansible.module_utils.basic import to_text
from ansible.module_utils.common.parameters import remove_values

from http.client import HTTPResponse

def hash_string(string: str) -> str:
    return hashlib.sha256(string.encode("utf-8")).hexdigest()

class HttpApi(HttpApiBase):
    def __init__(self, connection):
        super().__init__(connection)

        self._request_id = 0
        self._shelly_password = None

    @property
    def request_id(self):
        self._request_id += 1
        return self._request_id

    def login(self, username, password):
        """
        This function is called in the httpapi.Connection class during initialization.
        The password parameter corresponds to the value of ansible_httpapi_password.
        We can override this function to store the password and use it later for API authentication.
        """
        self._shelly_password = password

    def client_nonce(self):
        return secrets.token_hex(16)

    def ha1(self, realm, password=None):
        if password is None:
            password = self._shelly_password

        return hash_string(f"admin:{realm}:{password}")

    def ha2(self):
        return hash_string("dummy_method:dummy_uri")

    def auth_available(self):
        if self._shelly_password is not None:
            return True
        else:
            return False

    def process_authenticate_header(self, header):
        header = header.split(", ")
        header_dict = {}
        for header_subset in header:
            header_subset = header_subset.split("=")
            key = header_subset[0]
            value = header_subset[1]
            value = value[1:-1]
            header_dict[key] = value

        return header_dict

    def send_request(self, data, **message_kwargs):
        request_data = {
            "id": self.request_id,
            "method": data["method"],
            "params": None
        }

        if "params" in data.keys():
            request_data["params"] = data["params"]

        if "auth" in data.keys():
            request_data["auth"] = data["auth"]

        try:
            response: HTTPResponse
            response, response_data = self.connection.send(
                "/rpc", json.dumps(request_data, ensure_ascii=False), method="POST"
            )

            if response.getcode() == 401:
                if "auth" in data:
                    raise ConnectionError("Shelly API requires auth, currently provided credentials did not work. This is a library or device bug.")

                if not self.auth_available():
                    raise ConnectionError("Shelly API requires auth, but no ansible_httpapi_password was provided for host.")
                
                authenticate_request = response.getheader("WWW-Authenticate")
                if authenticate_request is None:
                    raise ConnectionError("Shelly API requires auth, but did not populate WWW-Authenticate header.")
                
                headers = self.process_authenticate_header(authenticate_request)
                nonce = headers["nonce"]
                realm = headers["realm"]
                client_nonce = self.client_nonce()
                data["auth"] = {
                    "realm": realm,
                    "username": "admin",
                    "nonce": nonce,
                    "cnonce": client_nonce,
                    # nc = 1 because it's only asked over WS.
                    "response": hash_string(f"{self.ha1(realm)}:{nonce}:1:{client_nonce}:auth:{self.ha2()}"),
                    "algorithm": "SHA-256"
                }

                return self.send_request(data)

            value = to_text(response_data.getvalue())
            try:
                json_data = json.loads(value) if value else {}
                # JSONDecodeError only available on Python 3.5+
            except ValueError:
                raise ConnectionError("Invalid JSON response: %s" % value)
            
            if "error" in json_data:
                raise ConnectionError(
                    "REST API returned %s when sending %s"
                        % (
                            json_data["error"],
                            remove_values(
                                data,
                                [
                                    self.connection.get_option("password"),
                                ],
                            ),
                        )
                    )
            
            if "result" in json_data:
                json_data = json_data["result"]
            
            return json_data
        except AnsibleConnectionFailure as e:
            e_text = to_text(e.message)
            if to_text("Could not connect to") in e_text:
                raise
            else:
                raise ConnectionError(f"Shelly API connection errored: {e_text}.")
        except ConnectionError as e:
            raise e
        except Exception as e:
            raise e

    def handle_httperror(self, exc):
        return exc
