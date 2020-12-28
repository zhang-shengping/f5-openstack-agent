# coding=utf-8
# Copyright (c) 2016-2018, F5 Networks, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

from f5_openstack_agent.lbaasv2.drivers.bigip import resource_helper
from oslo_log import log as logging

LOG = logging.getLogger(__name__)


class TCPProfileHelper(object):
    """A tool class for all tcp profile process"""

    def __init__(self):
        self.tcp_helper = resource_helper.BigIPResourceHelper(
            resource_helper.ResourceType.tcp_profile
        )

    @staticmethod
    def enable_tcp(service):
        listener = service.get('listener')

        # pzhang: do not check ipProtocol TCP for further requirements,
        # which may require to change tcp profile in higher level protocol
        # such as HTTPS, HTTP, FTP etc.
        if listener:
            return listener.get('transparent')
        return False

    def add_profile(self, service, vip, bigip, **kwargs):
        side = kwargs.get("side")
        tcp_options = kwargs.get("tcp_options")

        if tcp_options:
            first_option = tcp_options
            tcp_options = "{%s first}" % first_option

        partition = vip['partition']
        profile_name = self.get_profile_name(service, side)
        profile = "/" + partition + "/" + profile_name

        profile_exists = self.tcp_helper.exists(
            bigip,
            name=profile_name,
            partition=partition
        )

        if not profile_exists:
            payload = dict(
                name=profile_name,
                partition=partition,
                tcpOptions=tcp_options
            )
            LOG.info(
                "Add customized TCP profile: {} for "
                "BIGIP: {} ".format(
                    profile, bigip.hostname
                )
            )
            self.tcp_helper.create(bigip, payload)

        if side == "client":
            # pzhang: coustomerized clientside, serverside is /common/tcp
            client_profile_body = {
                "name": profile_name,
                "parition": partition,
                "context": "clientside"
            }
            server_profile_body = {
                "name": "tcp",
                "parition": "Common",
                "context": "serverside"
            }
        elif side == "server":
            # pzhang: coustomerized serverside, clientside is /common/tcp
            server_profile_body = {
                "name": profile_name,
                "parition": partition,
                "context": "serverside"
            }
            client_profile_body = {
                "name": "tcp",
                "parition": "Common",
                "context": "clientside"
            }
        else:
            # pzhang: coustomerized both serverside and clientside
            server_profile_body = {
                "name": profile_name,
                "parition": partition,
                "context": "serverside"
            }
            client_profile_body = {
                "name": profile_name,
                "parition": partition,
                "context": "clientside"
            }

        # pzhang tcp profile can not in fastL4 mode
        delete_fastL4s = vip['profiles'].count("/Common/fastL4")
        for _ in range(delete_fastL4s):
            vip['profiles'].remove("/Common/fastL4")

        # pzhang be careful, if we connect multiple
        # bigips
        if server_profile_body not in vip['profiles']:
            vip['profiles'].append(server_profile_body)
        if client_profile_body not in vip['profiles']:
            vip['profiles'].append(client_profile_body)

    def remove_profile(self, service, vip, bigip, **kwargs):
        # this function should be called after its
        # corresponding listener deleted

        side = kwargs.get("side")
        partition = vip['partition']

        profile_name = TCPProfileHelper.get_profile_name(
            service, side)
        profile = "/" + partition + "/" + profile_name

        LOG.info(
            "Remove customized TCP profile: {} from "
            "BIGIP: {}".format(
                profile, bigip.hostname
            )
        )

        self.tcp_helper.delete(
            bigip,
            name=profile_name,
            partition=partition
        )

    @staticmethod
    def get_profile_name(service, side):
        prefix = "tcp_profile_"
        if side:
            prefix = side + "_" + prefix
        listener_id = service.get('listener').get('id')
        profile_name = prefix + listener_id
        return profile_name
