import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

import pymupdf

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from collect import uid
from dataset import load
from pdf_results import extract_pdf, team_name
from reviewed_documents import extract_document, fixture_digest


class DocumentParserTests(unittest.TestCase):
    def pdf(self, write):
        directory=tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path=Path(directory.name)/'fixture.pdf'
        document=pymupdf.open()
        page=document.new_page(width=500,height=500)
        write(page)
        document.save(path)
        document.close()
        return path

    def test_winner_and_preliminary_slot_have_different_score_orientation(self):
        def draw(page):
            for offset,winner,score in [(0,'AWAY','4-1'),(160,'N1','0-4')]:
                for text,x,y in [('HOME',40,90),('AWAY',40,150),(winner,230,120),(score,260,134)]:
                    page.insert_text((x,y+offset),text,fontsize=10)
                for a,b in [((30,94),(200,94)),((30,154),(200,154)),((200,94),(200,124)),((200,124),(200,154)),((200,124),(350,124))]:
                    page.draw_line((a[0],a[1]+offset),(b[0],b[1]+offset))
        fixtures,_=extract_pdf(self.pdf(draw),'s-1','e-1',uid)
        self.assertEqual([(f['home'],f['away'],f['score']) for f in fixtures],[('HOME','AWAY',[1,4]),('HOME','AWAY',[0,4])])

    def test_bracket_team_hyphen_does_not_create_an_extra_match(self):
        def draw(page):
            page.insert_text((30,100),'22 CLUB NORTH - SOUTH              4-1',fontsize=10)
        fixtures,_=extract_pdf(self.pdf(draw),'s-1','e-1',uid)
        self.assertEqual(fixtures,[])

    def test_match_list_and_mirrored_grid_are_counted_once(self):
        def draw(page):
            xs=[30,60,220,260,300]
            ys=[50,75,100,125]
            for x in xs:page.draw_line((x,ys[0]),(x,ys[-1]))
            for y in ys:page.draw_line((xs[0],y),(xs[-1],y))
            for ri,row in enumerate([['A/A','TEAMS','1','2'],['1','HOME','','4-1'],['2','AWAY','1-4','']]):
                for ci,cell in enumerate(row):page.insert_text((xs[ci]+4,ys[ri]+17),cell,fontsize=9)
            page.insert_text((30,180),'1-2  HOME - AWAY                   4-1',fontsize=10)
        fixtures,_=extract_pdf(self.pdf(draw),'s-1','e-1',uid)
        self.assertEqual(len(fixtures),1)
        self.assertEqual(fixtures[0]['score'],[4,1])

    def test_team_initials_survive_forfeit_cleanup(self):
        self.assertEqual(team_name('ΗΡΑΚΛΕΙΟ Ο.Α.Α.'),'ΗΡΑΚΛΕΙΟ Ο.Α.Α.')
        self.assertEqual(team_name('CLUB (α.α.)'),'CLUB')
        self.assertEqual(team_name('(Δ2-7) CLUB'),'CLUB')

    def test_transcription_is_bound_to_reviewed_source_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'sheet.jpg';path.write_bytes(b'changed')
            review={'url':'https://www.pofepa.gr/sheet.jpg','sha256':hashlib.sha256(b'original').hexdigest()}
            with self.assertRaisesRegex(ValueError,'changed since visual review'):
                extract_document(path,uid('s-',review['url']),'e-1',uid,[review])


class ReviewedArchiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.data=load()

    def test_every_reviewed_document_has_a_source_and_record_count(self):
        reviews=self.data['coverage']['document_reviews']
        self.assertEqual(len(reviews),131)
        self.assertEqual(sum(r['review_status']=='standings_only' for r in reviews),6)
        for r in reviews:
            fixtures=[f for f in self.data['fixtures'] if f['source']==r['source']]
            self.assertEqual(len(fixtures),r['fixtures'])
            for f in fixtures:
                self.assertNotIn('\u03a2',f['home']+f['away'])
                self.assertTrue(f.get('page'))

    def test_all_reviewed_names_and_scores_match_the_pinned_manifest(self):
        for review in json.loads((ROOT/'data/document-reviews.json').read_text()):
            fixtures=[f for f in self.data['fixtures'] if f['source']==uid('s-',review['url'])]
            self.assertEqual(len(fixtures),review['expected_fixtures'])
            self.assertEqual(fixture_digest(fixtures),review['fixture_digest'])

    def test_repeated_rounds_survive_but_repeated_page_does_not(self):
        def rows(suffix):
            sid=next(s['id'] for s in self.data['sources'] if s['url'].endswith(suffix))
            return [f for f in self.data['fixtures'] if f['source']==sid]
        self.assertEqual(len(rows('CUP-PELLOPONHSOS-2022-2023.pdf')),14)
        self.assertEqual(len(rows('CUP-IND-ATTIKH-2024-2025.pdf')),48)
        repeated=[f for f in rows('KYPELLO-DYTELL.pdf') if {f['home'],f['away']}=={'ΦΑΕΘΩΝ','ΦΟΙΝΙΚΑΣ 2010'}]
        self.assertEqual(len(repeated),2)
        self.assertEqual(sum(bool(f.get('placement')) for f in repeated),1)

    def test_fixture_names_determine_score_order_not_draw_slot_numbers(self):
        sid=next(s['id'] for s in self.data['sources'] if s['url'].endswith('CUP-IND-ATTIKH-2024-2025.pdf'))
        rows=[f for f in self.data['fixtures'] if f['source']==sid and {f['home'],f['away']}=={'NOSPINATALL','SWORD'}]
        self.assertEqual(len(rows),1)
        self.assertEqual(dict(zip([rows[0]['home'],rows[0]['away']],rows[0]['score'])),{'SWORD':4,'NOSPINATALL':2})

    def test_image_singles_corroborate_existing_matches(self):
        matches={m['id']:m for m in self.data['matches']}
        image_fixtures=[f for f in self.data['fixtures'] if f.get('rubbers')]
        self.assertEqual(len(image_fixtures),1)
        fixture=image_fixtures[0]
        self.assertEqual(fixture['score'],[0,4])
        self.assertEqual([r['kind'] for r in fixture['rubbers']],['singles']*3+['doubles'])
        for rubber in fixture['rubbers'][:3]:
            match=matches[rubber['match']]
            self.assertEqual(match['date'],fixture['date'])
            self.assertEqual(match['score'],rubber['score'])
            self.assertEqual(match['document_evidence'][0]['source'],fixture['source'])


if __name__=='__main__':unittest.main()
