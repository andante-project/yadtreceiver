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


__author__ = 'Michael Gruber'

import unittest

from mock import Mock, call, patch

from yadtreceiver import Receiver, ReceiverException
from yadtreceiver.configuration import Configuration

class YadtReceiverTests (unittest.TestCase):
    def test_should_set_configuration (self):
        configuration = 'configuration'
        receiver = Receiver()

        receiver.set_configuration(configuration)

        self.assertEquals(configuration, receiver.configuration)

    @patch('yadtreceiver.WampBroadcaster')
    def test_should_initialize_broadcaster_when_starting_service (self, mock_wamb):
        configuration = Mock(Configuration)
        configuration.broadcaster_host = 'broadcaster-host'
        configuration.broadcaster_port = 1234
        receiver = Receiver()
        receiver.set_configuration(configuration)

        receiver.startService()

        self.assertEquals(call('broadcaster-host', 1234, 'yadtreceiver'), mock_wamb.call_args)

    @patch('yadtreceiver.WampBroadcaster')
    def test_should_add_session_handler_to_broadcaster_when_starting_service (self, mock_wamb):
        receiver = Receiver()
        receiver.set_configuration(Mock(Configuration))
        mock_broadcaster_client = Mock()
        mock_wamb.return_value = mock_broadcaster_client

        receiver.startService()

        self.assertEquals(call(receiver.onConnect), mock_broadcaster_client.addOnSessionOpenHandler.call_args)

    @patch('yadtreceiver.WampBroadcaster')
    def test_should_connect_broadcaster_when_starting_service (self, mock_wamb):
        receiver = Receiver()
        receiver.set_configuration(Mock(Configuration))
        mock_broadcaster_client = Mock()
        mock_wamb.return_value = mock_broadcaster_client

        receiver.startService()

        self.assertEquals(call(), mock_broadcaster_client.connect.call_args)

    @patch('yadtreceiver.WampBroadcaster')
    def test_should_initialize_broadcaster_when_starting_service (self, mock_wamb):
        configuration = Mock(Configuration)
        configuration.broadcaster_host = 'broadcaster-host'
        configuration.broadcaster_port = 1234
        receiver = Receiver()
        receiver.set_configuration(configuration)

        receiver.startService()

        self.assertEquals(call('broadcaster-host', 1234, 'yadtreceiver'), mock_wamb.call_args)

    def test_should_subscribe_to_target_from_configuration_when_connected (self):
        configuration = Mock(Configuration)
        configuration.targets = set(['devabc123'])
        receiver = Receiver()
        mock_broadcaster_client = Mock()
        receiver.broadcaster = mock_broadcaster_client
        receiver.set_configuration(configuration)

        receiver.onConnect()

        self.assertEquals(call('devabc123', receiver.onEvent), mock_broadcaster_client.client.subscribe.call_args)

    def test_should_subscribe_to_targets_from_configuration_in_alphabetical_order_when_connected (self):
        configuration = Mock(Configuration)
        configuration.targets = set(['dev01', 'dev02', 'dev03'])
        receiver = Receiver()
        mock_broadcaster_client = Mock()
        receiver.broadcaster = mock_broadcaster_client
        receiver.set_configuration(configuration)

        receiver.onConnect()

        self.assertEquals([call('dev01', receiver.onEvent),
                           call('dev02', receiver.onEvent),
                           call('dev03', receiver.onEvent)], mock_broadcaster_client.client.subscribe.call_args_list)

    @patch('os.path.exists')
    def test_should_raise_exception_when_target_directory_does_not_exist (self, mock_exists):
        mock_exists.return_value = False
        receiver = Receiver()
        mock_configuration = Mock(Configuration)
        mock_configuration.targets_directory = '/etc/yadtshell/targets/'
        receiver.set_configuration(mock_configuration)

        self.assertRaises(ReceiverException, receiver.get_target_directory, 'spargel')

    @patch('os.path.exists')
    def test_should_append_target_name_to_targets_directory (self, mock_exists):
        mock_exists.return_value = True
        receiver = Receiver()
        mock_configuration = Mock(Configuration)
        mock_configuration.targets_directory = '/etc/yadtshell/targets/'
        receiver.set_configuration(mock_configuration)

        actual_target_directory = receiver.get_target_directory('spargel')

        self.assertEquals('/etc/yadtshell/targets/spargel', actual_target_directory)

    @patch('os.path.exists')
    def test_should_join_target_name_with_targets_directory (self, mock_exists):
        mock_exists.return_value = True
        receiver = Receiver()
        mock_configuration = Mock(Configuration)
        mock_configuration.targets_directory = '/etc/yadtshell/targets'
        receiver.set_configuration(mock_configuration)

        actual_target_directory = receiver.get_target_directory('spargel')

        self.assertEquals('/etc/yadtshell/targets/spargel', actual_target_directory)

    @patch('yadtreceiver.reactor')
    def test_should_publish_start_event (self, mock_reactor):
        mock_receiver = Mock(Receiver)
        mock_receiver.broadcaster = Mock()
        mock_configuration = Mock(Configuration)
        mock_configuration.python_command = '/usr/bin/python'
        mock_configuration.script_to_execute = '/usr/bin/yadtshell'
        mock_receiver.configuration = mock_configuration

        Receiver.handle_request(mock_receiver, 'devabc123', 'yadtshell', ['update'])

        self.assertEquals(call('devabc123', 'yadtshell', ['update']), mock_receiver.publish_start.call_args)

    @patch('yadtreceiver.reactor')
    def test_should_notify_graphite (self, mock_reactor):
        mock_receiver = Mock(Receiver)
        mock_receiver.broadcaster = Mock()
        mock_configuration = Mock(Configuration)
        mock_configuration.python_command = '/usr/bin/python'
        mock_configuration.script_to_execute = '/usr/bin/yadtshell'
        mock_receiver.configuration = mock_configuration

        Receiver.handle_request(mock_receiver, 'devabc123', 'yadtshell', ['update'])

        self.assertEquals(call('devabc123', ['update']), mock_receiver.notify_graphite.call_args)

    @patch('yadtreceiver.reactor')
    @patch('yadtreceiver.ProcessProtocol')
    def test_should_spawn_new_process_on_reactor (self, mock_protocol, mock_reactor):
        mock_protocol.return_value = 'mock-protocol'
        mock_receiver = Mock(Receiver)
        mock_broadcaster = Mock()
        mock_receiver.broadcaster = mock_broadcaster
        mock_receiver.get_target_directory.return_value = '/etc/yadtshell/targets/devabc123'
        mock_configuration = Mock(Configuration)
        mock_configuration.hostname = 'hostname'
        mock_configuration.python_command = '/usr/bin/python'
        mock_configuration.script_to_execute = '/usr/bin/yadtshell'
        mock_receiver.configuration = mock_configuration

        Receiver.handle_request(mock_receiver, 'devabc123', 'yadtshell', ['update'])

        self.assertEquals(call('hostname', mock_broadcaster, 'devabc123', '/usr/bin/python /usr/bin/yadtshell update'), mock_protocol.call_args)
        self.assertEquals(call('mock-protocol', '/usr/bin/python', ['/usr/bin/python', '/usr/bin/yadtshell', 'update'], path='/etc/yadtshell/targets/devabc123', env={}), mock_reactor.spawnProcess.call_args)

    @patch('yadtreceiver.log')
    def test_should_log_broadcaster_message (self, mock_log):
        mock_receiver = Mock(Receiver)

        Receiver.log_broadcaster_notification(mock_receiver, 'Everything is fine.')

        self.assertEquals(call('(broadcaster) Everything is fine.'), mock_log.msg.call_args)

    def test_should_log_command_notification (self):
        mock_receiver = Mock(Receiver)
        mock_event = {'cmd': 'command', 'state': 'state'}

        Receiver.log_command_notification(mock_receiver, 'devabc123', mock_event)

        self.assertEquals(call('target[devabc123] command "command" state.'), mock_receiver.log_broadcaster_notification.call_args)

    def test_should_log_command_notification_with_message (self):
        mock_receiver = Mock(Receiver)
        mock_event = {'cmd': 'command', 'message': 'message', 'state': 'state'}

        Receiver.log_command_notification(mock_receiver, 'devabc123', mock_event)

        self.assertEquals(call('target[devabc123] command "command" state: message'), mock_receiver.log_broadcaster_notification.call_args)

    @patch('yadtreceiver.send_update_notification_to_graphite')
    def test_should_not_notify_graphite_on_update_if_command_is_status (self, mock_send):
        mock_receiver = Mock(Receiver)

        Receiver.notify_graphite(mock_receiver, 'devabc123', ['status'])

        self.assertEquals(None, mock_send.call_args)

    @patch('yadtreceiver.send_update_notification_to_graphite')
    def test_should_notify_graphite_on_update (self, mock_send):
        mock_receiver = Mock(Receiver)
        mock_configuration = Mock(Configuration)
        mock_configuration.graphite_host = 'host'
        mock_configuration.graphite_port = 'port'
        mock_receiver.configuration = mock_configuration

        Receiver.notify_graphite(mock_receiver, 'devabc123', ['update'])

        self.assertEquals(call('devabc123', 'host', 'port'), mock_send.call_args)


    @patch('yadtreceiver.log')
    def test_should_publish_event_about_failed_command_on_target (self, mock_log):
        mock_receiver = Mock(Receiver)
        mock_broadcaster = Mock()
        mock_receiver.broadcaster = mock_broadcaster

        Receiver.publish_failed(mock_receiver, 'devabc123', 'yadtshell', 'It failed!')

        self.assertEquals(call('devabc123', 'yadtshell', 'failed', 'It failed!'), mock_broadcaster.publish_cmd_for_target.call_args)

    @patch('yadtreceiver.log')
    def test_should_publish_event_about_started_command_on_target (self, mock_log):
        mock_receiver = Mock(Receiver)
        mock_configuration = Mock(Configuration)
        mock_configuration.hostname = 'hostname'
        mock_receiver.configuration = mock_configuration
        mock_broadcaster = Mock()
        mock_receiver.broadcaster = mock_broadcaster


        Receiver.publish_start(mock_receiver, 'devabc123', 'yadtshell', ['update'])

        self.assertEquals(call('devabc123', 'yadtshell', 'started', '(hostname) target[devabc123] request: command="yadtshell", arguments=[\'update\']'), mock_broadcaster.publish_cmd_for_target.call_args)

    def test_should_handle_request (self):
        mock_receiver = Mock(Receiver)
        mock_event = {'id': 'request', 'cmd': 'command', 'args': 'args'}

        Receiver.onEvent(mock_receiver, 'target', mock_event)

        self.assertEquals(call('target', 'command', 'args'), mock_receiver.handle_request.call_args)

    def test_should_publish_event_about_failed_request_when_handle_request_fails (self):
        mock_receiver = Mock(Receiver)
        mock_receiver.handle_request.side_effect = ReceiverException('It failed!')
        mock_event = {'id': 'request', 'cmd': 'command', 'args': 'args'}

        Receiver.onEvent(mock_receiver, 'target', mock_event)

        self.assertEquals(call('target', 'command', 'It failed!'), mock_receiver.publish_failed.call_args)

    def test_should_log_broadcaster_notification_of_full_update (self):
        mock_receiver = Mock(Receiver)
        mock_event = {'id': 'full-update'}

        Receiver.onEvent(mock_receiver, 'dev123', mock_event)

        self.assertEquals(call('target[dev123] update of status information.'), mock_receiver.log_broadcaster_notification.call_args)

    def test_should_log_broadcaster_notification_of_command_execution (self):
        mock_receiver = Mock(Receiver)
        mock_event = {'id': 'cmd'}

        Receiver.onEvent(mock_receiver, 'dev123', mock_event)

        self.assertEquals(call('dev123', {'id': 'cmd'}), mock_receiver.log_command_notification.call_args)

    def test_should_log_command_notification_of_ (self):
        mock_receiver = Mock(Receiver)
        mock_event = {'id': 'service-change',
                      'payload': [{'uri': 'service://host01/abc', 'state': 'up'}]}

        Receiver.onEvent(mock_receiver, 'dev123', mock_event)

        self.assertEquals(call('target[dev123] service://host01/abc is up.'), mock_receiver.log_broadcaster_notification.call_args)

    def test_should_log_unkown_event (self):
        mock_receiver = Mock(Receiver)
        mock_event = {'id': 'tralala'}

        Receiver.onEvent(mock_receiver, 'dev123', mock_event)

        self.assertEquals(call('target[dev123] unknown event "tralala".'), mock_receiver.log_broadcaster_notification.call_args)