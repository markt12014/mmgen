#!/usr/bin/env python3
#
# mmgen = Multi-Mode GENerator, command-line Bitcoin cold storage solution
# Copyright (C)2013-2020 The MMGen Project <mmgen@tuta.io>
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
term.py:  Terminal classes for the MMGen suite
"""

import sys,os,time
from collections import namedtuple
from .common import *

try:
	import tty,termios
	from select import select
	_platform = 'linux'
except:
	try:
		import msvcrt
		_platform = 'mswin'
	except:
		die(2,'Unable to set terminal mode')
	if not sys.stdin.isatty():
		msvcrt.setmode(sys.stdin.fileno(),os.O_BINARY)

class MMGenTerm(object):

	tdim = namedtuple('terminal_dimensions',['width','height'])

	@classmethod
	def init(cls):
		pass

	@classmethod
	def kb_hold_protect(cls):
		return None

class MMGenTermLinux(MMGenTerm):

	@classmethod
	def init(cls):
		cls.stdin_fd = sys.stdin.fileno()
		cls.old_term = termios.tcgetattr(cls.stdin_fd)

	@classmethod
	def get_terminal_size(cls):
		try:
			ret = os.get_terminal_size()
		except:
			try:
				ret = (os.environ['COLUMNS'],os.environ['LINES'])
			except:
				ret = (80,25)
		return cls.tdim(*ret)

	@classmethod
	def kb_hold_protect(cls):
		if g.test_suite:
			return
		tty.setcbreak(cls.stdin_fd)
		timeout = 0.3
		while True:
			key = select([sys.stdin], [], [], timeout)[0]
			if key:
				sys.stdin.read(1)
			else:
				termios.tcsetattr(cls.stdin_fd, termios.TCSADRAIN, cls.old_term)
				break

	@classmethod
	def get_char(cls,prompt='',immed_chars='',prehold_protect=True,num_chars=5,sleep=None):
		"""
		Use os.read(), not file.read(), to get a variable number of bytes without blocking.
		Request 5 bytes to cover escape sequences generated by F1, F2, .. Fn keys (5 bytes)
		as well as UTF8 chars (4 bytes max).
		"""
		timeout = 0.3
		tty.setcbreak(cls.stdin_fd)
		if sleep:
			time.sleep(sleep)
		msg_r(prompt)
		if g.test_suite:
			prehold_protect = False
		while True:
			# Protect against held-down key before read()
			key = select([sys.stdin], [], [], timeout)[0]
			s = os.read(cls.stdin_fd,num_chars).decode()
			if prehold_protect and key:
				continue
			if s in immed_chars:
				break
			# Protect against long keypress
			key = select([sys.stdin], [], [], timeout)[0]
			if not key:
				break
		termios.tcsetattr(cls.stdin_fd, termios.TCSADRAIN, cls.old_term)
		return s

	@classmethod
	def get_char_raw(cls,prompt='',num_chars=5,sleep=None):
		tty.setcbreak(cls.stdin_fd)
		if sleep:
			time.sleep(sleep)
		msg_r(prompt)
		s = os.read(cls.stdin_fd,num_chars).decode()
		termios.tcsetattr(cls.stdin_fd, termios.TCSADRAIN, cls.old_term)
		return s

class MMGenTermLinuxStub(MMGenTermLinux):

	@classmethod
	def init(cls):
		pass

	@classmethod
	def get_char(cls,prompt='',immed_chars='',prehold_protect=None,num_chars=None,sleep=None):
		if sleep:
			time.sleep(0.1)
		msg_r(prompt)
		return sys.stdin.read(1)

	get_char_raw = get_char

class MMGenTermMSWin(MMGenTerm):

	@classmethod
	def get_terminal_size(cls):
		import struct
		x,y = 0,0
		try:
			from ctypes import windll,create_string_buffer
			# handles - stdin: -10, stdout: -11, stderr: -12
			csbi = create_string_buffer(22)
			h = windll.kernel32.GetStdHandle(-12)
			res = windll.kernel32.GetConsoleScreenBufferInfo(h,csbi)
			assert res, 'failed to get console screen buffer info'
			left,top,right,bottom = struct.unpack('hhhhHhhhhhh', csbi.raw)[5:9]
			x = right - left + 1
			y = bottom - top + 1
		except:
			pass

		if x and y:
			return cls.tdim(x,y)
		else:
			msg(yellow('Warning: could not get terminal size. Using fallback dimensions.'))
			return cls.tdim(80,25)

	@classmethod
	def kb_hold_protect(cls):
		timeout = 0.5
		while True:
			hit_time = time.time()
			while True:
				if msvcrt.kbhit():
					msvcrt.getch()
					break
				if time.time() - hit_time > timeout:
					return

	@classmethod
	def get_char(cls,prompt='',immed_chars='',prehold_protect=True,num_chars=None,sleep=None):
		"""
		always return a single character, ignore num_chars
		first character of 2-character sequence returned by F1-F12 keys is discarded
		prehold_protect is ignored
		"""
		if sleep:
			time.sleep(sleep)
		msg_r(prompt)
		timeout = 0.5
		while True:
			if msvcrt.kbhit():
				ch = chr(msvcrt.getch()[0])
				if ch == '\x03':
					raise KeyboardInterrupt
				if ch in immed_chars:
					return ch
				hit_time = time.time()
				while True:
					if msvcrt.kbhit():
						break
					if time.time() - hit_time > timeout:
						return ch

	@classmethod
	def get_char_raw(cls,prompt='',num_chars=None,sleep=None):
		"""
		always return a single character, ignore num_chars
		first character of 2-character sequence returned by F1-F12 keys is discarded
		"""
		while True:
			if sleep:
				time.sleep(sleep)
			msg_r(prompt)
			ch = chr(msvcrt.getch()[0])
			if ch in '\x00\xe0': # first char of 2-char sequence for F1-F12 keys
				continue
			if ch == '\x03':
				raise KeyboardInterrupt
			return ch

class MMGenTermMSWinStub(MMGenTermMSWin):

	@classmethod
	def get_char(cls,prompt='',immed_chars='',prehold_protect=None,num_chars=None,sleep=None):
		if sleep:
			time.sleep(0.1)
		msg_r(prompt)
		return os.read(0,1).decode()

	get_char_raw = get_char

def init_term():

	term = {
		'linux': (MMGenTermLinux if sys.stdin.isatty() else MMGenTermLinuxStub),
		'mswin': (MMGenTermMSWin if sys.stdin.isatty() else MMGenTermMSWinStub),
	}[_platform]

	term.init()

	global get_char,get_char_raw,kb_hold_protect,get_terminal_size

	for var in ('get_char','get_char_raw','kb_hold_protect','get_terminal_size'):
		globals()[var] = getattr(term,var)
