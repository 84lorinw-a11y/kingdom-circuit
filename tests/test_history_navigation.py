import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import history_navigation as hn
import url_continuity as uc

class HistoryNavigationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.site=self.root/'site';self.site.mkdir()
        uc.save(self.root/'config/artists.json',[{'name':'Anike','enabled':True}])
        self.page('/shows/','<article data-event-card><h3><a href="/event/current/">Current</a></h3></article>')
        self.page('/event/current/','Current facts')
        self.page('/artists/anike/','Artist')
        self.page('/shows/texas/','Texas')
        self.page('/shows/dallas-texas/','Dallas')
        self.page('/shows/october-2026/','Month')
    def page(self,path,body,robots='index,follow'):
        f=uc.target_file(self.site,path);f.parent.mkdir(parents=True,exist_ok=True)
        f.write_text(f'<html><head><meta name="robots" content="{robots}"><link rel="canonical" href="{uc.ORIGIN+path}"><title>Example</title></head><body><main><h1>Example</h1>{body}</main></body></html>');return f
    def test_history_is_reachable_without_readding_it_to_current_shows(self):
        event={'id':'old','title':'Past show','startDate':'2026-10-01','artists':['Anike','Unknown'],'city':'Dallas','state':'TX'}
        self.page('/event/retained/','This date has passed. Original facts')
        state={'events':{'old':{'path':'/event/retained/','event':event}}}
        current=(self.site/'event/current/index.html').read_bytes()
        hn.connect(self.root,self.site,state,{'old':event},'2026-11-16')
        old=(self.site/'event/retained/index.html').read_text(); archive=(self.site/'shows/archive/index.html').read_text()
        for link in ['/artists/anike/','/shows/texas/','/shows/dallas-texas/','/shows/archive/']:self.assertIn(f'href="{link}"',old)
        self.assertNotIn('/artists/unknown/',old)
        self.assertIn('/event/retained/',archive);self.assertIn('/shows/october-2026/',archive)
        self.assertNotIn('/event/current/',archive)
        self.assertEqual(current,(self.site/'event/current/index.html').read_bytes())
        first={str(f.relative_to(self.site)):f.read_bytes() for f in self.site.rglob('*.html')}
        hn.connect(self.root,self.site,state,{'old':event},'2026-11-16')
        self.assertEqual(first,{str(f.relative_to(self.site)):f.read_bytes() for f in self.site.rglob('*.html')})
    def test_private_and_noncanonical_pages_are_not_promoted(self):
        self.page('/event/private/','Private event. Not open to the public.')
        self.page('/event/review/','Under review','noindex,follow')
        alias=self.page('/event/alias/','Alias');alias.write_text(uc.forwarding_page('/event/current/'))
        hn.connect(self.root,self.site,{'events':{}},{},'2026-11-16')
        archive=(self.site/'shows/archive/index.html').read_text()
        for path in ['/event/private/','/event/review/','/event/alias/']:self.assertNotIn(path,archive)
    def test_missing_location_pages_are_never_invented(self):
        event={'id':'old','artists':['Anike'],'city':'Unknown City','state':'TX','locationUnconfirmed':True}
        self.page('/event/retained/','Previously listed')
        hn.connect(self.root,self.site,{'events':{'old':{'path':'/event/retained/','event':event}}},{},'2026-11-16')
        text=(self.site/'event/retained/index.html').read_text()
        self.assertNotIn('unknown-city',text);self.assertNotIn('href="/shows/texas/"',text)
if __name__=='__main__':unittest.main()
