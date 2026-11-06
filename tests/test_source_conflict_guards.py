"""Reviewed contradictions must remain honest through repeated source refreshes."""
import copy
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from apply_verified_show_information import enrich
from show_information_model import normalize
from show_information import detail_transform, schema_blocks, event_schemas
from test_show_information import fixture
ROOT=Path(__file__).resolve().parents[1]

class SourceConflictGuards(unittest.TestCase):
    def setUp(self):
        self.registry=json.loads((ROOT/'config/verified-show-information.json').read_text())['events']
    def reviewed(self,part):
        return next(e for e in self.registry if part in e['id'])
    def stale(self,item,field=None):
        correction=next(c for c in reversed(item['corrections']) if field is None or field in c['expected'])
        return {'id':item['id'],'startDate':item['startDate'],'city':item['city'],'state':item['state'],'country':item['country'],'venue':item['expectedVenue'],'address':item.get('expectedAddress',''),**copy.deepcopy(correction['expected'])}
    def test_owner_resolved_times_survive_curated_refresh_without_overwriting_later_times(self):
        for part, clock, iso, doors in (
            ('ignite-and-unite-tour-daytona','18:00','2026-11-13T18:00:00-05:00','17:30'),
            ('heliopolis-soundoff','22:00','2026-11-13T22:00:00-06:00',''),
        ):
            item=self.reviewed(part); original=self.stale(item,'startTime'); result=enrich(original,[item])
            self.assertEqual(result['startTime'],clock);self.assertEqual(result['startDateTime'],iso)
            self.assertEqual(result.get('doorsTime',''),doors);self.assertFalse(result['publicNotice'])
            self.assertEqual(enrich(result,[item]),result)
            self.assertEqual(normalize(result)['schemaStartDate'],iso)
            moved=copy.deepcopy(original);moved['startTime']='20:15';moved['startDateTime']=item['startDate']+'T20:15:00-05:00'
            self.assertEqual(enrich(moved,[item])['startTime'],'20:15')
            # All earlier reviewed source variants resolve to the latest owner
            # decision, while genuinely new clocks above remain untouched.
            for correction in item['corrections']:
                if 'startTime' not in correction['expected']: continue
                stale={**original,**copy.deepcopy(correction['expected'])}
                self.assertEqual(enrich(stale,[item])['startTime'],clock)
        calgary=enrich(self.stale(self.reviewed('heliopolis-soundoff'),'startTime'),self.registry)
        self.assertEqual(calgary['ageRestriction'],'Under 18 must be accompanied by a parent or legal guardian.')
        self.assertEqual(calgary['organizer']['name'],'Music Calgary')
        self.assertNotIn('11:00 PM',calgary['publicDescription'])
    def test_disputed_venue_does_not_become_schema_fact(self):
        item=self.reviewed('hhwg-christmas'); result=enrich(self.stale(item),[item]);norm=normalize(result)
        self.assertEqual(norm['venueLabel'],'Venue not confirmed');self.assertFalse(norm['address']);self.assertFalse(norm['postalCode'])
        rendered=detail_transform(fixture(),norm)
        schema=next(event_schemas(schema_blocks(rendered)[0][1]))
        self.assertNotIn('name',schema['location']);self.assertNotIn('streetAddress',schema['location']['address'])
        self.assertIn('register through Eventbrite for the giveaways',result['price'])
    def test_artist_published_rsvp_location_restored_without_inventing_walk_in_access(self):
        item=self.reviewed('babytooth-experience-huntington'); original=self.stale(item);result=enrich(original,[item]);norm=normalize(result)
        self.assertFalse(norm['private']);self.assertEqual(norm['address'],'15202 Transistor Lane');self.assertEqual(norm['postalCode'],'92649')
        self.assertEqual(enrich(result,[item]),result)
        rendered=detail_transform(fixture(),norm)
        self.assertIn('15202 Transistor Lane',rendered);self.assertIn('92649',rendered)
        self.assertIn('RSVP/application required',rendered)
        private=normalize(enrich({**original,'admission':'private'},[item]))
        self.assertTrue(private['private']);self.assertFalse(private['address']);self.assertFalse(private['postalCode'])

if __name__=='__main__':unittest.main()
