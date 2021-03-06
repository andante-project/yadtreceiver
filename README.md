# yadtreceiver [![Build Status](https://secure.travis-ci.org/yadt/yadtreceiver.png?branch=master)](http://travis-ci.org/yadt/yadtreceiver)

Executes yadtshell commands triggered by a yadtbroadcaster.

## Big picture
![big picture : yadtreceiver with broadcaster and yadtshell](https://raw.github.com/yadt/yadtreceiver/master/bigpicture.png)

## Installation

Since yadtreceiver is a python application you can install it using `pip`

```bash
sudo pip install yadtreceiver
```

Unfortunately tar will not set the permissions as required:

```bash
sudo chmod 755 /etc/init.d/yadtreceiver
```
## Configuration

Put a file called receiver.cfg into the directory /etc/yadtshell/

```
[receiver]
log_filename = /var/log/yadtreceiver.log
targets = dev*
targets_directory = /etc/yadtshell/targets
script_to_execute = /usr/bin/yadtshell

[broadcaster]
host = broadcaster.domain.tld
port = 8081
```

`targets` is a whitelist with glob-like expressions, like `foo*` will match 
everything starting with `foo`, e.g. `foobar`, `foobaz`, etc. The receiver will 
watch the  targets directory for target configurations which names are covered 
by the whitelist and subscribe to them without the need to restart the receiver.

## Starting service

After installation you will find a minimal service script in `/etc/init.d`.
Maybe you want/need to modify the script to make it fit to your *nix
distribution.

```bash
sudo service yadtreceiver start
```

## Clustering
The receiver can be operated in a cluster by subscribing several receivers to the same target. They will then decide which receiver fulfills the request by issuing votes and using the following state machine:

![the voting state machine](https://raw.github.com/yadt/yadtreceiver/master/voting.png)

## License

Copyright (C) 2013-2014 Immobilien Scout GmbH

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.


This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.


You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
