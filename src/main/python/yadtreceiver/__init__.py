#   yadt receiver
#   Copyright (C) 2012 Immobilien Scout GmbH
#
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
    This module provides the YADT receiver, the configuration, a simple event
    class, a ProcessProtocol implementation and a module to send notifications
    to a graphite server.
"""

__author__ = 'Arne Hilmann, Michael Gruber'

import os

from twisted.application import service
from twisted.internet import reactor
from twisted.python import log

from yadtbroadcastclient import WampBroadcaster

from yadtreceiver.configuration import Configuration
from yadtreceiver.graphite import send_update_notification_to_graphite
from yadtreceiver.protocols import ProcessProtocol
from yadtreceiver.events import Event


class ReceiverException(Exception):
    """
        to be raised when an exception occurs within the receiver.
    """


class Receiver(service.Service):
    """
        The YADT receiver connects to the YADT broadcaster and receives events
        for the targets that it subscribed to.
    """

    def get_target_directory(self, target):
        """
            appends the given target name to the targets_directory.

            @raise Exception: if the target directory does not exist.
        """

        hostname = self.configuration.hostname
        targets_directory = self.configuration.targets_directory

        target_directory = os.path.join(targets_directory, target)

        if not os.path.exists(target_directory):
            raise ReceiverException('(%s) target[%s] request failed: target '
                                    'directory "%s" does not exist.'
                                    % (hostname, target, target_directory))

        return target_directory

    def handle_request(self, target, command, arguments):
        """
            handles an request for the given target by executing the given
            command (using the python_command and script_to_execute from
            the configuration).
        """

        self.publish_start(target, command, arguments)

        python_command = self.configuration.python_command
        script_to_execute = self.configuration.script_to_execute
        command_and_arguments = [python_command, script_to_execute] + arguments
        target_dir = self.get_target_directory(target)
        readable_command_and_arguments = ' '.join(command_and_arguments)

        self.notify_graphite(target, arguments)

        process_protocol = ProcessProtocol(self.configuration.hostname,
                                           self.broadcaster,
                                           target,
                                           readable_command_and_arguments)

        reactor.spawnProcess(process_protocol,
                             python_command,
                             command_and_arguments,
                             env={},
                             path=target_dir)

    def log_broadcaster_notification(self, message):
        log.msg('(broadcaster) %s' % message)

    def log_command_notification(self, target, event):
        command = event['cmd']
        state = event['state']

        if 'message' in event:
            message = event['message']
            self.log_broadcaster_notification(
                'target[%s] command "%s" %s: %s'
                % (target, command, state, message)
            )
        else:
            self.log_broadcaster_notification(
                'target[%s] command "%s" %s.' % (target, command, state)
            )

    def notify_graphite(self, target, arguments):
        """
            notifies the configured graphite server about events (currently
            only update events).
        """

        if arguments[0] == 'update':
            port = self.configuration.graphite_port
            host = self.configuration.graphite_host

            send_update_notification_to_graphite(target, host, port)

    def publish_failed(self, target, command, message):
        """

        """
        log.err(_stuff=Exception(message), _why=message)
        self.broadcaster.publish_cmd_for_target(target,
                                                command,
                                                Event.FAILED,
                                                message)

    def publish_start(self, target, command, arguments):
        """
            publishes the start of the
        """

        hostname = self.configuration.hostname
        message = '(%s) target[%s] request: command="%s", arguments=%s' \
                  % (hostname, target, command, arguments)
        log.msg(message)
        self.broadcaster.publish_cmd_for_target(target,
                                                command,
                                                Event.STARTED,
                                                message)

    def onConnect(self):
        """
            Subscribes to the targets in the configuration..
        """

        sorted_targets = sorted(self.configuration.targets)

        for target in sorted_targets:
            log.msg('subscribing to target "%s".' % target)
            self.broadcaster.client.subscribe(target, self.onEvent)

    def onEvent(self, target, event):
        event_id = event.get('id')
        if event_id == 'request':
            command = event['cmd']
            arguments = event['args']

            try:
                self.handle_request(target, command, arguments)
            except BaseException as exception:
                self.publish_failed(target, command, exception.message)

        elif event_id == 'full-update':
            self.log_broadcaster_notification(
                'target[%s] update of status information.' % target
            )

        elif event_id == 'cmd':
            self.log_command_notification(target, event)

        elif event_id == 'service-change':
            for payload in event['payload']:
                uri = payload['uri']
                state = payload['state']
                self.log_broadcaster_notification(
                    'target[%s] %s is %s.' % (target, uri, state)
                )

        else:
            self.log_broadcaster_notification(
                'target[%s] unknown event "%s".' % (target, event_id)
            )

    def set_configuration(self, configuration):
        """
            assigns a configuration to this receiver instance.
        """

        self.configuration = configuration

    def startService(self):
        """
            Establishes a connection to the broadcaster as found in the
            configuration.
        """

        host = self.configuration.broadcaster_host
        port = self.configuration.broadcaster_port

        log.msg('Connecting to broadcaster on %s:%s' % (host, port))

        self.broadcaster = WampBroadcaster(host, port, 'yadtreceiver')
        self.broadcaster.addOnSessionOpenHandler(self.onConnect)
        self.broadcaster.connect()
