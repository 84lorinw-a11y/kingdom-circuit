import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import artist_engagement as fan
from mobile_discovery import Document

class FanEngagement(unittest.TestCase):
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
