#!/usr/bin/env python
#
# mmgen = Multi-Mode GENerator, command-line Bitcoin cold storage solution
# Copyright (C)2013-2015 Philemon <mmgen-py@yandex.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
mmgen-tool:  Perform various Bitcoin-related operations.
             Part of the MMGen suite
"""

import sys
import mmgen.config as g
import mmgen.tool as tool
from mmgen.Opts import *

help_data = {
	'prog_name': g.prog_name,
	'desc':    "Perform various BTC-related operations",
	'usage':   "[opts] <command> <command args>",
	'options': """
-d, --outdir=       d Specify an alternate directory 'd' for output
-h, --help            Print this help message
-q, --quiet           Produce quieter output
-r, --usr-randchars=n Get 'n' characters of additional randomness from
                      user (min={g.min_urandchars}, max={g.max_urandchars})
-v, --verbose         Produce more verbose output
""".format(g=g),
	'notes': """

COMMANDS:{}
Type '{} <command> --help for usage information on a particular
command
""".format(tool.command_help,g.prog_name)
}

opts,cmd_args = parse_opts(sys.argv,help_data)

if len(cmd_args) < 1:
	usage(help_data)
	sys.exit(1)

command = cmd_args.pop(0)

if command not in tool.commands.keys():
	msg("'%s': No such command" % command)
	sys.exit(1)

if cmd_args and cmd_args[0] == '--help':
	tool.tool_usage(g.prog_name, command)
	sys.exit(0)

args = tool.process_args(g.prog_name, command, cmd_args)

tool.opts = opts

#print command + "(" + ", ".join(args) + ")"
eval("tool." + command + "(" + ", ".join(args) + ")")
