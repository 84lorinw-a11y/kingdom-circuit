"""A source event title must never masquerade as a venue in another surface."""
import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import build_seo_site as seo
from show_information_model import normalize
from mobile_discovery import Document
ROOT=Path(__file__).resolve().parents[1]

class VenuePresentationTests(unittest.TestCase):
    def cases(self):
        base={'id':'source:1','title':'RWG TOUR 2026','startDate':'2026-11-13','artists':['Example'], 'city':'Lake Hiawatha','state':'NJ','country':'US'}
        return [(dict(base,venue=v),'Venue not confirmed') for v in ('RWG TOUR 2026',' rwg  tour 2026 ','TBD','Venue to be announced','Venue not provided','')] + [
            (dict(base,venue='Promoter event',unconfirmedVenueValue='Promoter event'),'Venue not confirmed'),
            (dict(base,venue='Real Venue & Chapel'),'Real Venue & Chapel'),
            (dict(base,venue='Updated Venue',unconfirmedVenueValue='Old Venue'),'Updated Venue')]
    def test_python_cards_and_detail_model_agree_without_mutating_source(self):
        for event,expected in self.cases():
            before=copy.deepcopy(event)
            doc=Document(seo.event_card(event,[]))
            label=doc.one(lambda n:n.tag=='dt' and doc.text(n)=='Venue')
            dd=next(n for n in doc.nodes if n.tag=='dd' and label.end<=n.start)
            self.assertEqual(doc.text(dd),expected)
            self.assertEqual(normalize(event)['venueLabel'],expected)
            self.assertEqual(event,before)
    def test_browser_renderers_use_same_honest_venue_rules(self):
        node=shutil.which('node')
        self.assertIsNotNone(node,'Node is required for production rendering parity')
        source=(ROOT/'app.js').read_text()
        helper=source.split('function eventVenueLabel(event) {',1)[1].split('function eventCard(event) {',1)[0]
        script='function eventVenueLabel(event) {'+helper+'\nconsole.log(JSON.stringify('+json.dumps([e for e,_ in self.cases()])+'.map(eventVenueLabel)));'
        actual=json.loads(subprocess.check_output([node,'-e',script],text=True))
        self.assertEqual(actual,[expected for _,expected in self.cases()])
        self.assertIn('esc(eventVenueLabel(event))',source.split('function eventCard(event) {')[1].split('function filterEvents')[0])
        self.assertIn('esc(eventVenueLabel(event))',source.split('function renderEventDetail() {')[1].split('function ensureCanonical')[0])

if __name__=='__main__':unittest.main()
