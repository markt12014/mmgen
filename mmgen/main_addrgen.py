#!/usr/bin/env python
#
# mmgen = Multi-Mode GENerator, command-line Bitcoin cold storage solution
# Copyright (C)2013-2014 Philemon <mmgen-py@yandex.com>
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
mmgen-addrgen: Generate a series or range of addresses from an MMGen
               deterministic wallet
"""

import sys

import mmgen.config as g
from mmgen.Opts import *
from mmgen.license import *
from mmgen.util import *
from mmgen.crypto import *
from mmgen.addr import *
from mmgen.tx import make_addr_data_chksum

what = "keys" if sys.argv[0].split("-")[-1] == "keygen" else "addresses"

help_data = {
	'prog_name': g.prog_name,
	'desc': """Generate a range or list of {} from an {g.proj_name} wallet,
                  mnemonic, seed or password""".format(what,g=g),
	'usage':"[opts] [infile] <address range or list>",
	'options': """
-h, --help              Print this help message{}
-d, --outdir=       d   Specify an alternate directory 'd' for output
-c, --save-checksum     Save address list checksum to file
-e, --echo-passphrase   Echo passphrase or mnemonic to screen upon entry
-H, --show-hash-presets Show information on available hash presets
-K, --no-keyconv        Force use of internal libraries for address gener-
                        ation, even if 'keyconv' is available
-l, --seed-len=     N   Length of seed.  Options: {seed_lens}
                        (default: {g.seed_len})
-p, --hash-preset=  p   Use scrypt.hash() parameters from preset 'p' when
                        hashing password (default: '{g.hash_preset}')
-P, --passwd-file=  f   Get MMGen wallet passphrase from file 'f'
-q, --quiet             Suppress warnings; overwrite files without
                        prompting
-S, --stdout            Print {what} to stdout
-v, --verbose           Produce more verbose output{}

-b, --from-brain=  l,p  Generate {what} from a user-created password,
                        i.e. a "brainwallet", using seed length 'l' and
                        hash preset 'p' (comma-separated)
-g, --from-incog        Generate {what} from an incognito wallet
-X, --from-incog-hex    Generate {what} from incognito hexadecimal wallet
-G, --from-incog-hidden=f,o,l Generate {what} from incognito data in file
                        'f' at offset 'o', with seed length of 'l'
-o, --old-incog-fmt     Use old (pre-0.7.8) incog format
-m, --from-mnemonic     Generate {what} from an electrum-like mnemonic
-s, --from-seed         Generate {what} from a seed in .{g.seed_ext} format
""".format(
		*(
			(
"\n-A, --no-addresses      Print only secret keys, no addresses",
"\n-x, --b16               Print secret keys in hexadecimal too"
			)
		if what == "keys" else ("","")),
		seed_lens=", ".join([str(i) for i in g.seed_lens]),
		what=what, g=g
),
	'notes': """

Addresses are given in a comma-separated list.  Hyphen-separated ranges are
also allowed.{}

If available, the external 'keyconv' program will be used for address
generation.

Data for the --from-<what> options will be taken from <infile> if <infile>
is specified.  Otherwise, the user will be prompted to enter the data.

For passphrases all combinations of whitespace are equal, and leading and
trailing space are ignored.  This permits reading passphrase data from a
multi-line file with free spacing and indentation.  This is particularly
convenient for long brainwallet passphrases, for example.

BRAINWALLET NOTE:

As brainwallets require especially strong hashing to thwart dictionary
attacks, the brainwallet hash preset must be specified by the user, using
the 'p' parameter of the '--from-brain' option

The '--from-brain' option also requires the user to specify a seed length
(the 'l' parameter)

For a brainwallet passphrase to always generate the same keys and addresses,
the same 'l' and 'p' parameters to '--from-brain' must be used in all future
invocations with that passphrase
""".format("\n\nBy default, both addresses and secret keys are generated."
				if what == "keys" else "")
}

wmsg = {
	'unencrypted_secret_keys': """
This program generates secret keys from your {} seed, outputting them in
UNENCRYPTED form.  Generate only the key(s) you need and guard them carefully.
""".format(g.proj_name),
}

opts,cmd_args = parse_opts(sys.argv,help_data)

if 'show_hash_presets' in opts: show_hash_presets()
if 'from_incog_hex' in opts or 'from_incog_hidden' in opts:
	opts['from_incog'] = True

if g.debug: show_opts_and_cmd_args(opts,cmd_args)

if len(cmd_args) == 1 and (
			'from_mnemonic' in opts
			or 'from_brain' in opts
			or 'from_seed' in opts
			or 'from_incog_hidden' in opts
		):
	infile,addr_idx_arg = "",cmd_args[0]
elif len(cmd_args) == 2:
	infile,addr_idx_arg = cmd_args
	check_infile(infile)
else: usage(help_data)

addr_idxs = parse_addr_idxs(addr_idx_arg)

if not addr_idxs: sys.exit(2)

do_license_msg()

# Interact with user:
if what == "keys" and not g.quiet:
	confirm_or_exit(wmsg['unencrypted_secret_keys'], 'continue')

# Generate data:

seed    = get_seed_retry(infile,opts)
seed_id = make_chksum_8(seed)

opts['gen_what'] = "a" if what == "addresses" else (
	"k" if 'no_addresses' in opts else "ka")

addr_data = generate_addrs(seed, addr_idxs, opts)

if 'a' in opts['gen_what']:
	if 'k' in opts['gen_what']:
		def l(a): return ( a.num, (a.addr,"",a.wif) )
		keys = True
	else:
		def l(a): return ( a.num, (a.addr,) )
		keys = False
	addr_data_chksum = make_addr_data_chksum([l(a) for a in addr_data],keys)
else:
	addr_data_chksum = ""

addr_data_str = format_addr_data(
		addr_data, addr_data_chksum, seed_id, addr_idxs, opts)

outfile_base = "{}[{}]".format(seed_id, fmt_addr_idxs(addr_idxs))
if 'a' in opts['gen_what']:
	w = "key-address" if 'k' in opts['gen_what'] else "address"
	qmsg("Checksum for %s data %s: %s" % (w,outfile_base,addr_data_chksum))
	if 'save_checksum' in opts:
		write_to_file(outfile_base+"."+g.addrfile_chksum_ext,
			addr_data_chksum+"\n",opts,"%s data checksum" % w,True,True,False)
	else:
		qmsg("This checksum will be used to verify the %s file in the future."%w)
		qmsg("Record it to a safe location.")

if 'k' in opts['gen_what'] and keypress_confirm("Encrypt key list?"):
	addr_data_str = mmgen_encrypt(addr_data_str,"key list","",opts)
	enc_ext = "." + g.mmenc_ext
else: enc_ext = ""

# Output data:
if 'stdout' in opts or not sys.stdout.isatty():
	if enc_ext and sys.stdout.isatty():
		msg("Cannot write encrypted data to screen.  Exiting")
		sys.exit(2)
	write_to_stdout(addr_data_str,what,
		(what=="keys"and not g.quiet and sys.stdout.isatty()))
else:
	outfile = "%s.%s%s" % (outfile_base, (
		g.keyaddrfile_ext if "ka" in opts['gen_what'] else (
		g.keyfile_ext if "k" in opts['gen_what'] else
		g.addrfile_ext)), enc_ext)
	write_to_file(outfile,addr_data_str,opts,what,not g.quiet,True)