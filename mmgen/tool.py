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
tool.py:  Routines for the 'mmgen-tool' utility
"""

from mmgen.protocol import hash160
from mmgen.common import *
from mmgen.crypto import *
from mmgen.addr import *

NL = ('\n','\r\n')[g.platform=='win']

def _create_call_sig(cmd,parsed=False):

	m = getattr(MMGenToolCmd,cmd)

	if 'varargs_call_sig' in m.__code__.co_varnames: # hack
		flag = 'VAR_ARGS'
		va = m.__defaults__[0]
		args,dfls,ann = va['args'],va['dfls'],va['annots']
	else:
		flag = None
		args = m.__code__.co_varnames[1:m.__code__.co_argcount]
		dfls = m.__defaults__ or ()
		ann  = m.__annotations__

	nargs = len(args) - len(dfls)

	def get_type_from_ann(arg):
		return ann[arg][1:] + (' or STDIN','')[parsed] if ann[arg] == 'sstr' else ann[arg].__name__

	if parsed:
		c_args = [(a,get_type_from_ann(a)) for a in args[:nargs]]
		c_kwargs = [(a,dfls[n]) for n,a in enumerate(args[nargs:])]
		return c_args,dict(c_kwargs),'STDIN_OK' if c_args and ann[args[0]] == 'sstr' else flag
	else:
		c_args = ['{} [{}]'.format(a,get_type_from_ann(a)) for a in args[:nargs]]
		c_kwargs = ['"{}" [{}={!r}{}]'.format(
					a, type(dfls[n]).__name__, dfls[n],
					(' ' + ann[a] if a in ann else ''))
						for n,a in enumerate(args[nargs:])]
		return ' '.join(c_args + c_kwargs)

def _usage(cmd=None,exit_val=1):

	m1=('USAGE INFORMATION FOR MMGEN-TOOL COMMANDS:\n\n'
		'  Unquoted arguments are mandatory\n'
		'  Quoted arguments are optional, default values will be used\n'
		'  Argument types and default values are shown in square brackets\n')

	m2=('  To force a command to read from STDIN instead of file (for commands taking\n'
		'  a filename as their first argument), substitute "-" for the filename.\n\n'
		'EXAMPLES:\n\n'
		'  Generate a random Bech32 public/private keypair for LTC:\n'
		'  $ mmgen-tool -r0 --coin=ltc --type=bech32 randpair\n\n'
		'  Generate a DASH compressed public key address from the supplied WIF key:\n'
		'  $ mmgen-tool --coin=dash --type=compressed wif2addr XJkVRC3eGKurc9Uzx1wfQoio3yqkmaXVqLMTa6y7s3M3jTBnmxfw\n\n'
		'  Generate a well-known burn address:\n'
		'  $ mmgen-tool hextob58chk 000000000000000000000000000000000000000000\n\n'
		'  Generate a random 12-word seed phrase:\n'
		'  $ mmgen-tool -r0 mn_rand128\n\n'
		'  Same as above, but get additional entropy from user:\n'
		'  $ mmgen-tool mn_rand128\n\n'
		'  Encode bytes from a file to base 58:\n'
		'  $ mmgen-tool bytestob58 /etc/timezone pad=20\n\n'
		'  Reverse a hex string:\n'
		'  $ mmgen-tool hexreverse "deadbeefcafe"\n\n'
		'  Same as above, but use a pipe:\n'
		'  $ echo "deadbeefcafe" | mmgen-tool hexreverse -')

	if not cmd:
		Msg(m1)
		for bc in MMGenToolCmd.__bases__:
			cls_info = bc.__doc__.strip().split('\n')[0]
			Msg('  {}{}\n'.format(cls_info[0].upper(),cls_info[1:]))
			ucmds = bc._user_commands()
			max_w = max(map(len,ucmds))
			for cmd in ucmds:
				if getattr(MMGenToolCmd,cmd).__doc__:
					Msg('    {:{w}} {}'.format(cmd,_create_call_sig(cmd),w=max_w))
			Msg('')
		Msg(m2)
	elif cmd in MMGenToolCmd._user_commands():
		docstr = getattr(MMGenToolCmd,cmd).__doc__.strip()
		msg('{}'.format(capfirst(docstr)))
		msg('USAGE: {} {} {}'.format(g.prog_name,cmd,_create_call_sig(cmd)))
	else:
		die(1,"'{}': no such tool command".format(cmd))

	sys.exit(exit_val)

def _process_args(cmd,cmd_args):
	c_args,c_kwargs,flag = _create_call_sig(cmd,parsed=True)
	have_stdin_input = False

	if flag != 'VAR_ARGS':
		if len(cmd_args) < len(c_args):
			m1 = 'Command requires exactly {} non-keyword argument{}'
			msg(m1.format(len(c_args),suf(c_args)))
			_usage(cmd)

		u_args = cmd_args[:len(c_args)]

		# If we're reading from a pipe, replace '-' with output of previous command
		if flag == 'STDIN_OK' and u_args and u_args[0] == '-':
			if sys.stdin.isatty():
				raise BadFilename("Standard input is a TTY.  Can't use '-' as a filename")
			else:
				max_dlen_spec = '10kB' # limit input to 10KB for now
				max_dlen = MMGenToolCmdUtil().bytespec(max_dlen_spec)
				u_args[0] = os.read(0,max_dlen)
# 				try: u_args[0] = u_args[0].decode()
# 				except: pass
				have_stdin_input = True
				if len(u_args[0]) >= max_dlen:
					die(2,'Maximum data input for this command is {}'.format(max_dlen_spec))
				if not u_args[0]:
					die(2,'{}: ERROR: no output from previous command in pipe'.format(cmd))

	u_nkwargs = len(cmd_args) - len(c_args)
	u_kwargs = {}
	if flag == 'VAR_ARGS':
		t = [a.split('=',1) for a in cmd_args if '=' in a]
		tk = [a[0] for a in t]
		tk_bad = [a for a in tk if a not in c_kwargs]
		if set(tk_bad) != set(tk[:len(tk_bad)]): # permit non-kw args to contain '='
			die(1,"'{}': illegal keyword argument".format(tk_bad[-1]))
		u_kwargs = dict(t[len(tk_bad):])
		u_args = cmd_args[:-len(u_kwargs) or None]
	elif u_nkwargs > 0:
		u_kwargs = dict([a.split('=',1) for a in cmd_args[len(c_args):] if '=' in a])
		if len(u_kwargs) != u_nkwargs:
			msg('Command requires exactly {} non-keyword argument{}'.format(len(c_args),suf(c_args)))
			_usage(cmd)
		if len(u_kwargs) > len(c_kwargs):
			msg('Command accepts no more than {} keyword argument{}'.format(len(c_kwargs),suf(c_kwargs)))
			_usage(cmd)

	for k in u_kwargs:
		if k not in c_kwargs:
			msg("'{}': invalid keyword argument".format(k))
			_usage(cmd)

	def conv_type(arg,arg_name,arg_type):
		if arg_type == 'bytes' and type(arg) != bytes:
			die(1,"'Binary input data must be supplied via STDIN")

		if have_stdin_input and arg_type == 'str' and isinstance(arg,bytes):
			arg = arg.decode()
			if arg[-len(NL):] == NL: # rstrip one newline
				arg = arg[:-len(NL)]

		if arg_type == 'bool':
			if arg.lower() in ('true','yes','1','on'): arg = True
			elif arg.lower() in ('false','no','0','off'): arg = False
			else:
				msg("'{}': invalid boolean value for keyword argument".format(arg))
				_usage(cmd)

		try:
			return __builtins__[arg_type](arg)
		except:
			die(1,"'{}': Invalid argument for argument {} ('{}' required)".format(arg,arg_name,arg_type))

	if flag == 'VAR_ARGS':
		args = [conv_type(u_args[i],c_args[0][0],c_args[0][1]) for i in range(len(u_args))]
	else:
		args = [conv_type(u_args[i],c_args[i][0],c_args[i][1]) for i in range(len(c_args))]
	kwargs = {k:conv_type(u_kwargs[k],k,type(c_kwargs[k]).__name__) for k in u_kwargs}

	return args,kwargs

def _process_result(ret,pager=False,print_result=False):
	"""
	Convert result to something suitable for output to screen and return it.
	If result is bytes and not convertible to utf8, output as binary using os.write().
	If 'print_result' is True, send the converted result directly to screen or
	pager instead of returning it.
	"""
	def triage_result(o):
		return o if not print_result else do_pager(o) if pager else Msg(o)

	if ret == True:
		return True
	elif ret in (False,None):
		ydie(1,"tool command returned '{}'".format(ret))
	elif isinstance(ret,str):
		return triage_result(ret)
	elif isinstance(ret,int):
		return triage_result(str(ret))
	elif isinstance(ret,tuple):
		return triage_result('\n'.join([r.decode() if isinstance(r,bytes) else r for r in ret]))
	elif isinstance(ret,bytes):
		try:
			o = ret.decode()
			return o if not print_result else do_pager(o) if pager else Msg(o)
		except:
			# don't add NL to binary data if it can't be converted to utf8
			return ret if not print_result else os.write(1,ret)
	else:
		ydie(1,"tool.py: can't handle return value of type '{}'".format(type(ret).__name__))

from mmgen.obj import MMGenAddrType

def init_generators(arg=None):
	global at,kg,ag
	at = MMGenAddrType((hasattr(opt,'type') and opt.type) or g.proto.dfl_mmtype)
	if arg != 'at':
		kg = KeyGenerator(at)
		ag = AddrGenerator(at)

def conv_cls_bip39():
	from mmgen.bip39 import bip39
	return bip39

dfl_mnemonic_fmt = 'mmgen'
mnemonic_fmts = {
	'mmgen': { 'fmt': 'words', 'conv_cls': lambda: baseconv },
	'bip39': { 'fmt': 'bip39', 'conv_cls': conv_cls_bip39 },
	'xmrseed': { 'fmt': 'xmrseed','conv_cls': lambda: baseconv },
}
mn_opts_disp = "(valid options: '{}')".format("', '".join(mnemonic_fmts))

class MMGenToolCmdBase(object):

	@classmethod
	def _user_commands(cls):
		return [e for e in dir(cls) if e[0] != '_' and getattr(cls,e).__doc__ and callable(getattr(cls,e))]


class MMGenToolCmdMisc(MMGenToolCmdBase):
	"miscellaneous commands"

	def help(self,command_name=''):
		"display usage information for a single command or all commands"
		_usage(command_name,exit_val=0)

	usage = help

class MMGenToolCmdUtil(MMGenToolCmdBase):
	"general string conversion and hashing utilities"

	def bytespec(self,dd_style_byte_specifier:str):
		"convert a byte specifier such as '1GB' into an integer"
		return parse_bytespec(dd_style_byte_specifier)

	def randhex(self,nbytes='32'):
		"print 'n' bytes (default 32) of random data in hex format"
		return get_random(int(nbytes)).hex()

	def hexreverse(self,hexstr:'sstr'):
		"reverse bytes of a hexadecimal string"
		return bytes.fromhex(hexstr.strip())[::-1].hex()

	def hexlify(self,infile:str):
		"convert bytes in file to hexadecimal (use '-' for stdin)"
		data = get_data_from_file(infile,dash=True,quiet=True,binary=True)
		return data.hex()

	def unhexlify(self,hexstr:'sstr'):
		"convert hexadecimal value to bytes (warning: outputs binary data)"
		return bytes.fromhex(hexstr)

	def hexdump(self,infile:str,cols=8,line_nums='hex'):
		"create hexdump of data from file (use '-' for stdin)"
		data = get_data_from_file(infile,dash=True,quiet=True,binary=True)
		return pretty_hexdump(data,cols=cols,line_nums=line_nums).rstrip()

	def unhexdump(self,infile:str):
		"decode hexdump from file (use '-' for stdin) (warning: outputs binary data)"
		if g.platform == 'win':
			import msvcrt
			msvcrt.setmode(sys.stdout.fileno(),os.O_BINARY)
		hexdata = get_data_from_file(infile,dash=True,quiet=True)
		return decode_pretty_hexdump(hexdata)

	def hash160(self,hexstr:'sstr'):
		"compute ripemd160(sha256(data)) (convert hex pubkey to hex addr)"
		return hash160(hexstr)

	def hash256(self,string_or_bytes:str,file_input=False,hex_input=False): # TODO: handle stdin
		"compute sha256(sha256(data)) (double sha256)"
		from hashlib import sha256
		if file_input:  b = get_data_from_file(string_or_bytes,binary=True)
		elif hex_input: b = decode_pretty_hexdump(string_or_bytes)
		else:           b = string_or_bytes
		return sha256(sha256(b.encode()).digest()).hexdigest()

	def id6(self,infile:str):
		"generate 6-character MMGen ID for a file (use '-' for stdin)"
		return make_chksum_6(
			get_data_from_file(infile,dash=True,quiet=True,binary=True))

	def str2id6(self,string:'sstr'): # retain ignoring of space for backwards compat
		"generate 6-character MMGen ID for a string, ignoring spaces"
		return make_chksum_6(''.join(string.split()))

	def id8(self,infile:str):
		"generate 8-character MMGen ID for a file (use '-' for stdin)"
		return make_chksum_8(
			get_data_from_file(infile,dash=True,quiet=True,binary=True))

	def randb58(self,nbytes=32,pad=0):
		"generate random data (default: 32 bytes) and convert it to base 58"
		return baseconv.frombytes(get_random(nbytes),'b58',pad=pad,tostr=True)

	def bytestob58(self,infile:str,pad=0):
		"convert bytes to base 58 (supply data via STDIN)"
		data = get_data_from_file(infile,dash=True,quiet=True,binary=True)
		return baseconv.frombytes(data,'b58',pad=pad,tostr=True)

	def b58tobytes(self,b58num:'sstr',pad=0):
		"convert a base 58 number to bytes (warning: outputs binary data)"
		return baseconv.tobytes(b58num,'b58',pad=pad)

	def hextob58(self,hexstr:'sstr',pad=0):
		"convert a hexadecimal number to base 58"
		return baseconv.fromhex(hexstr,'b58',pad=pad,tostr=True)

	def b58tohex(self,b58num:'sstr',pad=0):
		"convert a base 58 number to hexadecimal"
		return baseconv.tohex(b58num,'b58',pad=pad)

	def hextob58chk(self,hexstr:'sstr'):
		"convert a hexadecimal number to base58-check encoding"
		from mmgen.protocol import _b58chk_encode
		return _b58chk_encode(bytes.fromhex(hexstr))

	def b58chktohex(self,b58chk_num:'sstr'):
		"convert a base58-check encoded number to hexadecimal"
		from mmgen.protocol import _b58chk_decode
		return _b58chk_decode(b58chk_num).hex()

	def hextob32(self,hexstr:'sstr',pad=0):
		"convert a hexadecimal number to MMGen's flavor of base 32"
		return baseconv.fromhex(hexstr,'b32',pad,tostr=True)

	def b32tohex(self,b32num:'sstr',pad=0):
		"convert an MMGen-flavor base 32 number to hexadecimal"
		return baseconv.tohex(b32num.upper(),'b32',pad)

	def hextob6d(self,hexstr:'sstr',pad=0,add_spaces=True):
		"convert a hexadecimal number to die roll base6 (base6d)"
		ret = baseconv.fromhex(hexstr,'b6d',pad,tostr=True)
		return block_format(ret,gw=5,cols=None).strip() if add_spaces else ret

	def b6dtohex(self,b6d_num:'sstr',pad=0):
		"convert a die roll base6 (base6d) number to hexadecimal"
		return baseconv.tohex(remove_whitespace(b6d_num),'b6d',pad)

class MMGenToolCmdCoin(MMGenToolCmdBase):
	"""
	cryptocoin key/address utilities

		May require use of the '--coin', '--type' and/or '--testnet' options

		Examples:
			mmgen-tool --coin=ltc --type=bech32 wif2addr <wif key>
			mmgen-tool --coin=zec --type=zcash_z randpair
	"""
	def randwif(self):
		"generate a random private key in WIF format"
		init_generators('at')
		return PrivKey(get_random(32),pubkey_type=at.pubkey_type,compressed=at.compressed).wif

	def randpair(self):
		"generate a random private key/address pair"
		init_generators()
		privhex = PrivKey(get_random(32),pubkey_type=at.pubkey_type,compressed=at.compressed)
		addr = ag.to_addr(kg.to_pubhex(privhex))
		return (privhex.wif,addr)

	def wif2hex(self,wifkey:'sstr'):
		"convert a private key from WIF to hex format"
		return PrivKey(wif=wifkey)

	def hex2wif(self,privhex:'sstr'):
		"convert a private key from hex to WIF format"
		init_generators('at')
		return PrivKey(bytes.fromhex(privhex),pubkey_type=at.pubkey_type,compressed=at.compressed).wif

	def wif2addr(self,wifkey:'sstr'):
		"generate a coin address from a key in WIF format"
		init_generators()
		privhex = PrivKey(wif=wifkey)
		addr = ag.to_addr(kg.to_pubhex(privhex))
		return addr

	def wif2redeem_script(self,wifkey:'sstr'): # new
		"convert a WIF private key to a Segwit P2SH-P2WPKH redeem script"
		assert opt.type == 'segwit','This command is meaningful only for --type=segwit'
		init_generators()
		privhex = PrivKey(wif=wifkey)
		return ag.to_segwit_redeem_script(kg.to_pubhex(privhex))

	def wif2segwit_pair(self,wifkey:'sstr'):
		"generate both a Segwit P2SH-P2WPKH redeem script and address from WIF"
		assert opt.type == 'segwit','This command is meaningful only for --type=segwit'
		init_generators()
		pubhex = kg.to_pubhex(PrivKey(wif=wifkey))
		addr = ag.to_addr(pubhex)
		rs = ag.to_segwit_redeem_script(pubhex)
		return (rs,addr)

	def privhex2addr(self,privhex:'sstr',output_pubhex=False):
		"generate coin address from raw private key data in hexadecimal format"
		init_generators()
		pk = PrivKey(bytes.fromhex(privhex),compressed=at.compressed,pubkey_type=at.pubkey_type)
		ph = kg.to_pubhex(pk)
		return ph if output_pubhex else ag.to_addr(ph)

	def privhex2pubhex(self,privhex:'sstr'): # new
		"generate a hex public key from a hex private key"
		return self.privhex2addr(privhex,output_pubhex=True)

	def pubhex2addr(self,pubkeyhex:'sstr'):
		"convert a hex pubkey to an address"
		if opt.type == 'segwit':
			return g.proto.pubhex2segwitaddr(pubkeyhex)
		else:
			return self.pubhash2addr(hash160(pubkeyhex))

	def pubhex2redeem_script(self,pubkeyhex:'sstr'): # new
		"convert a hex pubkey to a Segwit P2SH-P2WPKH redeem script"
		assert opt.type == 'segwit','This command is meaningful only for --type=segwit'
		return g.proto.pubhex2redeem_script(pubkeyhex)

	def redeem_script2addr(self,redeem_scripthex:'sstr'): # new
		"convert a Segwit P2SH-P2WPKH redeem script to an address"
		assert opt.type == 'segwit','This command is meaningful only for --type=segwit'
		assert redeem_scripthex[:4] == '0014','{!r}: invalid redeem script'.format(redeem_scripthex)
		assert len(redeem_scripthex) == 44,'{} bytes: invalid redeem script length'.format(len(redeem_scripthex)//2)
		return self.pubhash2addr(self.hash160(redeem_scripthex))

	def pubhash2addr(self,pubhashhex:'sstr'):
		"convert public key hash to address"
		if opt.type == 'bech32':
			return g.proto.pubhash2bech32addr(pubhashhex)
		else:
			init_generators('at')
			return g.proto.pubhash2addr(pubhashhex,at.addr_fmt=='p2sh')

	def addr2pubhash(self,addr:'sstr'):
		"convert coin address to public key hash"
		from mmgen.tx import addr2pubhash
		return addr2pubhash(CoinAddr(addr))

	def addr2scriptpubkey(self,addr:'sstr'):
		"convert coin address to scriptPubKey"
		from mmgen.tx import addr2scriptPubKey
		return addr2scriptPubKey(CoinAddr(addr))

	def scriptpubkey2addr(self,hexstr:'sstr'):
		"convert scriptPubKey to coin address"
		from mmgen.tx import scriptPubKey2addr
		return scriptPubKey2addr(hexstr)[0]

class MMGenToolCmdMnemonic(MMGenToolCmdBase):
	"""
	seed phrase utilities (valid formats: 'mmgen' (default), 'bip39', 'xmrseed')

		IMPORTANT NOTE: MMGen's default seed phrase format uses the Electrum
		wordlist, however seed phrases are computed using a different algorithm
		and are NOT Electrum-compatible!

		BIP39 support is fully compatible with the standard, allowing users to
		import and export seed entropy from BIP39-compatible wallets.  However,
		users should be aware that BIP39 support does not imply BIP32 support!
		MMGen uses its own key derivation scheme differing from the one described
		by the BIP32 protocol.

		For Monero ('xmrseed') seed phrases, input data is reduced to a spendkey
		before conversion so that a canonical seed phrase is produced.  This is
		required because Monero seeds, unlike ordinary wallet seeds, are tied
		to a concrete key/address pair.  To manually generate a Monero spendkey,
		use the 'hex2wif' command.
	"""

	@staticmethod
	def _xmr_reduce(bytestr):
		from mmgen.protocol import MoneroProtocol as mp
		if len(bytestr) != mp.privkey_len:
			m = '{!r}: invalid bit length for Monero private key (must be {})'
			die(1,m.format(len(bytestr*8),mp.privkey_len*8))
		return mp.preprocess_key(bytestr,None)

	def _do_random_mn(self,nbytes:int,fmt:str):
		assert nbytes in (16,24,32), 'nbytes must be 16, 24 or 32'
		randbytes = get_random(nbytes)
		if fmt == 'xmrseed':
			randbytes = self._xmr_reduce(randbytes)
		if opt.verbose:
			msg('Seed: {}'.format(randbytes.hex()))
		return self.hex2mn(randbytes.hex(),fmt=fmt)

	def mn_rand128(self, fmt:mn_opts_disp = dfl_mnemonic_fmt ):
		"generate random 128-bit mnemonic seed phrase"
		return self._do_random_mn(16,fmt)

	def mn_rand192(self, fmt:mn_opts_disp = dfl_mnemonic_fmt ):
		"generate random 192-bit mnemonic seed phrase"
		return self._do_random_mn(24,fmt)

	def mn_rand256(self, fmt:mn_opts_disp = dfl_mnemonic_fmt ):
		"generate random 256-bit mnemonic seed phrase"
		return self._do_random_mn(32,fmt)

	def _get_mnemonic_fmt(self,fmt):
		if fmt not in mnemonic_fmts:
			m = '{!r}: invalid format (valid options: {})'
			die(1,m.format(fmt,', '.join(mnemonic_fmts)))
		return mnemonic_fmts[fmt]['fmt']

	def hex2mn( self, hexstr:'sstr', fmt:mn_opts_disp = dfl_mnemonic_fmt ):
		"convert a 16, 24 or 32-byte hexadecimal number to a mnemonic seed phrase"
		if fmt == 'bip39':
			from mmgen.bip39 import bip39
			return ' '.join(bip39.fromhex(hexstr,fmt))
		else:
			bytestr = bytes.fromhex(hexstr)
			if fmt == 'xmrseed':
				bytestr = self._xmr_reduce(bytestr)
			return baseconv.frombytes(bytestr,fmt,'seed',tostr=True)

	def mn2hex( self, seed_mnemonic:'sstr', fmt:mn_opts_disp = dfl_mnemonic_fmt ):
		"convert a mnemonic seed phrase to a hexadecimal number"
		if fmt == 'bip39':
			from mmgen.bip39 import bip39
			return bip39.tohex(seed_mnemonic.split(),fmt)
		else:
			return baseconv.tohex(seed_mnemonic.split(),fmt,'seed')

	def mn2hex_interactive( self, fmt:mn_opts_disp=dfl_mnemonic_fmt, mn_len=24, print_mn=False ):
		"convert an interactively supplied mnemonic seed phrase to a hexadecimal number"
		from mmgen.mn_entry import mn_entry
		mn = mn_entry(fmt).get_mnemonic_from_user(25 if fmt == 'xmrseed' else mn_len,validate=False)
		if print_mn:
			msg(mn)
		return self.mn2hex(seed_mnemonic=mn,fmt=fmt)

	def mn_stats(self, fmt:mn_opts_disp = dfl_mnemonic_fmt ):
		"show stats for mnemonic wordlist"
		conv_cls = mnemonic_fmts[fmt]['conv_cls']()
		return conv_cls.check_wordlist(fmt)

	def mn_printlist( self, fmt:mn_opts_disp = dfl_mnemonic_fmt, enum=False, pager=False ):
		"print mnemonic wordlist"
		conv_cls = mnemonic_fmts[fmt]['conv_cls']()
		ret = conv_cls.get_wordlist(fmt)
		if enum:
			ret = ['{:>4} {}'.format(n,e) for n,e in enumerate(ret)]
		return '\n'.join(ret)

class MMGenToolCmdFile(MMGenToolCmdBase):
	"utilities for viewing/checking MMGen address and transaction files"

	def _file_chksum(self,mmgen_addrfile,objname):
		opt.yes = True
		opt.quiet = True
		from mmgen.addr import AddrList,KeyAddrList,PasswordList
		ret = locals()[objname](mmgen_addrfile)
		if opt.verbose:
			if ret.al_id.mmtype.name == 'password':
				fs = 'Passwd fmt:  {}\nPasswd len:  {}\nID string:   {}'
				msg(fs.format(capfirst(ret.pw_info[ret.pw_fmt].desc),ret.pw_len,ret.pw_id_str))
			else:
				msg('Base coin:   {} {}'.format(ret.base_coin,('Mainnet','Testnet')[ret.is_testnet]))
				msg('MMType:      {}'.format(capfirst(ret.al_id.mmtype.name)))
			msg('List length: {}'.format(len(ret.data)))
		return ret.chksum

	def addrfile_chksum(self,mmgen_addrfile:str):
		"compute checksum for MMGen address file"
		return self._file_chksum(mmgen_addrfile,'AddrList')

	def keyaddrfile_chksum(self,mmgen_keyaddrfile:str):
		"compute checksum for MMGen key-address file"
		return self._file_chksum(mmgen_keyaddrfile,'KeyAddrList')

	def passwdfile_chksum(self,mmgen_passwdfile:str):
		"compute checksum for MMGen password file"
		return self._file_chksum(mmgen_passwdfile,'PasswordList')

	def txview( varargs_call_sig = { # hack to allow for multiple filenames
					'args': (
						'mmgen_tx_file(s)',
						'pager',
						'terse',
						'sort',
						'filesort' ),
					'dfls': ( False, False, 'addr', 'mtime' ),
					'annots': {
						'mmgen_tx_file(s)': str,
						'sort': '(valid options: addr,raw)',
						'filesort': '(valid options: mtime,ctime,atime)'
						} },
				*infiles,**kwargs):
		"show raw/signed MMGen transaction in human-readable form"

		terse = bool(kwargs.get('terse'))
		tx_sort = kwargs.get('sort') or 'addr'
		file_sort = kwargs.get('filesort') or 'mtime'

		from mmgen.filename import MMGenFileList
		from mmgen.tx import MMGenTX
		flist = MMGenFileList(infiles,ftype=MMGenTX)
		flist.sort_by_age(key=file_sort) # in-place sort

		sep = '—'*77+'\n'
		return sep.join(
			[MMGenTX(fn,offline=True).format_view(terse=terse,sort=tx_sort) for fn in flist.names()]
		).rstrip()

class MMGenToolCmdFileCrypt(MMGenToolCmdBase):
	"""
	file encryption and decryption

		MMGen encryption suite:
		* Key: Scrypt (user-configurable hash parameters, 32-byte salt)
		* Enc: AES256_CTR, 16-byte rand IV, sha256 hash + 32-byte nonce + data
		* The encrypted file is indistinguishable from random data
	"""
	def encrypt(self,infile:str,outfile='',hash_preset=''):
		"encrypt a file"
		data = get_data_from_file(infile,'data for encryption',binary=True)
		enc_d = mmgen_encrypt(data,'user data',hash_preset)
		if not outfile:
			outfile = '{}.{}'.format(os.path.basename(infile),g.mmenc_ext)
		write_data_to_file(outfile,enc_d,'encrypted data',binary=True)
		return True

	def decrypt(self,infile:str,outfile='',hash_preset=''):
		"decrypt a file"
		enc_d = get_data_from_file(infile,'encrypted data',binary=True)
		while True:
			dec_d = mmgen_decrypt(enc_d,'user data',hash_preset)
			if dec_d: break
			msg('Trying again...')
		if not outfile:
			o = os.path.basename(infile)
			outfile = remove_extension(o,g.mmenc_ext)
			if outfile == o: outfile += '.dec'
		write_data_to_file(outfile,dec_d,'decrypted data',binary=True)
		return True

class MMGenToolCmdFileUtil(MMGenToolCmdBase):
	"file utilities"

	def find_incog_data(self,filename:str,incog_id:str,keep_searching=False):
		"Use an Incog ID to find hidden incognito wallet data"
		ivsize,bsize,mod = g.aesctr_iv_len,4096,4096*8
		n,carry = 0,b' '*ivsize
		flgs = os.O_RDONLY|os.O_BINARY if g.platform == 'win' else os.O_RDONLY
		f = os.open(filename,flgs)
		for ch in incog_id:
			if ch not in '0123456789ABCDEF':
				die(2,"'{}': invalid Incog ID".format(incog_id))
		while True:
			d = os.read(f,bsize)
			if not d: break
			d = carry + d
			for i in range(bsize):
				if sha256(d[i:i+ivsize]).hexdigest()[:8].upper() == incog_id:
					if n+i < ivsize: continue
					msg('\rIncog data for ID {} found at offset {}'.format(incog_id,n+i-ivsize))
					if not keep_searching: sys.exit(0)
			carry = d[len(d)-ivsize:]
			n += bsize
			if not n % mod:
				msg_r('\rSearched: {} bytes'.format(n))

		msg('')
		os.close(f)
		return True

	def rand2file(self,outfile:str,nbytes:str,threads=4,silent=False):
		"write 'n' bytes of random data to specified file"
		from threading import Thread
		from queue import Queue
		from cryptography.hazmat.primitives.ciphers import Cipher,algorithms,modes
		from cryptography.hazmat.backends import default_backend

		def encrypt_worker(wid):
			ctr_init_val = os.urandom(g.aesctr_iv_len)
			c = Cipher(algorithms.AES(key),modes.CTR(ctr_init_val),backend=default_backend())
			encryptor = c.encryptor()
			while True:
				q2.put(encryptor.update(q1.get()))
				q1.task_done()

		def output_worker():
			while True:
				f.write(q2.get())
				q2.task_done()

		nbytes = parse_bytespec(nbytes)
		if opt.outdir:
			outfile = make_full_path(opt.outdir,outfile)
		f = open(outfile,'wb')

		key = get_random(32)
		q1,q2 = Queue(),Queue()

		for i in range(max(1,threads-2)):
			t = Thread(target=encrypt_worker,args=[i])
			t.daemon = True
			t.start()

		t = Thread(target=output_worker)
		t.daemon = True
		t.start()

		blk_size = 1024 * 1024
		for i in range(nbytes // blk_size):
			if not i % 4:
				msg_r('\rRead: {} bytes'.format(i * blk_size))
			q1.put(os.urandom(blk_size))

		if nbytes % blk_size:
			q1.put(os.urandom(nbytes % blk_size))

		q1.join()
		q2.join()
		f.close()

		fsize = os.stat(outfile).st_size
		if fsize != nbytes:
			die(3,'{}: incorrect random file size (should be {})'.format(fsize,nbytes))

		if not silent:
			msg('\rRead: {} bytes'.format(nbytes))
			qmsg("\r{} byte{} of random data written to file '{}'".format(nbytes,suf(nbytes),outfile))

		return True

class MMGenToolCmdWallet(MMGenToolCmdBase):
	"key, address or subseed generation from an MMGen wallet"

	def get_subseed(self,subseed_idx:str,wallet=''):
		"get the Seed ID of a single subseed by Subseed Index for default or specified wallet"
		opt.quiet = True
		sf = get_seed_file([wallet] if wallet else [],1)
		from mmgen.seed import SeedSource
		return SeedSource(sf).seed.subseed(subseed_idx).sid

	def get_subseed_by_seed_id(self,seed_id:str,wallet='',last_idx=g.subseeds):
		"get the Subseed Index of a single subseed by Seed ID for default or specified wallet"
		opt.quiet = True
		sf = get_seed_file([wallet] if wallet else [],1)
		from mmgen.seed import SeedSource
		ret = SeedSource(sf).seed.subseed_by_seed_id(seed_id,last_idx)
		return ret.ss_idx if ret else None

	def list_subseeds(self,subseed_idx_range:str,wallet=''):
		"list a range of subseed Seed IDs for default or specified wallet"
		opt.quiet = True
		sf = get_seed_file([wallet] if wallet else [],1)
		from mmgen.seed import SeedSource
		return SeedSource(sf).seed.subseeds.format(*SubSeedIdxRange(subseed_idx_range))

	def list_shares(self,
			share_count:int,
			id_str='default',
			master_share:"(min:1, max:{}, 0=no master share)".format(MasterShareIdx.max_val)=0,
			wallet=''):
		"list the Seed IDs of the shares resulting from a split of default or specified wallet"
		opt.quiet = True
		sf = get_seed_file([wallet] if wallet else [],1)
		from mmgen.seed import SeedSource
		return SeedSource(sf).seed.split(share_count,id_str,master_share).format()

	def gen_key(self,mmgen_addr:str,wallet=''):
		"generate a single MMGen WIF key from default or specified wallet"
		return self.gen_addr(mmgen_addr,wallet,target='wif')

	def gen_addr(self,mmgen_addr:str,wallet='',target='addr'):
		"generate a single MMGen address from default or specified wallet"
		addr = MMGenID(mmgen_addr)
		opt.quiet = True
		sf = get_seed_file([wallet] if wallet else [],1)
		from mmgen.seed import SeedSource
		ss = SeedSource(sf)
		if ss.seed.sid != addr.sid:
			m = 'Seed ID of requested address ({}) does not match wallet ({})'
			die(1,m.format(addr.sid,ss.seed.sid))
		al = AddrList(seed=ss.seed,addr_idxs=AddrIdxList(str(addr.idx)),mmtype=addr.mmtype)
		d = al.data[0]
		ret = d.sec.wif if target=='wif' else d.addr
		return ret

class MMGenToolCmdRPC(MMGenToolCmdBase):
	"tracking wallet commands using the JSON-RPC interface"

	def getbalance(self,minconf=1,quiet=False,pager=False):
		"list confirmed/unconfirmed, spendable/unspendable balances in tracking wallet"
		from mmgen.tw import TwGetBalance
		return TwGetBalance(minconf,quiet).format()

	def listaddress(self,
					mmgen_addr:str,
					minconf = 1,
					pager = False,
					showempty = True,
					showbtcaddr = True,
					age_fmt:'(valid options: days,confs)' = ''):
		"list the specified MMGen address and its balance"
		return self.listaddresses(  mmgen_addrs = mmgen_addr,
									minconf = minconf,
									pager = pager,
									showempty = showempty,
									showbtcaddrs = showbtcaddr,
									age_fmt = age_fmt)

	def listaddresses(  self,
						mmgen_addrs:'(range or list)' = '',
						minconf = 1,
						showempty = False,
						pager = False,
						showbtcaddrs = True,
						all_labels = False,
						sort:'(valid options: reverse,age)' = '',
						age_fmt:'(valid options: days,confs)' = ''):
		"list MMGen addresses and their balances"
		show_age = bool(age_fmt)

		if sort:
			sort = set(sort.split(','))
			sort_params = {'reverse','age'}
			if not sort.issubset(sort_params):
				die(1,"The sort option takes the following parameters: '{}'".format("','".join(sort_params)))

		usr_addr_list = []
		if mmgen_addrs:
			a = mmgen_addrs.rsplit(':',1)
			if len(a) != 2:
				m = "'{}': invalid address list argument (must be in form <seed ID>:[<type>:]<idx list>)"
				die(1,m.format(mmgen_addrs))
			usr_addr_list = [MMGenID('{}:{}'.format(a[0],i)) for i in AddrIdxList(a[1])]

		rpc_init()
		from mmgen.tw import TwAddrList
		al = TwAddrList(usr_addr_list,minconf,showempty,showbtcaddrs,all_labels)
		if not al:
			die(0,('No tracked addresses with balances!','No tracked addresses!')[showempty])
		return al.format(showbtcaddrs,sort,show_age,age_fmt or 'days')

	def twview( self,
				pager = False,
				reverse = False,
				wide = False,
				minconf = 1,
				sort = 'age',
				age_fmt:'(valid options: days,confs)' = 'days',
				show_mmid = True):
		"view tracking wallet"
		rpc_init()
		from mmgen.tw import TwUnspentOutputs
		twuo = TwUnspentOutputs(minconf=minconf)
		twuo.do_sort(sort,reverse=reverse)
		twuo.age_fmt = age_fmt
		twuo.show_mmid = show_mmid
		ret = twuo.format_for_printing(color=True) if wide else twuo.format_for_display()
		del twuo.wallet
		return ret

	def add_label(self,mmgen_or_coin_addr:str,label:str):
		"add descriptive label for address in tracking wallet"
		rpc_init()
		from mmgen.tw import TrackingWallet
		TrackingWallet(mode='w').add_label(mmgen_or_coin_addr,label,on_fail='raise')
		return True

	def remove_label(self,mmgen_or_coin_addr:str):
		"remove descriptive label for address in tracking wallet"
		self.add_label(mmgen_or_coin_addr,'')
		return True

	def remove_address(self,mmgen_or_coin_addr:str):
		"remove an address from tracking wallet"
		from mmgen.tw import TrackingWallet
		tw = TrackingWallet(mode='w')
		ret = tw.remove_address(mmgen_or_coin_addr) # returns None on failure
		if ret:
			msg("Address '{}' deleted from tracking wallet".format(ret))
		return ret

class MMGenToolCmdMonero(MMGenToolCmdBase):
	"""
	Monero wallet utilities

	Note that the use of these commands requires private data to be exposed on
	a network-connected machine in order to unlock the Monero wallets.  This is
	a violation of MMGen's security policy.
	"""

	_monero_chain_height = None
	monerod_args = []

	@property
	def monero_chain_height(self):
		if self._monero_chain_height == None:
			from mmgen.daemon import CoinDaemon
			port = CoinDaemon('xmr',test_suite=g.test_suite).rpc_port
			cmd = ['monerod','--rpc-bind-port={}'.format(port)] + self.monerod_args + ['status']

			from subprocess import run,PIPE,DEVNULL
			cp = run(cmd,stdout=PIPE,stderr=DEVNULL,check=True)
			import re
			m = re.search(r'Height: (\d+)/\d+ ',cp.stdout.decode())
			if not m:
				die(1,'Unable to connect to monerod!')
			self._monero_chain_height = int(m.group(1))
			msg('Chain height: {}'.format(self._monero_chain_height))

		return self._monero_chain_height

	def keyaddrlist2monerowallets(  self,
									xmr_keyaddrfile:str,
									blockheight:'(default: current height)' = 0,
									addrs:'(integer range or list)' = ''):
		"create Monero wallets from a key-address list"
		return self.monero_wallet_ops(  infile = xmr_keyaddrfile,
										op = 'create',
										blockheight = blockheight,
										addrs = addrs)

	def syncmonerowallets(self,xmr_keyaddrfile:str,addrs:'(integer range or list)'=''):
		"sync Monero wallets from a key-address list"
		return self.monero_wallet_ops(infile=xmr_keyaddrfile,op='sync',addrs=addrs)

	def monero_wallet_ops(self,infile:str,op:str,blockheight=0,addrs='',monerod_args=[]):

		if monerod_args:
			self.monerod_args = monerod_args

		def create(n,d,fn,c,m):
			try: os.stat(fn)
			except: pass
			else:
				ymsg("Wallet '{}' already exists!".format(fn))
				return False
			gmsg(m)

			from mmgen.baseconv import baseconv
			ret = c.restore_deterministic_wallet(
				filename  = os.path.basename(fn),
				password  = d.wallet_passwd,
				seed      = baseconv.fromhex(d.sec,'xmrseed',tostr=True),
				restore_height = blockheight,
				language  = 'English' )

			pp_msg(ret) if opt.verbose else msg('  Address: {}'.format(ret['address']))
			return True

		def sync(n,d,fn,c,m):
			try:
				os.stat(fn)
			except:
				ymsg("Wallet '{}' does not exist!".format(fn))
				return False

			chain_height = self.monero_chain_height
			gmsg(m)

			import time
			t_start = time.time()

			msg_r('  Opening wallet...')
			c.open_wallet(filename=os.path.basename(fn),password=d.wallet_passwd)
			msg('done')

			msg_r('  Getting wallet height...')
			wallet_height = c.get_height()['height']
			msg('\r  Wallet height: {}        '.format(wallet_height))

			behind = chain_height - wallet_height
			if behind > 1000:
				m = '  Wallet is {} blocks behind chain tip.  Please be patient.  Syncing...'
				msg_r(m.format(behind))

			ret = c.refresh()

			if behind > 1000:
				msg('done')

			if ret['received_money']:
				msg('  Wallet has received funds')

			t_elapsed = int(time.time() - t_start)

			ret = c.get_balance() # account_index=0, address_indices=[0,1]

			from mmgen.obj import XMRAmt
			bals[fn] = tuple([XMRAmt(ret[k],from_unit='min_coin_unit') for k in ('balance','unlocked_balance')])

			if opt.verbose:
				pp_msg(ret)
			else:
				msg('  Balance: {} Unlocked balance: {}'.format(*[b.hl() for b in bals[fn]]))

			msg('  Wallet height: {}'.format(c.get_height()['height']))
			msg('  Sync time: {:02}:{:02}'.format(t_elapsed//60,t_elapsed%60))

			c.close_wallet()
			return True

		def process_wallets():
			m =   { 'create': ('Creat','Generat',create,False),
					'sync':   ('Sync', 'Sync',   sync,  True) }
			opt.accept_defaults = opt.accept_defaults or m[op][3]
			from mmgen.protocol import init_coin
			init_coin('xmr')
			from mmgen.addr import AddrList
			al = KeyAddrList(infile)
			data = [d for d in al.data if addrs == '' or d.idx in AddrIdxList(addrs)]
			dl = len(data)
			assert dl,"No addresses in addrfile within range '{}'".format(addrs)
			gmsg('\n{}ing {} wallet{}'.format(m[op][0],dl,suf(dl)))

			from mmgen.daemon import MoneroWalletDaemon
			wd = MoneroWalletDaemon(opt.outdir or '.',test_suite=g.test_suite)
			wd.restart()

			from mmgen.rpc import MoneroWalletRPCConnection
			c = MoneroWalletRPCConnection(
				g.monero_wallet_rpc_host,
				wd.rpc_port,
				g.monero_wallet_rpc_user,
				g.monero_wallet_rpc_password)

			wallets_processed = 0
			for n,d in enumerate(data): # [d.sec,d.wallet_passwd,d.viewkey,d.addr]
				fn = os.path.join(
					opt.outdir or '.','{}-{}-MoneroWallet{}'.format(
						al.al_id.sid,
						d.idx,
						'-α' if g.debug_utf8 else ''))

				info = '\n{}ing wallet {}/{} ({})'.format(m[op][1],n+1,dl,fn)
				wallets_processed += m[op][2](n,d,fn,c,info)

			wd.stop()
			gmsg('\n{} wallet{} {}ed'.format(wallets_processed,suf(wallets_processed),m[op][0].lower()))

			if wallets_processed and op == 'sync':
				col1_w = max(map(len,bals)) + 1
				fs = '{:%s} {} {}' % col1_w
				msg('\n'+fs.format('Wallet','Balance           ','Unlocked Balance  '))
				from mmgen.obj import XMRAmt
				tbals = [XMRAmt('0'),XMRAmt('0')]
				for bal in bals:
					for i in (0,1): tbals[i] += bals[bal][i]
					msg(fs.format(bal+':',*[XMRAmt(b).fmt(fs='5.12',color=True) for b in bals[bal]]))
				msg(fs.format('-'*col1_w,'-'*18,'-'*18))
				msg(fs.format('TOTAL:',*[XMRAmt(b).fmt(fs='5.12',color=True) for b in tbals]))

		if blockheight < 0:
			blockheight = 0 # TODO: handle the non-zero case

		from collections import OrderedDict
		bals = OrderedDict() # locked,unlocked

		try:
			process_wallets()
		except KeyboardInterrupt:
			rdie(1,'\nUser interrupt\n')
		except EOFError:
			rdie(2,'\nEnd of file\n')
		except Exception as e:
			try:
				die(1,'Error: {}'.format(e.args[0]))
			except:
				rdie(1,'Error: {!r}'.format(e.args[0]))

		return True

class MMGenToolCmd(
		MMGenToolCmdMisc,
		MMGenToolCmdUtil,
		MMGenToolCmdCoin,
		MMGenToolCmdMnemonic,
		MMGenToolCmdFile,
		MMGenToolCmdFileCrypt,
		MMGenToolCmdFileUtil,
		MMGenToolCmdWallet,
		MMGenToolCmdRPC,
		MMGenToolCmdMonero,
	): pass

class tool_api(
		MMGenToolCmdUtil,
		MMGenToolCmdCoin,
		MMGenToolCmdMnemonic,
	):
	"""
	API providing access to a subset of methods from the mmgen.tool module

	Example:
		from mmgen.tool import tool_api
		tool = tool_api()

		# Set the coin and network:
		tool.init_coin('btc','mainnet')

		# Print available address types:
		tool.print_addrtypes()

		# Set the address type:
		tool.addrtype = 'segwit'

		# Disable user entropy gathering (optional, reduces security):
		tool.usr_randchars = 0

		# Generate a random BTC segwit keypair:
		wif,addr = tool.randpair()

		# Set coin, network and address type:
		tool.init_coin('ltc','testnet')
		tool.addrtype = 'bech32'

		# Generate a random LTC testnet Bech32 keypair:
		wif,addr = tool.randpair()
	"""

	def __init__(self):
		"""
		Initializer - takes no arguments
		"""
		if not hasattr(opt,'version'):
			opts.init({'text': { 'desc': '', 'usage':'', 'options':'' }})
		opt.use_old_ed25519 = None
		opt.type = None

	def init_coin(self,coinsym,network):
		"""
		Initialize a coin/network pair
		Valid choices for coins: one of the symbols returned by the 'coins' attribute
		Valid choices for network: 'mainnet','testnet','regtest'
		"""
		from mmgen.protocol import init_coin,init_genonly_altcoins
		altcoin_trust_level = init_genonly_altcoins(coinsym)
		warn_altcoins(coinsym,altcoin_trust_level)
		if network == 'regtest':
			g.regtest = True
		return init_coin(coinsym,{'mainnet':False,'testnet':True,'regtest':True}[network])

	@property
	def coins(self):
		"""The available coins"""
		from mmgen.protocol import CoinProtocol
		from mmgen.altcoin import CoinInfo
		return sorted(set(CoinProtocol.list_coins() + [c.symbol for c in CoinInfo.get_supported_coins(g.network)]))

	@property
	def coin(self):
		"""The currently configured coin"""
		return g.coin

	@property
	def network(self):
		"""The currently configured network"""
		if g.network == 'testnet':
			return ('testnet','regtest')[g.regtest]
		else:
			return g.network

	@property
	def addrtypes(self):
		"""
		The available address types for current coin/network pair.  The
		first-listed is the default
		"""
		return [MMGenAddrType(t).name for t in g.proto.mmtypes]

	def print_addrtypes(self):
		"""
		Print the available address types for current coin/network pair along with
		a description.  The first-listed is the default
		"""
		for t in [MMGenAddrType(s) for s in g.proto.mmtypes]:
			print('{:<12} - {}'.format(t.name,t.desc))

	@property
	def addrtype(self):
		"""The currently configured address type (is assignable)"""
		return opt.type

	@addrtype.setter
	def addrtype(self,val):
		opt.type = val

	@property
	def usr_randchars(self):
		"""
		The number of keystrokes of entropy to be gathered from the user.
		Setting to zero disables user entropy gathering.
		"""
		return opt.usr_randchars

	@usr_randchars.setter
	def usr_randchars(self,val):
		opt.usr_randchars = val
