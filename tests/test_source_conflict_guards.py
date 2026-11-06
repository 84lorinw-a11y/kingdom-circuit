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
    def stale(self,item):
        return {'id':item['id'],'startDate':item['startDate'],'city':item['city'],'state':item['state'],'country':item['country'],'venue':item['expectedVenue'],'address':item.get('expectedAddress',''),**copy.deepcopy(item['corrections'][-1]['expected'])}
    def test_disputed_times_cannot_reappear_through_curated_refresh(self):
        for part in ('ignite-and-unite-tour-daytona','heliopolis-soundoff'):
            item=self.reviewed(part); original=self.stale(item); result=enrich(original,[item])
            self.assertEqual(result['startTime'],'');self.assertEqual(result['startDateTime'],'');self.assertEqual(result['doorsTime'],'')
            self.assertIn('not confirmed',result['publicNotice'])
            self.assertEqual(enrich(result,[item]),result)
            self.assertEqual(normalize(result)['schemaStartDate'],item['startDate'])
            moved=copy.deepcopy(original);moved['startTime']='20:15';moved['startDateTime']=item['startDate']+'T20:15:00-05:00'
            self.assertEqual(enrich(moved,[item])['startTime'],'20:15')
    def test_disputed_venue_does_not_become_schema_fact(self):
        item=self.reviewed('hhwg-christmas'); result=enrich(self.stale(item),[item]);norm=normalize(result)
        self.assertEqual(norm['venueLabel'],'Venue not confirmed');self.assertFalse(norm['address']);self.assertFalse(norm['postalCode'])
        rendered=detail_transform(fixture(),norm)
        schema=next(event_schemas(schema_blocks(rendered)[0][1]))
        self.assertNotIn('name',schema['location']);self.assertNotIn('streetAddress',schema['location']['address'])
        self.assertIn('register through Eventbrite for the giveaways',result['price'])
    def test_rsvp_restricted_street_removed_without_inventing_private_status(self):
        item=self.reviewed('babytooth-experience-huntington'); original=self.stale(item);result=enrich(original,[item]);norm=normalize(result)
        self.assertFalse(norm['private']);self.assertFalse(norm['address']);self.assertFalse(norm['venue']);self.assertFalse(norm['postalCode'])
        self.assertEqual(enrich(result,[item]),result)
        rendered=detail_transform(fixture(),norm)
        self.assertNotIn('15202 Transistor Lane',rendered);self.assertNotIn('92649',rendered)
        self.assertIn('RSVP/application required',rendered)

if __name__=='__main__':unittest.main()
