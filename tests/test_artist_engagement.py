import sys
import json
import unittest
from tempfile import TemporaryDirectory
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import artist_engagement as fan
from mobile_discovery import Document

class FanEngagement(unittest.TestCase):
    def test_final_discovery_counts_follow_catalog_membership_instead_of_linked_billing(self):
        artists = [{'name': 'Mica', 'href': '/artists/mica/', 'count': 1},
                   {'name': 'Altar Ego', 'href': '/artists/altar-ego/', 'count': 5},
                   {'name': 'No Shows', 'href': '/artists/no-shows/', 'count': 0}]
        text = ('<script type="application/json" id="kc-fan-artists">' + json.dumps(artists) + '</script>'
                '<a class="kc-discovery-artist" href="/artists/mica/"><div><img src="/mica.jpg"></div>'
                '<strong>Mica</strong><span>1 upcoming show</span></a>'
                '<a class="kc-discovery-artist" href="/artists/altar-ego/"><div><img src="/altar.jpg"></div>'
                '<strong>Altar Ego</strong><span>5 upcoming shows</span></a>')
        ctx = {'asOf': '2026-11-08', 'shows': [{'path': '/old/', 'date': '2026-11-07', 'end': '2026-11-07'},
               *[{'path': f'/show/{i}/', 'date': '2026-11-14', 'end': '2026-11-14'} for i in range(6)]],
               'artists': {'mica': {'path': '/artists/mica/', 'shows': ['/old/']},
                           'altar': {'path': '/artists/altar-ego/', 'shows': [f'/show/{i}/' for i in range(6)] + ['/show/0/', '/absent/']},
                           'none': {'path': '/artists/no-shows/', 'shows': []}}}
        output = fan.reconcile_artist_counts(text, ctx)
        doc = Document(output)
        revised = json.loads(doc.text(doc.one(lambda n: n.attrs.get('id') == 'kc-fan-artists')))
        self.assertEqual([a['count'] for a in revised], [0, 6, 0])
        self.assertEqual([len(a['shows']) for a in revised], [0, 6, 0])
        tiles = [n for n in doc.nodes if n.has('kc-discovery-artist')]
        self.assertIn('hidden', tiles[0].attrs)
        self.assertNotIn('hidden', tiles[1].attrs)
        self.assertEqual(doc.text(tiles[1].children[-1]), '6 upcoming shows')
        self.assertEqual([n.attrs['src'] for n in doc.nodes if n.tag == 'img'], ['/mica.jpg', '/altar.jpg'])
        self.assertEqual(fan.reconcile_artist_counts(output, ctx), output)
        css = (fan.ROOT/'assets/national-discovery.css').read_text()
        self.assertIn('.kc-discovery-artist[hidden]', css)
        self.assertIn('.kc-discovery-section[hidden]', css)
        profile_css = (fan.ROOT/'assets/fan-engagement.css').read_text()
        for selector in ('.kc-rd-show-row[hidden]', '.kc-rd-next-show[hidden]', '.kc-rd-profile-empty[hidden]'):
            self.assertIn(selector, profile_css)

    def test_state_classification_uses_final_directory_names_not_counts_or_weekend_links(self):
        with TemporaryDirectory() as tmp:
            site=Path(tmp);(site/'shows').mkdir()
            (site/'shows/index.html').write_text('<a href="/shows/this-weekend/">This Weekend</a><nav class="kc-state-links"><a href="/shows/texas/"><span>Texas</span><small>12 upcoming</small></a><a href="/shows/on/"><span>Ontario</span><small>Check for dates</small></a></nav>')
            self.assertEqual(fan.context(site,'2026-10-24')['statePaths'],{'/shows/texas/':'Texas','/shows/on/':'Ontario'})
    def test_home_source_loads_existing_google_tag_once_and_keeps_image_recovery_guards(self):
        text=(fan.ROOT/'index.html').read_text();d=Document(text)
        loaders=[n for n in d.nodes if n.tag=='script' and 'googletagmanager.com/gtag/js' in n.attrs.get('src','')]
        self.assertEqual(len(loaders),1)
        self.assertEqual(loaders[0].attrs['src'],'https://www.googletagmanager.com/gtag/js?id=G-N2KK9XF4TJ')
        self.assertIn('image-fix.js?v=20260906-2 temporarily disabled',text)
    def test_final_google_guard_rejects_comments_missing_bootstrap_and_duplicate_loaders(self):
        valid='''<html><head><script async src="https://www.googletagmanager.com/gtag/js?id=G-N2KK9XF4TJ"></script><script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}gtag('js',new Date());gtag('config','G-N2KK9XF4TJ');</script></head><body></body></html>'''
        fan.verify_google_tag(valid,'fixture')
        for invalid in ['<!-- G-N2KK9XF4TJ -->',valid.replace("gtag('config','G-N2KK9XF4TJ');",''),valid.replace('</head>',valid+'</head>')]:
            with self.assertRaises(AssertionError):fan.verify_google_tag(invalid,'fixture')
    def fixture(self, empty=True):
        name='Mike & Friends'
        body='<p class="kc-rd-profile-empty">No upcoming shows are currently listed.</p>' if empty else '<a class="kc-rd-show-row" href="/event/a/">A</a>'
        text=f'<html><head><title>Original</title><meta name="robots" content="index,follow"><script>gtag("config","G-N2KK9XF4TJ")</script></head><body><h1 id="kc-rd-artist-name">Mike &amp; Friends</h1><img src="/portrait.webp"><div class="kc-rd-next kc-rd-next--empty">Old empty message</div><div class="kc-rd-show-list">{body}</div><details class="kc-rd-past-shows"><summary>Past shows</summary>Archive</details></body></html>'
        return text,{'count':167,'artists':{'artists/mike/index.html':{'name':name,'empty':empty,'shows':[] if empty else ['/event/a/']}}}
    def test_empty_addition_preserves_photo_and_archive_and_valid_links(self):
        original,ctx=self.fixture()
        s=fan.transform(Path('artists/mike/index.html'),original.encode(),ctx).decode();d=Document(s)
        self.assertIn('No upcoming Mike &amp; Friends shows listed right now.',s)
        self.assertIn('href="/shows/#browse-states"',s)
        self.assertIn('<img src="/portrait.webp">',s)
        self.assertIn('<details class="kc-rd-past-shows"><summary>Past shows</summary>Archive</details>',s)
        self.assertNotIn('Old empty message',s)
        template=d.one(lambda n:n.tag=='template')
        self.assertEqual(len([n for n in d.nodes if 'data-empty-discovery' in n.attrs and n.start<template.start]),1)
    def test_active_artist_gets_only_inert_fallback_template(self):
        original,ctx=self.fixture(False);d=Document(fan.transform(Path('artists/mike/index.html'),original.encode(),ctx).decode())
        template=d.one(lambda n:n.tag=='template');self.assertFalse(any('data-empty-discovery' in n.attrs and n.start<template.start for n in d.nodes))
    def test_existing_google_identity_is_preserved(self):
        original,ctx=self.fixture();s=fan.transform(Path('artists/mike/index.html'),original.encode(),ctx).decode()
        self.assertIn('G-N2KK9XF4TJ',s);self.assertIn('"mode": "production"',s);self.assertNotIn('noindex',s)
    def test_instrumentation_fails_closed_if_upstream_callback_changes(self):
        with self.assertRaises((AssertionError,ValueError)):fan.transform(Path('app.js'),b'function unexpected() {}',{})
    def test_workflow_verifies_discovery_before_engagement_and_verifies_engagement_before_upload(self):
        s=(fan.ROOT/'.github/workflows/update-and-deploy.yml').read_text()
        self.assertLess(s.index('python scripts/finalize_fan_discovery.py _site _discovery_baseline --check'),s.index('python scripts/artist_engagement.py _site _engagement_baseline'))
        self.assertLess(s.index('python scripts/artist_engagement.py _site _engagement_baseline --check'),s.index('actions/upload-pages-artifact@v3'))
