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
mmgen-addrimport: Import addresses into a MMGen coin daemon tracking wallet
"""

import time

from .common import *
from .addr import AddrList,KeyAddrList
from .obj import TwLabel,is_coin_addr

ai_msgs = lambda k: {
	'rescan': """
WARNING: You've chosen the '--rescan' option.  Rescanning the blockchain is
necessary only if an address you're importing is already in the blockchain,
has a balance and is not in your tracking wallet.  Note that the rescanning
process is very slow (>30 min. for each imported address on a low-powered
computer).
	""".strip() if opt.rescan else """
WARNING: If any of the addresses you're importing is already in the blockchain,
has a balance and is not in your tracking wallet, you must exit the program now
and rerun it using the '--rescan' option.
""".strip(),
	'bad_args': """
You must specify an {pnm} address file, a single address with the '--address'
option, or a list of non-{pnm} addresses with the '--addrlist' option
""".strip().format(pnm=g.proj_name)
}[k]

# In batch mode, daemon just rescans each address separately anyway, so make
# --batch and --rescan incompatible.

opts_data = {
	'text': {
		'desc': """Import addresses into an {} tracking wallet""".format(g.proj_name),
		'usage':'[opts] [mmgen address file]',
		'options': """
-h, --help         Print this help message
--, --longhelp     Print help message for long options (common options)
-a, --address=a    Import the single coin address 'a'
-b, --batch        Import all addresses in one RPC call
-l, --addrlist     Address source is a flat list of non-MMGen coin addresses
-k, --keyaddr-file Address source is a key-address file
-q, --quiet        Suppress warnings
-r, --rescan       Rescan the blockchain.  Required if address to import is
                   in the blockchain and has a balance.  Rescanning is slow.
""",
	'notes': """\n
This command can also be used to update the comment fields of addresses
already in the tracking wallet.

The --batch and --rescan options cannot be used together.
"""
	}
}

cmd_args = opts.init(opts_data)

def import_mmgen_list(infile):
	al = (AddrList,KeyAddrList)[bool(opt.keyaddr_file)](infile)
	if al.al_id.mmtype in ('S','B'):
		from .tx import segwit_is_active
		if not segwit_is_active():
			rdie(2,'Segwit is not active on this chain. Cannot import Segwit addresses')
	return al

if len(cmd_args) == 1:
	infile = cmd_args[0]
	check_infile(infile)
	if opt.addrlist:
		al = AddrList(addrlist=get_lines_from_file(
			infile,
			'non-{pnm} addresses'.format(pnm=g.proj_name),
			trim_comments=True))
	else:
		al = import_mmgen_list(infile)
elif len(cmd_args) == 0 and opt.address:
	al = AddrList(addrlist=[opt.address])
	infile = 'command line'
else:
	die(1,ai_msgs('bad_args'))

m = ' from Seed ID {}'.format(al.al_id.sid) if hasattr(al.al_id,'sid') else ''
qmsg('OK. {} addresses{}'.format(al.num_addrs,m))

err_msg = None

from .tw import TrackingWallet
tw = TrackingWallet(mode='w')

if g.token:
	if not is_coin_addr(g.token):
		m = "When importing addresses for a new token, the token must be specified by address, not symbol."
		raise InvalidTokenAddress('{!r}: invalid token address\n{}'.format(m))
	sym = tw.addr2sym(g.token) # check for presence in wallet or blockchain; raises exception on failure

if opt.rescan and not 'rescan' in tw.caps:
	msg("'--rescan' ignored: not supported by {}".format(type(tw).__name__))
	opt.rescan = False

if opt.rescan and not opt.quiet:
	confirm_or_raise(ai_msgs('rescan'),'continue',expect='YES')

if opt.batch and not 'batch' in tw.caps:
	msg("'--batch' ignored: not supported by {}".format(type(tw).__name__))
	opt.batch = False

def import_address(addr,label,rescan):
	try: tw.import_address(addr,label,rescan)
	except Exception as e:
		global err_msg
		err_msg = e.args[0]
	if g.token and not tw.get_token_param(g.token,'symbol'):
		tw.set_token_param(g.token,'symbol',sym)
		tw.set_token_param(g.token,'decimals',tw.token_obj.decimals())

w_n_of_m = len(str(al.num_addrs)) * 2 + 2
w_mmid = 1 if opt.addrlist or opt.address else len(str(max(al.idxs()))) + 13
msg_fmt = '{{:{}}} {{:34}} {{:{}}}'.format(w_n_of_m,w_mmid)

if opt.rescan: import threading

fs = 'Importing {} address{} from {}{}'
bm =' (batch mode)' if opt.batch else ''
msg(fs.format(len(al.data),suf(al.data,'es'),infile,bm))

if not al.data[0].addr.is_for_chain(g.chain):
	die(2,'Address{} not compatible with {} chain!'.format((' list','')[bool(opt.address)],g.chain))

for n,e in enumerate(al.data):
	if e.idx:
		label = '{}:{}'.format(al.al_id,e.idx)
		if e.label: label += ' ' + e.label
		m = label
	else:
		label = '{}:{}'.format(g.proto.base_coin.lower(),e.addr)
		m = 'non-'+g.proj_name

	label = TwLabel(label)

	if opt.batch:
		if n == 0: arg_list = []
		arg_list.append((e.addr,label,False))
		continue

	msg_data = ('{}/{}:'.format(n+1,al.num_addrs),e.addr,'({})'.format(m))

	if opt.rescan:
		t = threading.Thread(target=import_address,args=[e.addr,label,True])
		t.daemon = True
		t.start()
		start = int(time.time())
		while True:
			if t.is_alive():
				elapsed = int(time.time()-start)
				msg_r(('\r{} '+msg_fmt).format(secs_to_hms(elapsed),*msg_data))
				time.sleep(0.5)
			else:
				if err_msg: die(2,'\nImport failed: {!r}'.format(err_msg))
				msg('\nOK')
				break
	else:
		import_address(e.addr,label,False)
		msg_r('\r'+msg_fmt.format(*msg_data))
		if err_msg: die(2,'\nImport failed: {!r}'.format(err_msg))
		msg(' - OK')

if opt.batch:
	ret = tw.batch_import_address(arg_list)
	msg('OK: {} addresses imported'.format(len(ret)))

del tw
