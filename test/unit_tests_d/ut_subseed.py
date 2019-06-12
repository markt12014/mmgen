#!/usr/bin/env python3
"""
test/unit_tests_d/ut_subseed: subseed unit test for the MMGen suite
"""

from mmgen.common import *

class unit_test(object):

	def run_test(self,name):
		from mmgen.seed import Seed
		from mmgen.obj import SubSeedIdxRange

		def basic_ops():
			msg_r('Testing basic ops...')
			for a,b,c,d,e,f,h in (
					(8,'4710FBF0','0C1B0615','803B165C','2669AC64',256,'10L'),
					(6,'9D07ABBD','EBA9C33F','20787E6A','192E2AA2',192,'10L'),
					(4,'43670520','04A4CCB3','B5F21D7B','C1934CFF',128,'10L'),
				):

				seed_bin = bytes.fromhex('deadbeef' * a)
				seed = Seed(seed_bin)
				assert seed.sid == b, seed.sid

				subseed = seed.subseed('2s')
				assert subseed.sid == c, subseed.sid

				subseed = seed.subseed('3')
				assert subseed.sid == d, subseed.sid

				subseed = seed.subseed_by_seed_id(e)
				assert subseed.bitlen == f, subseed.bitlen
				assert subseed.sid == e, subseed.sid
				assert subseed.idx == 10, subseed.idx
				assert subseed.ss_idx == h, subseed.ss_idx

				seed2 = Seed(seed_bin)
				ss2_list = seed2.subseeds

				seed2.subseeds._generate(1)
				assert len(ss2_list) == 1, len(ss2_list)

				seed2.subseeds._generate(1) # do nothing
				seed2.subseeds._generate(2) # append one item

				seed2.subseeds._generate(5)
				assert len(ss2_list) == 5, len(ss2_list)

				seed2.subseeds._generate(3) # do nothing
				assert len(ss2_list) == 5, len(ss2_list)

				seed2.subseeds._generate(10)
				assert len(ss2_list) == 10, len(ss2_list)

				assert seed.pformat() == seed2.pformat()

				s = seed.subseeds.format(1,g.subseeds)
				s_lines = s.strip().split('\n')
				assert len(s_lines) == g.subseeds + 4, s

				a = seed.subseed('2L').sid
				b = [e for e in s_lines if ' 2L:' in e][0].strip().split()[1]
				assert a == b, b

				c = seed.subseed('2').sid
				assert c == a, c

				a = seed.subseed('5S').sid
				b = [e for e in s_lines if ' 5S:' in e][0].strip().split()[3]
				assert a == b, b

				s = seed.subseeds.format(g.subseeds+1,g.subseeds+2)
				s_lines = s.strip().split('\n')
				assert len(s_lines) == 6, s

				ss_idx = str(g.subseeds+2) + 'S'
				a = seed.subseed(ss_idx).sid
				b = [e for e in s_lines if ' {}:'.format(ss_idx) in e][0].strip().split()[3]
				assert a == b, b

				s = seed.subseeds.format(1,10)
				s_lines = s.strip().split('\n')
				assert len(s_lines) == 14, s

				vmsg_r('\n{}'.format(s))

			msg('OK')

		def defaults_and_limits():
			msg_r('Testing defaults and limits...')

			seed_bin = bytes.fromhex('deadbeef' * 8)
			seed = Seed(seed_bin)
			seed.subseeds._generate()
			ss = seed.subseeds
			assert len(ss.data['long']) == len(ss.data['short']), len(ss.data['short'])
			assert len(ss) == g.subseeds, len(ss)

			seed = Seed(seed_bin)
			seed.subseed_by_seed_id('EEEEEEEE')
			ss = seed.subseeds
			assert len(ss.data['long']) == len(ss.data['short']), len(ss.data['short'])
			assert len(ss) == g.subseeds, len(ss)

			seed = Seed(seed_bin)
			subseed = seed.subseed_by_seed_id('803B165C')
			assert len(ss.data['long']) == len(ss.data['short']), len(ss.data['short'])
			assert subseed.sid == '803B165C', subseed.sid
			assert subseed.idx == 3, subseed.idx

			seed = Seed(seed_bin)
			subseed = seed.subseed_by_seed_id('803B165C',last_idx=1)
			assert len(ss.data['long']) == len(ss.data['short']), len(ss.data['short'])
			assert subseed == None, subseed

			r = SubSeedIdxRange('1-5')
			r2 = SubSeedIdxRange(1,5)
			assert r2 == r, r2
			assert r == (r.first,r.last), r
			assert r.first == 1, r.first
			assert r.last == 5, r.last
			assert r.items == [1,2,3,4,5], r.items
			assert list(r.iterate()) == r.items, list(r.iterate())

			r = SubSeedIdxRange('22')
			r2 = SubSeedIdxRange(22,22)
			assert r2 == r, r2
			assert r == (r.first,r.last), r
			assert r.first == 22, r.first
			assert r.last == 22, r.last
			assert r.items == [22], r
			assert list(r.iterate()) == r.items, list(r.iterate())

			r = SubSeedIdxRange('3-3')
			assert r.items == [3], r.items

			r = SubSeedIdxRange('{}-{}'.format(g.subseeds-1,g.subseeds))
			assert r.items == [g.subseeds-1,g.subseeds], r.items

			for n,e in enumerate(SubSeedIdxRange('1-5').iterate(),1):
				assert n == e, e

			assert n == 5, n

			msg('OK')

		def collisions():
			ss_count,ltr,last_sid,collisions_chk = (
				(SubSeedIdxRange.max_idx,'S','2788F26B',470),
				(49509,'L','8D1FE500',2)
			)[bool(opt.fast)]

			last_idx = str(ss_count) + ltr

			msg_r('Testing Seed ID collisions ({} subseed pairs)...'.format(ss_count))

			seed_bin = bytes.fromhex('12abcdef' * 8)
			seed = Seed(seed_bin)

			seed.subseeds._generate(ss_count)
			ss = seed.subseeds

			assert seed.subseed(last_idx).sid == last_sid, seed.subseed(last_idx).sid

			for sid in ss.data['long']:
				# msg(sid)
				assert sid not in ss.data['short']

			collisions = 0
			for k in ('short','long'):
				for sid in ss.data[k]:
					collisions += ss.data[k][sid][1]

			assert collisions == collisions_chk, collisions
			vmsg_r('\n{} collisions, last_sid {}'.format(collisions,last_sid))
			msg('OK')

		basic_ops()
		defaults_and_limits()
		collisions()

		return True
