#   yadtreceiver
#   Copyright (C) 2013 Immobilien Scout GmbH
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
    Provides the Receiver class which implements a twisted service
    application. The receiver allows to start processes triggered by
    broadcast events. It is configured using a dictionary. You can load
    configuration files using the load method from the configuration
    module.
"""

import os
import traceback
import functools
from uuid import uuid4 as random_uuid
from collections import defaultdict
from datetime import datetime
from time import time

from twisted.application import service
from twisted.internet import inotify, reactor
from twisted.python import filepath, log
from twisted.python.logfile import LogFile

from yadtbroadcastclient import WampBroadcaster
from .scheduling import seconds_to_midnight

import events
from voting import create_voting_fsm

__version__ = '${version}'

METRICS = defaultdict(lambda: 0)

# delayed import so that METRICS is importable from ProcessProtocol
from protocols import ProcessProtocol  # noqa


def _write_metrics(metrics, metrics_file):
    for metric_name in metrics:
        metrics_file.write("{0}={1}\n".format(metric_name, metrics[metric_name]))


def _reset_metrics(metrics):
    for metric_name in metrics.keys():
        if metrics[metric_name] == 0:
            del metrics[metric_name]
        else:
            metrics[metric_name] = 0


class ReceiverException(Exception):

    """
        To be raised when an exception occurs within the receiver.
    """


class Receiver(service.Service):

    """
        The receiver connects to the broadcaster and receives events
        for the targets that it subscribed to.
    """

    def subscribeTarget(self, targetname):
        self.configuration.reload_targets()
        if targetname in self.configuration['allowed_targets']:
            log.msg('subscribing to target "%s".' % targetname)
            self.broadcaster.client.subscribe(self.onEvent, unicode(targetname))
        else:
            log.msg(
                "Can't subscribe to target %s. Target not in allowed targets." %
                targetname)

    def unsubscribeTarget(self, targetname):
        log.msg('unsubscribing from target "%s".' % targetname)
        self.broadcaster.client.unsubscribe(targetname)

    def get_target_directory(self, target):
        """
            Appends the given target name to the targets_directory.

            @raise ReceiverException: if the target directory does not exist.
        """
        hostname = self.configuration['hostname']
        targets_directory = self.configuration['targets_directory']

        target_directory = os.path.join(targets_directory, target)

        if not os.path.exists(target_directory):
            raise ReceiverException('(%s) target[%s] request failed: target directory "%s" does not exist.'
                                    % (hostname, target, target_directory))

        return target_directory

    def handle_request(self, event):
        tracking_id = _determine_tracking_id(event.arguments)
        vote = str(random_uuid())

        def broadcast_vote(_):
            log.msg('Voting %r for request with tracking-id %r' %
                    (vote, tracking_id))
            self.broadcaster._sendEvent('vote',
                                        data=vote,
                                        tracking_id=tracking_id,
                                        target=event.target)

        def cleanup_fsm(_):
            del self.states[tracking_id]
            log.msg('Cleaned up fsm for %s, %d left in memory' % (event.target, len(self.states)))

        def fold(_):
            METRICS['voting_folds'] += 1

        self.states[tracking_id] = create_voting_fsm(tracking_id,
                                                     vote,
                                                     broadcast_vote,
                                                     functools.partial(
                                                         self.perform_request, event),
                                                     fold,
                                                     cleanup_fsm)

        reactor.callLater(10, self.states[tracking_id].showdown)

    def perform_request(self, event, _):
        """
            Handles a request for the given target by executing the given
            command (using the python_command and script_to_execute from
            the configuration).
        """
        log.msg('I have won the vote for %r, starting it now..' %
                (event.target))
        METRICS['voting_wins'] += 1
        try:
            hostname = str(self.configuration['hostname'])
            python_command = str(self.configuration['python_command'])
            script_to_execute = str(self.configuration['script_to_execute'])
            command_and_arguments_list = [
                python_command, script_to_execute] + event.arguments
            command_with_arguments = ' '.join(command_and_arguments_list)

            event.tracking_id = _determine_tracking_id(command_and_arguments_list)
            self.publish_start(event)

            if event.tracking_id in self.states:
                self.states[event.tracking_id].spawned()
            else:
                log.err('Tracking ID %r not registered with my FSM, but handling it anyway.' % event.tracking_id)

            process_protocol = ProcessProtocol(
                hostname, self.broadcaster, event.target, command_with_arguments, tracking_id=event.tracking_id)

            target_dir = self.get_target_directory(event.target)
            #  we pulled the arguments out of the event, so they are unicode, not string yet
            command_and_arguments_list = map(lambda possible_unicode: str(possible_unicode), command_and_arguments_list)

            reactor.spawnProcess(process_protocol, python_command,
                                 command_and_arguments_list, env={}, path=target_dir)
        except Exception as e:
            self.publish_failed(event, "%s : %s" % (type(e), e.message))

    def publish_failed(self, event, message):
        """
            Publishes a event to signal that the command on the target failed.
        """
        log.err(_stuff=Exception(message), _why=message)
        METRICS['commands_failed.%s' % (event.target)] += 1
        self.broadcaster.publish_cmd_for_target(
            event.target,
            event.command,
            events.FAILED,
            message,
            tracking_id=event.tracking_id)

    def publish_start(self, event):
        """
            Publishes a event to signal that the command on the target started.
        """
        hostname = self.configuration['hostname']
        message = '(%s) target[%s] request: command="%s", arguments=%s' % (
            hostname, event.target, event.command, event.arguments)
        log.msg(message)
        METRICS['commands_started.%s' % (event.target)] += 1
        self.broadcaster.publish_cmd_for_target(
            event.target,
            event.command,
            events.STARTED,
            message,
            tracking_id=event.tracking_id)

    def onConnect(self):
        """
            Subscribes to the targets from the configuration. The receiver
            is useless when no targets are configured, therefore it will exit
            with error code 1 when no targets are configured.
        """
        self.states = {}

        self.broadcaster.client.connectionLost = self.onConnectionLost

        host = self.configuration['broadcaster_host']
        port = self.configuration['broadcaster_port']

        log.msg('Successfully connected to broadcaster on %s:%s' %
                (host, port))

        self.configuration.reload_targets()
        targets = sorted(self.configuration['allowed_targets'])

        if not targets:
            log.err('No targets configured or no targets in allowed targets.')
            exit(1)

        for targetname in targets:
            log.msg('subscribing to target "%s".' % targetname)
            self.broadcaster.client.subscribe(self.onEvent, unicode(targetname))

    def _should_refresh_connection(self):
        if not hasattr(self, 'broadcaster') or not self.broadcaster.client:
            log.msg('Not connected, cannot refresh connection')
            return False  # no connection, cannot refresh

        current_hour = datetime.now().hour
        if not current_hour == 2:  # only refresh at 2:xx a.m.
            log.msg("It's %d:xx, not 2:xx a.m., no connection-refresh now." % current_hour)
            return False

        return True

    def _refresh_connection(self, delay=60 * 60, first_call=False):
        """
            When connected, closes connection to force a clean reconnect,
            except on first_call
        """
        reactor.callLater(delay, self._refresh_connection)
        log.msg('Might want to refresh connection now.')
        if not first_call and self._should_refresh_connection():
            log.msg(
                'Closing connection to broadcaster. This should force a connection-refresh.')
            self.broadcaster.client.sendClose()

    def onConnectionLost(self, reason):
        """
            Allows for clean reconnect behaviour, because it 'none'ifies
            the client explicitly
        """
        log.err('connection lost: %s' % reason)
        self.broadcaster.client = None

    def onEvent(self, *args):
        """
            Will be called when receiving an event from the broadcaster.
            See onConnect which subscribes to the targets.
        """

        try:
            # Wamp v1: onEvent is callbacked with topic and event
            target, event_data = args
        except ValueError:
            # Wamp v2: onEvent is callbacked with event
            event_data, = args
            target = None

        event = events.Event(target, event_data)

        if event.is_a_vote:
            voting_fsm = self.states.get(event.tracking_id)
            if not voting_fsm:
                log.msg(
                    'Ignoring vote %r because I have already lost' % event.vote)
                return
            own_vote = voting_fsm.vote
            is_a_fold = (own_vote < event.vote)

            if is_a_fold:
                log.msg(
                    'Folding due to vote %r being higher than own vote %r' %
                    (event.vote, own_vote))
                voting_fsm.fold()
            else:
                log.msg(
                    'Calling due to vote %r being lower than own vote %r' %
                    (event.vote, own_vote))
                voting_fsm.call()

        elif event.is_a_request:
            try:
                self.handle_request(event)
            except Exception as e:
                log.err(e.message)

                for line in traceback.format_exc().splitlines():
                    log.err(line)

                self.publish_failed(event, e.message)

        else:
            log.msg(str(event))

    def set_configuration(self, configuration):
        """
            Assigns a configuration to this receiver instance.
        """
        self.configuration = configuration

    def initialize_twisted_logging(self):
        twenty_megabytes = 20000000
        log_file = LogFile.fromFullPath(self.configuration['log_filename'],
                                        maxRotatedFiles=10,
                                        rotateLength=twenty_megabytes)
        log.startLogging(log_file)

    def startService(self):
        """
            Initializes logging and establishes connection to broadcaster.
        """
        self.initialize_twisted_logging()
        log.msg('yadtreceiver version %s' % __version__)
        self._connect_broadcaster()
        self._refresh_connection(first_call=True)
        self.schedule_write_metrics(first_call=True)
        self.reset_metrics_at_midnight(first_call=True)

    def stopService(self):
        """
            Writes 'shutting down service' to the log.
        """
        log.msg('shutting down service')

    def _connect_broadcaster(self):
        """
            Establishes a connection to the broadcaster as found in the
            configuration.
        """
        host = self.configuration['broadcaster_host']
        port = self.configuration['broadcaster_port']

        log.msg('Connecting to broadcaster on %s:%s' % (host, port))

        self.broadcaster = WampBroadcaster(host, port, 'yadtreceiver')
        self.broadcaster.addOnSessionOpenHandler(self.onConnect)

    def write_metrics_to_file(self):

        metrics_directory = self.configuration['metrics_directory']
        if not metrics_directory:
            return

        if not os.path.isdir(metrics_directory):
            try:
                os.makedirs(metrics_directory)
            except Exception as e:
                log.err("Cannot create metrics directory : {0}".format(e))
                return

        metrics_file_name = self.configuration['metrics_file']
        with open(metrics_file_name, 'w') as metrics_file:
            _write_metrics(METRICS, metrics_file)

    def schedule_write_metrics(self, delay=30, first_call=False):
        reactor.callLater(delay, self.schedule_write_metrics)
        if not first_call:
            start = time()
            self.write_metrics_to_file()
            write_duration = time() - start
            log.msg("Wrote metrics to file in {0} seconds".format(write_duration))
            METRICS["last_write_duration"] = write_duration

    def reset_metrics_at_midnight(cls, first_call=False):
        reactor.callLater(seconds_to_midnight(), cls.reset_metrics_at_midnight)
        if not first_call:
            log.msg("Resetting metrics")
            _reset_metrics(METRICS)


def _determine_tracking_id(command_and_arguments_list):
    tracking_id = None
    for command_or_argument in command_and_arguments_list:
        if command_or_argument.startswith('--tracking-id='):
            tracking_id = command_or_argument.split('=')[1]
    return tracking_id


class FileSystemWatcher(service.Service):

    def __init__(self, path_to_watch):
        self.SUBFOLDER_CREATE = 0x40000100
        self.path = path_to_watch

    def startService(self):
        in_watch_mask = self.SUBFOLDER_CREATE
        notifier = inotify.INotify()
        notifier.startReading()
        notifier.watch(filepath.FilePath(self.path), mask=in_watch_mask,
                       callbacks=[self.onChange])

    def onChange(self, watch, path, mask):
        if mask == self.SUBFOLDER_CREATE:
            callback = self.onChangeCallbacks['create']
            target = path.basename()
            callback(target)
