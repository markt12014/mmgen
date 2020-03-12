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
common.py: Shared routines and data for the test.py test suite
"""

import os,time
from mmgen.common import *
from ..common import *

log_file = 'test.py.log'

rt_pw = 'abc-α'
ref_wallet_brainpass = 'abc'
ref_wallet_hash_preset = '1'
ref_wallet_incog_offset = 123

dfl_seed_id = '98831F3A'
dfl_addr_idx_list = '1010,500-501,31-33,1,33,500,1011'
dfl_wpasswd = 'reference password'

pwfile = 'passwd_file'
hincog_fn = 'rand_data'
hincog_bytes = 1024*1024
hincog_offset = 98765
hincog_seedlen = 256

incog_id_fn = 'incog_id'
non_mmgen_fn = 'coinkey'

ref_dir = os.path.join('test','ref')
dfl_words_file = os.path.join(ref_dir,'98831F3A.mmwords')

from mmgen.obj import MMGenTXLabel,TwComment

tx_label_jp = text_jp
tx_label_zh = text_zh

lcg = ascii_cyr_gr if g.platform == 'win' else lat_cyr_gr # MSYS2 popen_spawn issue
tx_label_lat_cyr_gr = lcg[:MMGenTXLabel.max_len] # 72 chars

tw_label_zh         = text_zh[:TwComment.max_screen_width // 2]
tw_label_lat_cyr_gr = lcg[:TwComment.max_screen_width] # 80 chars

ref_bw_hash_preset = '1'
ref_bw_file = 'wallet.mmbrain'
ref_bw_file_spc = 'wallet-spaced.mmbrain'

ref_enc_fn = 'sample-text.mmenc'
tool_enc_passwd = "Scrypt it, don't hash it!"
chksum_pat = r'\b[A-F0-9]{4} [A-F0-9]{4} [A-F0-9]{4} [A-F0-9]{4}\b'

def ok_msg():
	if opt.profile: return
	sys.stderr.write(green('\nOK\n') if opt.exact_output or opt.verbose else ' OK\n')

def skip(name,reason=None):
	msg('Skipping {}{}'.format(name,' ({})'.format(reason) if reason else ''))
	return 'skip'

def confirm_continue():
	if keypress_confirm(blue('Continue? (Y/n): '),default_yes=True,complete_prompt=True):
		if opt.verbose or opt.exact_output: sys.stderr.write('\n')
	else:
		raise KeyboardInterrupt('Exiting at user request')

def randbool():
	return os.urandom(1).hex()[0] in '02468ace'

def disable_debug():
	global save_debug
	save_debug = {}
	for k in g.env_opts:
		if k[:11] == 'MMGEN_DEBUG':
			save_debug[k] = os.getenv(k)
			os.environ[k] = ''

def restore_debug():
	for k in save_debug:
		os.environ[k] = save_debug[k] or ''

def get_file_with_ext(tdir,ext,delete=True,no_dot=False,return_list=False,delete_all=False):

	dot = ('.','')[bool(no_dot)]
	flist = [os.path.join(tdir,f) for f in os.listdir(tdir) if f == ext or f[-len(dot+ext):] == dot+ext]

	if not flist: return False
	if return_list: return flist

	if len(flist) > 1 or delete_all:
		if delete or delete_all:
			if not opt.quiet:
				msg("Multiple *.{} files in '{}' - deleting".format(ext,tdir))
			for f in flist:
				os.unlink(f)
		return False
	else:
		return flist[0]

labels = [
	"Automotive",
	"Travel expenses",
	"Healthcare",
	tx_label_jp[:40],
	tx_label_zh[:40],
	"Alice's allowance",
	"Bob's bequest",
	"House purchase",
	"Real estate fund",
	"Job 1",
	"XYZ Corp.",
	"Eddie's endowment",
	"Emergency fund",
	"Real estate fund",
	"Ian's inheritance",
	"",
	"Rainy day",
	"Fred's funds",
	"Job 2",
	"Carl's capital",
]

def get_label(do_shuffle=False):
	from random import shuffle
	global label_iter
	try:
		return next(label_iter)
	except:
		if do_shuffle: shuffle(labels)
		label_iter = iter(labels)
		return next(label_iter)

def stealth_mnemonic_entry(t,mne,mn,entry_mode,pad_entry=False):

	def pad_mnemonic(mn,ss_len):
		def get_pad_chars(n):
			ret = ''
			for i in range(n):
				m = int.from_bytes(os.urandom(1),'big') % 32
				ret += r'123579!@#$%^&*()_+-=[]{}"?/,.<>|'[m]
			return ret
		ret = []
		for w in mn:
			if entry_mode == 'short':
				w = w[:ss_len]
				if len(w) < ss_len:
					npc = 3
					w = w[0] + get_pad_chars(npc) + w[1:]
					if pad_entry:
						w += '%' * (1 + mne.em.pad_max - npc)
					else:
						w += '\n'
				else:
					w = get_pad_chars(1) + w[0] + get_pad_chars(1) + w[1:]
			elif len(w) > (3,5)[ss_len==12]:
				w = w + '\n'
			else:
				w = (
					get_pad_chars(2 if randbool() and entry_mode != 'short' else 0)
					+ w[0] + get_pad_chars(2) + w[1:]
					+ get_pad_chars(9) )
				w = w[:ss_len+1]
			ret.append(w)
		return ret

	if entry_mode == 'fixed':
		mn = ['bkr'] + mn[:5] + ['nfb'] + mn[5:]
		ssl = mne.uniq_ss_len
		mn = [w[:ssl] if len(w) >= ssl else (w[0] + 'z\b{}'.format('#'*(ssl-len(w))) + w[1:]) for w in mn]
	elif entry_mode in ('full','short'):
		mn = ['fzr'] + mn[:5] + ['grd','grdbxm'] + mn[5:]
		mn = pad_mnemonic(mn,mne.em.ss_len)
		mn[10] = '@#$%*##' + mn[10]

	wnum = 1
	p_ok,p_err = mne.word_prompt
	for w in mn:
		ret = t.expect((p_ok.format(wnum),p_err.format(wnum-1)))
		if ret == 0:
			wnum += 1
		for j in range(len(w)):
			t.send(w[j])
			time.sleep(0.005)

def user_dieroll_entry(t,data):
	for s in data:
		t.expect(r'Enter die roll #.+: ',s,regex=True)
		time.sleep(0.005)
