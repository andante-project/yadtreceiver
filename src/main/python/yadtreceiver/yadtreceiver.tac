#!/usr/bin/env python
#
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
"""

__author__ = 'Arne Hilmann, Michael Gruber'


import os
import re
import socket
import subprocess
import sys
import time

from twisted.application import service
from twisted.internet import reactor, protocol

from yadtreceiver import Receiver
from yadtreceiver.configuration import Configuration


VERSION = '${version}'


configuration = Configuration.load('/etc/yadtshell/receiver.cfg')
application = service.Application('yadt-receiver version %s' % VERSION)

receiver = Receiver()
receiver.set_configuration(configuration)
receiver.setServiceParent(application)