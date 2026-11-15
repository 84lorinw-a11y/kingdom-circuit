"""Final historical verifiers must share publication expiry without hiding defects."""
from contextlib import ExitStack, redirect_stdout
from copy import deepcopy
from datetime import date
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import verify_oct3_concert_corrections as october
import verify_live_redesign as redesign
from apply_verified_show_information import enrich
from build_seo_site import event_path


class FinalVerifierExpiryContractTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.site = self.root / 'site'
        original = next(e for e in json.loads((ROOT/'config/oct3-verified-concerts.json').read_text())
                        if e['id'] == 'the-holy-ghost-experience-chattanooga-2026-11-14')
        reviews = json.loads((ROOT/'config/verified-show-information.json').read_text())['events']
        self.event = enrich(original, reviews)
        self.assertEqual('2026-11-15T01:00:00-05:00', self.event['endDateTime'])
        self.event['image'] = 'assets/fixture-flyer.jpg'
        self.event['imageType'] = 'event_artwork'
        self.artist = {'name':'Nehemiah', 'imageUrl':'assets/nehemiah.jpg',
                       'bandsintownRejectedArtistIds':['15347266'],
                       'socialSearchEnabled':True, 'ticketmasterEnabled':False,
                       'textMatchEnabled':False}
        self.registry = [self.artist, {'name':'ZEKE', 'bandsintownRejectedArtistIds':['32942']}]
        self.write('config/artists.json', self.registry)
        self.write('site/config/artists.json', self.registry)
        self.write('event-history.json', {'events':[{'event':deepcopy(self.event),
                                                  'observedOnOrAfterEventDate':True}]})
        self.write('config/verified-show-information.json', {'events':[]})
        self.write('config/sep26-requested-lineups.json', {
            'ty-brasel-outlandish-fest-fort-worth-2026': {'startDate':'2026-01-01'}})
        self.text('site/artists/nehemiah/index.html', '<h1>Nehemiah</h1>')
        self.text('site/assets/nehemiah.jpg', 'retained portrait bytes')
        self.text('site/assets/fixture-flyer.jpg', 'retained original flyer bytes')
        self.retired = {'id':'fixture:retired', 'startDate':'2026-01-01'}
        self.whatup = {identity:dict(self.retired, id=identity) for identity in (
            'whatuprg-houston-2026-11-19', 'whatuprg-dallas-2026-11-20',
            'whatuprg-san-antonio-2026-11-22')}
        self.prepare(visible=True)

    def write(self, path, value):
        self.text(path, json.dumps(value))

    def text(self, path, value):
        file = self.root / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(value)

    def prepare(self, *, visible, actual=None):
        self.write('config/oct3-verified-concerts.json', [self.event])
        public = deepcopy(self.event if actual is None else actual)
        public['id'] = 'manual:' + public['id'].removeprefix('manual:')
        self.write('site/events.json', [public] if visible else [])
        self.write('site/supplemental-events.json', [])
        page = 'site/' + event_path(public).strip('/') + '/index.html'
        # The full verifier still checks accepted facts and original image bytes.
        self.text(page, '<img src="/' + public['image'] + '">' +
                  ' '.join(public.get('advertisedBilling', [])))
        return public

    def verify(self, as_of):
        with ExitStack() as stack:
            stack.enter_context(patch.object(october, 'ROOT', self.root))
            stack.enter_context(patch.object(october, 'REVIVAL_NIGHT_EVENT', self.retired))
            stack.enter_context(patch.object(october, 'BY_ID', self.whatup))
            stack.enter_context(redirect_stdout(io.StringIO()))
            october.verify(self.site, as_of=as_of)

    def test_actual_holy_ghost_before_on_and_after_pacific_expiry(self):
        before = {p.relative_to(self.root):p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        for day in ('2026-11-13','2026-11-14'):
            with self.subTest(day=day):
                self.verify(day)
        self.assertEqual(before, {p.relative_to(self.root):p.read_bytes()
                                 for p in self.root.rglob('*') if p.is_file()})
        self.prepare(visible=False)
        archive_before = (self.root/'event-history.json').read_bytes()
        for day in ('2026-11-15','2026-11-16','2027-01-01'):
            with self.subTest(day=day):
                self.verify(day)
        self.assertEqual(archive_before, (self.root/'event-history.json').read_bytes())

    def test_missing_current_or_future_show_still_fails(self):
        self.prepare(visible=False)
        for day in ('2026-11-13','2026-11-14'):
            with self.subTest(day=day), self.assertRaisesRegex(AssertionError, self.event['id']):
                self.verify(day)

    def test_wrong_active_facts_and_missing_original_artwork_still_fail(self):
        for field, wrong in (('venue','Wrong venue'), ('artists',['Wrong artist']),
                             ('startTime','21:30'), ('advertisedBilling',['Wrong bill'])):
            with self.subTest(field=field):
                self.prepare(visible=True, actual=dict(self.event, **{field:wrong}))
                with self.assertRaises(AssertionError):
                    self.verify('2026-11-14')
        self.prepare(visible=True)
        (self.site/self.event['image']).unlink()
        with self.assertRaises(AssertionError):
            self.verify('2026-11-14')

    def test_unknown_or_conflicting_end_clock_keeps_final_date_required(self):
        for change in ({'endDateTime':''}, {'endDateTime':'2026-11-15T01:00:00'},
                       {'endDateTime':'2026-11-15T01:00:00-05:00','endTime':'03:00'}):
            with self.subTest(change=change):
                self.event.update(change)
                self.prepare(visible=True)
                self.verify('2026-11-15')
                self.prepare(visible=False)
                with self.assertRaises(AssertionError):
                    self.verify('2026-11-15')
                self.verify('2026-11-16')

    def test_808_counts_share_the_same_boundary_and_keep_private_future_entries(self):
        overnight = dict(self.event, artists=['808 BEEZY'])
        unknown = dict(overnight, id='fixture:unknown', endDateTime='')
        future_private = dict(overnight, id='fixture:private', startDate='2026-11-20',
                              endDate='2026-11-20', startDateTime='', endDateTime='',
                              status='private')
        cancelled = dict(future_private, id='fixture:cancelled', status='cancelled')
        self.write('site/events.json',[overnight,unknown,future_private,cancelled])
        self.write('site/supplemental-events.json',[overnight])
        self.assertEqual(date(2026,11,14),redesign.event_last_date(overnight))
        self.assertEqual(3,redesign.current_808_count(self.site,as_of='2026-11-14'))
        self.assertEqual(2,redesign.current_808_count(self.site,as_of='2026-11-15'))
        self.assertEqual(1,redesign.current_808_count(self.site,as_of='2026-11-16'))

    def test_midnight_boundary_and_still_running_overnight_are_distinct(self):
        for ending, clock, required_on_nov15 in (
            ('2026-11-15T00:00:00-08:00','00:00',False),
            ('2026-11-15T00:00:01-08:00','00:00:01',True),
        ):
            with self.subTest(ending=ending):
                self.event.update(endDateTime=ending,endTime=clock)
                self.prepare(visible=False)
                if required_on_nov15:
                    with self.assertRaises(AssertionError): self.verify('2026-11-15')
                else:
                    self.verify('2026-11-15')

    def test_both_verifiers_use_the_frozen_publication_day_by_default(self):
        self.prepare(visible=False)
        with patch.dict(os.environ, {'KC_CATALOG_DAY':'2026-11-15'}):
            self.verify(None)
        with patch.dict(os.environ, {'KC_CATALOG_DAY':'2026-11-14'}):
            with self.assertRaises(AssertionError): self.verify(None)
        self.write('site/events.json',[dict(self.event,artists=['808 BEEZY'])])
        with patch.dict(os.environ, {'KC_CATALOG_DAY':'2026-11-14'}):
            self.assertEqual(1,redesign.current_808_count(self.site))
        with patch.dict(os.environ, {'KC_CATALOG_DAY':'2026-11-15'}):
            self.assertEqual(0,redesign.current_808_count(self.site))


if __name__ == '__main__':
    unittest.main()
