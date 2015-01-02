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
main.py - Script launcher for the MMGen suite
"""

def launch_addrgen():    import mmgen.main_addrgen
def launch_addrimport(): import mmgen.main_addrimport
def launch_keygen():     import mmgen.main_addrgen
def launch_passchg():    import mmgen.main_passchg
def launch_pywallet():   import mmgen.main_pywallet
def launch_tool():       import mmgen.main_tool
def launch_txcreate():   import mmgen.main_txcreate
def launch_txsend():     import mmgen.main_txsend
def launch_txsign():     import mmgen.main_txsign
def launch_walletchk():  import mmgen.main_walletchk
def launch_walletgen():  import mmgen.main_walletgen

def launch(what):
	try: import termios
	except: globals()["launch_"+what]() # Windows
	else:
		import sys,atexit
		fd = sys.stdin.fileno()
		old = termios.tcgetattr(fd)
		def at_exit():
			termios.tcsetattr(fd, termios.TCSADRAIN, old)
		atexit.register(at_exit)
		try: globals()["launch_"+what]()
		except KeyboardInterrupt:
			sys.stderr.write("\nUser interrupt\n")
		except EOFError:
			sys.stderr.write("\nEnd of file\n")
