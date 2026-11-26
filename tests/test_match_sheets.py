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

    def test_whole_team_no_show_creates_no_individual_results(self):
        self.run_import()
        original_matches=copy.deepcopy(self.data['matches'])
        self.data['fixtures'][0]['score']=[5,0]
        self.review.update(status='team_walkover', team_score=[5,0], players={}, rows=[],
                           notes='Away team did not attend; all rubber fields are blank.')
        self.run_import()
        self.assertEqual(self.data['matches'],original_matches)
        self.assertEqual(self.data['fixtures'][0]['rubbers'],[])
        self.assertEqual(self.data['fixtures'][0]['match_sheet_status'],'team_walkover')
        coverage=self.data['coverage']['match_sheets']
        self.assertEqual((coverage['imported'],coverage['corroborated'],coverage['excluded_walkovers']),(0,0,0))
        self.assertEqual(coverage['excluded_team_walkovers'],1)
        before=copy.deepcopy(self.data)
        self.run_import()
        self.assertEqual(before,self.data)

    def test_whole_team_no_show_rejects_rubbers_or_non_walkover_total(self):
        self.review['status']='team_walkover'
        with self.assertRaisesRegex(ValueError,'Invalid whole-team walkover'):self.run_import()
        self.review.update(players={},rows=[],notes='No attendance')
        with self.assertRaisesRegex(ValueError,'Invalid whole-team walkover'):self.run_import()

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

    def test_walkover_cannot_silently_leave_an_existing_played_result(self):
        self.review['rows'][1]['status']='played'
        self.run_import()
        self.review['rows'][1]['status']='walkover'
        with self.assertRaisesRegex(ValueError,'Existing played result conflicts with walkover'):
            self.run_import()

    def test_changed_source_and_registration_fail_closed(self):
        self.path.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'sheet changed'):self.run_import()
        self.path.write_bytes(b'reviewed public sheet');self.review['players']['1']['registration']='999'
        with self.assertRaisesRegex(ValueError,'registration mismatch'):self.run_import()

    def test_recovered_source_retains_original_fixture_link_and_actual_document(self):
        from unittest.mock import patch
        recovered='https://www.pofepa.gr/recovered-sheet.jpg'
        self.review['document_url']=recovered
        with self.assertRaisesRegex(ValueError,'recovered-source explanation'):self.run_import()
        self.review['notes']='Original link is broken; this separately linked sheet matches teams, date and score.'
        self.source['url']=recovered
        with patch.object(self.cache,'get',wraps=self.cache.get) as get:
            self.run_import()
            get.assert_called_once_with(recovered)
        self.assertEqual(self.data['fixtures'][0]['sheet_url'],self.url)
        report=self.data['coverage']['match_sheets']['reviews'][0]
        self.assertEqual((report['url'],report['linked_url']),(recovered,self.url))

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

    def prepare_score_correction(self):
        self.run_import()
        match = self.data['matches'][0]
        match.update(origin='workbook', score=[3,2])
        self.data['fixtures'][0].pop('rubbers')
        before = {k:copy.deepcopy(match[k]) for k in ('date','p1','p2','score')}
        after = {**before, 'score':[3,1]}
        self.review['corrections'] = [{'match':match['id'], 'row':1,
            'before':before, 'after':after, 'reason':'Explicit total and complete games agree.'}]
        return match, copy.deepcopy(match)

    def test_source_bound_score_correction_retains_original_and_replays(self):
        match, original = self.prepare_score_correction()
        self.run_import()
        self.assertEqual(match['score'],[3,1])
        self.assertEqual(match['sheet_corrections'][0]['match'],original)
        before = copy.deepcopy(self.data)
        self.run_import()
        self.assertEqual(before,self.data)
        self.assertEqual(len(self.data['matches']),1)

    def test_correction_rejects_stale_state_wrong_source_and_wrong_row_result(self):
        match, original = self.prepare_score_correction()
        match['score']=[3,0]
        with self.assertRaisesRegex(ValueError,'precondition'):self.run_import()
        match['score']=[3,2]
        self.review['corrections'][0]['after']['score']=[3,0]
        with self.assertRaisesRegex(ValueError,'score mismatch'):self.run_import()
        self.review['corrections'][0]['after']['score']=[3,1]
        self.path.write_bytes(b'different sheet')
        with self.assertRaisesRegex(ValueError,'Correction source changed'):self.run_import()

    def test_opponent_correction_updates_name_and_preserves_original_identity(self):
        self.run_import()
        match=self.data['matches'][0]
        match.update(origin='workbook')
        self.data['fixtures'][0].pop('rubbers')
        before={k:copy.deepcopy(match[k]) for k in ('date','p1','p2','score')}
        self.review['rows'][0]['players']=['1','4']
        self.review['corrections']=[{'match':match['id'],'row':1,'before':before,
            'after':{**before,'p2':'p-4'},'reason':'Explicit substitute on the signed sheet.'}]
        self.run_import()
        self.assertEqual((match['p2'],match['names'][1]),('p-4','PLAYER 4'))
        self.assertEqual(match['sheet_corrections'][0]['match']['p2'],'p-3')
        self.assertEqual(match['identity'][1],'reviewed_sheet_name_and_team')

    def test_correction_cannot_create_duplicate_result(self):
        match, original=self.prepare_score_correction()
        duplicate=copy.deepcopy(match);duplicate.update(id='m-existing',score=[3,1])
        self.data['matches'].append(duplicate)
        with self.assertRaisesRegex(ValueError,'collide'):self.run_import()

    def test_explicit_walkover_correction_excludes_only_named_existing_match(self):
        self.review['rows'][1]['status']='played'
        self.run_import()
        match=next(m for m in self.data['matches'] if m['row']==2)
        match['origin']='workbook'
        self.data['fixtures'][0].pop('rubbers')
        self.review['rows'][1]['status']='walkover'
        self.review['corrections']=[{'match':match['id'],'row':2,
            'action':'exclude_walkover','before':{k:copy.deepcopy(match[k]) for k in ('date','p1','p2','score')},
            'reason':'Both names retained but sheet explicitly records no play.'}]
        self.run_import()
        self.assertEqual(len(self.data['matches']),1)
        excluded=self.data['fixtures'][0]['excluded_workbook_results']
        self.assertEqual(excluded[0]['match']['id'],match['id'])
        before=copy.deepcopy(self.data)
        self.run_import()
        self.assertEqual(before,self.data)

    def prepare_same_day_identity(self):
        self.run_import()
        self.data['matches'][0]['origin']='workbook'
        self.data['snapshots'][0]['rows']=self.data['snapshots'][0]['rows'][1:]
        self.data['players'][0].update(club='c-a',provisional=True)
        person=self.review['players']['1']
        person.pop('registration')
        person.update(identity_match=self.data['matches'][0]['id'],identity_basis='same_day_workbook')
        return person

    def test_same_day_provisional_proof_only_attaches_evidence_to_existing_rows(self):
        self.prepare_same_day_identity()
        count=len(self.data['matches'])
        self.run_import()
        self.assertEqual(len(self.data['matches']),count)
        self.assertTrue(self.data['players'][0]['provisional'])
        before=copy.deepcopy(self.data)
        self.run_import()
        self.assertEqual(self.data,before)

    def test_same_day_proof_rejects_new_rows_wrong_club_score_or_duplicate(self):
        self.prepare_same_day_identity()
        good=copy.deepcopy(self.data)
        for change in ('club','score','duplicate','new_row'):
            self.data=copy.deepcopy(good)
            self.review['rows'][1]['status']='walkover'
            if change=='club':self.data['matches'][0]['clubs']=self.data['matches'][0]['clubs'][::-1]
            if change=='score':self.data['matches'][0]['score']=[3,2]
            if change=='duplicate':
                duplicate=copy.deepcopy(self.data['matches'][0]);duplicate['id']='m-duplicate'
                self.data['matches'].append(duplicate)
            if change=='new_row':self.review['rows'][1]['status']='played'
            with self.subTest(change=change), self.assertRaisesRegex(ValueError,'prior-result identity'):
                self.run_import()

    def test_same_day_proof_requires_explicit_opt_in_and_matching_existing_player(self):
        person=self.prepare_same_day_identity()
        person.pop('identity_basis')
        with self.assertRaisesRegex(ValueError,'prior-result identity'):self.run_import()
        person['identity_basis']='same_day_workbook'
        person['identity_match']='missing'
        with self.assertRaisesRegex(ValueError,'prior-result identity'):self.run_import()
        person['identity_match']=self.data['matches'][0]['id']
        self.data['players'][0]['provisional']=False
        with self.assertRaisesRegex(ValueError,'prior-result identity'):self.run_import()

    def test_correction_rejects_result_already_linked_to_a_fixture(self):
        match, original=self.prepare_score_correction()
        self.data['fixtures'][0]['rubbers']=[{'kind':'singles','row':1,'match':match['id'],'score':[3,2],'players':['p-1','p-3']}]
        with self.assertRaisesRegex(ValueError,'already linked'):self.run_import()

    def test_correction_audit_does_not_alias_review_input(self):
        match, original=self.prepare_score_correction()
        self.run_import()
        audit=copy.deepcopy(match['sheet_corrections'])
        self.review['corrections'][0]['before']['score'][1]=0
        self.review['corrections'][0]['after']['score'][1]=2
        self.assertEqual(audit,match['sheet_corrections'])

    def test_unavailable_source_is_distinct_from_reviewed_or_pending(self):
        self.run_import()
        fixture=copy.deepcopy(self.data['fixtures'][0])
        fixture.update(id='f-missing',sheet_url='https://www.pofepa.gr/missing.jpg')
        fixture.pop('rubbers')
        self.data['fixtures'].append(fixture)
        self.data['coverage']['fixtures']=2
        unavailable={fixture['sheet_url']:{'fixture':'f-missing','checked_at':'2026-11-26','http_status':404,'reason':'Source returns404.'}}
        import_reviews(self.data,self.cache,{self.url:self.review},{},unavailable)
        c=self.data['coverage']['match_sheets']
        self.assertEqual((c['linked'],c['reviewed'],c['unavailable'],c['pending']),(2,1,1,0))
        self.assertEqual(c['seasons']['2026-2027']['unavailable'],1)
        self.assertNotIn('sha256',c['unavailable_sources'][0])

    def test_unavailable_source_cannot_also_be_imported(self):
        self.run_import()
        unavailable={self.url:{'fixture':'f-1','checked_at':'2026-11-26','http_status':404,'reason':'Unavailable'}}
        with self.assertRaisesRegex(ValueError,'Invalid unavailable'):
            import_reviews(self.data,self.cache,{self.url:self.review},{},unavailable)

    def test_date_correction_preserves_original_workbook_date(self):
        match, original=self.prepare_score_correction()
        self.review['date']='2026-11-19'
        self.review['corrections'][0]['after']['date']='2026-11-19'
        self.run_import()
        self.assertEqual(match['date'],'2026-11-19')
        self.assertEqual(match['sheet_corrections'][0]['match']['date'],'2026-11-20')
        before=copy.deepcopy(self.data)
        self.run_import()
        self.assertEqual(before,self.data)


if __name__=='__main__':unittest.main()
