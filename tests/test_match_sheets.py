import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from collect import parse_fixture_tables
from import_match_sheets import import_reviews


class MatchSheetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'sheet.jpg'
        self.path.write_bytes(b'reviewed public sheet')
        self.url = 'https://www.pofepa.gr/test-sheet.jpg'
        self.source = {'id':'s-sheet','url':self.url,'sha256':hashlib.sha256(self.path.read_bytes()).hexdigest()}
        self.data = {'schema':1,'sources':[self.source], 'players':[{'id':f'p-{i}','name':f'PLAYER {i}','registration':str(i)} for i in range(1,5)],
                     'clubs':[{'id':'c-a','name':'A'},{'id':'c-b','name':'B'}],
                     'events':[{'id':'e-fixture','name':'LEAGUE','kind':'fixtures','season':'2026-2027','sources':['s-sheet']}],
                     'fixtures':[{'id':'f-1','event':'e-fixture','source':'s-sheet','sheet_url':self.url,'home':'A','away':'B','score':[2,0],'status':'reported','clubs':['c-a','c-b']}],
                     'matches':[], 'snapshots':[{'id':'ranking','source':'s-sheet','period':'2026-10','list':'ΓΕΝΙΚΟΣ','rows':[[f'p-{i}',i,100,'c-a' if i<3 else 'c-b','ANE',i] for i in range(1,5)]}],
                     'coverage':{'as_of':'2026-11-26','players':4,'fixtures':1,'events':1,'matches':0}}
        self.review = {'sha256':self.source['sha256'],'fixture':'f-1','team_score':[2,0],'date':'2026-11-20',
                       'players':{str(i):{'id':f'p-{i}','label':f'PLAYER {i}','registration':str(i)} for i in range(1,5)},
                       'rows':[{'row':1,'players':['1','3'],'score':[3,1]},{'row':2,'players':['2','4'],'score':[3,0],'status':'walkover'}]}
        test = self
        class Cache:
            sources = {'s-sheet':test.source}
            def get(self,url,filename=None): return 's-sheet',test.path
        self.cache = Cache()

    def run_import(self):
        return import_reviews(self.data,self.cache,{self.url:self.review})

    def test_only_played_singles_enter_player_history(self):
        result=self.run_import()
        self.assertEqual(len(result['matches']),1)
        self.assertEqual(result['matches'][0]['score'],[3,1])
        self.assertEqual(result['fixtures'][0]['rubbers'][1]['status'],'walkover')
        self.assertEqual(result['coverage']['match_sheets']['excluded_walkovers'],1)

    def test_replay_is_idempotent(self):
        self.run_import()
        before=copy.deepcopy(self.data)
        self.run_import()
        self.assertEqual(before,self.data)

    def test_absent_roster_slot_is_allowed_only_for_a_walkover(self):
        self.review['players']['4']={'label':'Absent player'}
        self.run_import()
        self.assertEqual(len(self.data['matches']),1)
        self.assertEqual(self.data['fixtures'][0]['rubbers'][1]['names'][1],'Absent player')
        self.review['rows'][1]['status']='played'
        with self.assertRaisesRegex(ValueError,'Absent participant'):self.run_import()

    def test_reversed_existing_result_is_corroborated_once(self):
        self.run_import()
        m=self.data['matches'][0]
        m['p1'],m['p2']=m['p2'],m['p1'];m['score'].reverse()
        m['origin']='workbook';m['evidence']=[{'source':'s-sheet','row':50,'region':'national'}]
        self.run_import()
        self.assertEqual(len(self.data['matches']),1)
        self.assertEqual(self.data['coverage']['match_sheets']['corroborated'],1)
        self.assertEqual(m['document_evidence'][0]['fixture'],'f-1')

    def test_conflicting_score_does_not_create_a_second_match(self):
        self.run_import();self.data['matches'][0]['score']=[3,2]
        with self.assertRaisesRegex(ValueError,'Ambiguous existing result'):self.run_import()

    def test_changed_source_and_registration_fail_closed(self):
        self.path.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'sheet changed'):self.run_import()
        self.path.write_bytes(b'reviewed public sheet');self.review['players']['1']['registration']='999'
        with self.assertRaisesRegex(ValueError,'registration mismatch'):self.run_import()

    def test_team_total_must_reconcile(self):
        self.review['rows'][0]['score']=[1,3]
        with self.assertRaisesRegex(ValueError,'totals disagree'):self.run_import()

    def test_prior_result_can_support_an_existing_provisional_identity(self):
        self.run_import()
        prior=copy.deepcopy(self.data['matches'][0])
        prior.update(id='m-prior', date='2026-10-20', origin='workbook')
        self.data['matches']=[prior]
        self.data['snapshots'][0]['rows']=self.data['snapshots'][0]['rows'][1:]
        self.data['players'][0].update(club='c-a', provisional=True)
        self.review['players']['1'].pop('registration')
        self.review['players']['1']['identity_match']='m-prior'
        self.run_import()
        self.assertEqual(len(self.data['matches']),2)
        self.assertTrue(self.data['players'][0]['provisional'])
        self.assertEqual(self.data['matches'][0]['p1'],'p-1')
        self.review['players']['1']['identity_match']='missing'
        with self.assertRaisesRegex(ValueError,'prior-result identity'):self.run_import()

    def test_duplicate_rows_and_identical_participants_fail_closed(self):
        self.review['rows'][1]['row']=1
        with self.assertRaisesRegex(ValueError,'repeated match-sheet row'):self.run_import()
        self.review['rows'][1]['row']=2
        self.review['rows'][0]['players']=['1','1']
        with self.assertRaisesRegex(ValueError,'Identical match-sheet participants'):self.run_import()

    def test_held_sheet_is_visible_but_does_not_import_matches(self):
        issue={'sha256':self.source['sha256'],'fixture':'f-1','reason':'Missing actual date'}
        # Keep a pre-existing result so ordinary dataset date bounds remain defined.
        self.run_import()
        count=len(self.data['matches'])
        import_reviews(self.data,self.cache,{}, {self.url:issue})
        c=self.data['coverage']['match_sheets']
        self.assertEqual((c['reviewed'],c['held'],c['pending']),(1,1,0))
        self.assertEqual(c['imported_sheets'],0)
        self.assertEqual(len(self.data['matches']),count)
        with self.assertRaisesRegex(ValueError,'both imported and held'):
            import_reviews(self.data,self.cache,{self.url:self.review},{self.url:issue})

    def test_historical_score_links_preserve_blank_rows_and_nested_breaks(self):
        html='<h2>Round</h2><table><tr><td>A<br>B<br>C</td><td>-<br>-<br>-</td><td>X<br>Y<br>Z</td><td><a href="one.jpg">5-1       </a><br><a href="two.jpg">2-5<br></a> -</td></tr></table>'
        rows=parse_fixture_tables(html,'s','https://www.pofepa.gr/test.html','e')
        self.assertEqual([r['score'] for r in rows],[[5,1],[2,5],None])
        self.assertEqual([r['sheet_url'] for r in rows],['https://www.pofepa.gr/one.jpg','https://www.pofepa.gr/two.jpg',''])


if __name__=='__main__':unittest.main()
