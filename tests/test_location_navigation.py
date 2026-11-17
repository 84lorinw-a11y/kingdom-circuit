"""Guard public counts and factual preservation at the production location boundary."""
import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import location_navigation as location
from mobile_discovery import Document
from finalize_seo_indexing_core import classify
from url_continuity import calendar_robots

class LocationNavigationTests(unittest.TestCase):
    def test_new_directories_remain_indexable_without_event_cards(self):
        for route in ['/shows/states/', '/shows/cities/']:
            self.assertEqual(classify(route, '<a data-location-entry>Florida</a>'), (True, 'core'))
            self.assertIsNone(calendar_robots(route, '<a data-location-entry>Florida</a>'))
        self.assertEqual(classify('/shows/empty-florida/', ''), (False, 'empty-city'))

    def test_structure_preserves_original_show_facts_and_artwork(self):
        original = '<html><head><title>Show</title><meta name="robots" content="index,follow"><script type="application/ld+json">{"@type":"Event","name":"Concert","offers":{"price":"15"}}</script></head><body>' + self.card('/event/one/') + '<img src="/assets/real-flyer.jpg"></body></html>'
        linked = original.replace('<dd>Orlando, FL</dd>', '<dd><a class="kc-location-inline" href="/shows/orlando-florida/">Orlando, FL</a></dd>')
        self.assertEqual(location.html_facts(original), location.html_facts(linked))
        self.assertNotEqual(location.html_facts(original), location.html_facts(linked.replace('"15"', '"0"')))
        self.assertNotEqual(location.html_facts(original), location.html_facts(linked.replace('real-flyer.jpg', 'old-flyer.jpg')))

    def card(self, path, title='Concert', badge='Concert'):
        return f'<article data-event-card data-state="FL"><h3><a href="{path}">{title}</a></h3><div class="event-badges">{badge}</div><dl><div><dt>Location</dt><dd>Orlando, FL</dd></div></dl></article>'
    def test_counts_distinct_public_shows_and_preserves_sold_out(self):
        one=self.card('/event/one/')
        html=one+one+self.card('/event/private/',badge='Private Event')+self.card('/event/cancelled/',badge='Cancelled')+self.card('/event/postponed/',badge='Postponed')+self.card('/event/sold/',badge='Sold Out')
        result=location.public_cards(html)
        self.assertEqual(set(result),{'/event/one/','/event/sold/'})
        self.assertEqual(result['/event/one/']['location'],'Orlando, FL')
    def test_production_paths_keep_existing_identity(self):
        self.assertEqual(location.path_of('https://kingdomcircuit.com/shows/orlando-florida/'),'/shows/orlando-florida/')
        self.assertEqual(location.href('/shows/orlando-florida/'),'/shows/orlando-florida/')
    def test_sitemap_adds_only_directory_routes_and_keeps_existing_dates(self):
        source=b'<urlset><url><loc>https://example.com/old/</loc><lastmod>2026-09-21</lastmod></url></urlset>'
        result=location.transform('sitemap.xml',source,{})
        self.assertIn(b'<lastmod>2026-09-21</lastmod>',result)
        self.assertEqual(result.count(b'<lastmod>'),1)
        self.assertEqual(result.count(b'<url>'),3)
        self.assertEqual(location.transform('sitemap.xml',result,{}),result)

    def test_directory_metadata_uses_production_identity(self):
        template='<html><head><title>About Us</title><meta name="robots" content="index,follow"><meta name="twitter:title" content="About Us"><link rel="canonical" href="https://example.com/about/"></head><body><header class="kc-rd-header"><div class="kc-rd-primary"></div></header><main>About content</main><footer><div class="footer-links"></div></footer></body></html>'
        ctx={'template':template,'regions':{},'cities':{},'locations':{}}
        for kind in ['states','cities']:
            page=location.directory(ctx,kind).decode();doc=Document(page)
            canonical=doc.one(lambda n:n.attrs.get('rel')=='canonical').attrs['href']
            self.assertEqual(canonical,'https://kingdomcircuit.com/shows/'+kind+'/')
            self.assertNotIn('content="About Us"',page)
            self.assertIn('content="index,follow"',page)

    def test_navigation_preserves_final_show_stylesheet_position(self):
        marker = '<link data-kc-show-information rel="stylesheet" href="/assets/show-information.css?v=20261106-2">'
        text = '<html><head>' + marker + '</head><body><header class="kc-rd-header"><div class="kc-rd-primary"></div></header><main></main><footer><div class="footer-links"></div></footer></body></html>'
        ctx = {'regions': {}, 'cities': {}, 'locations': {}}
        result = location.transform('event/example/index.html', text.encode(), ctx).decode()
        self.assertIn(marker + '</head>', result)
        self.assertLess(result.index('assets/location-navigation.js'), result.index(marker))

    def test_zero_count_does_not_claim_future_event(self):
        self.assertIn('No upcoming shows listed',location.location_link({'path':'/shows/florida/','name':'Florida','count':0}))
    def test_featured_locations_rank_by_count_with_stable_ties_and_exclude_empty(self):
        rows=[{'path':f'/shows/city-{i}/','name':f'City {i:02d}','count':i} for i in range(14)]
        rows += [{'path':'/shows/alpha/','name':'Alpha','count':13}]
        ctx={'cities':{r['path']:r for r in reversed(rows)}}
        ranked=location.featured_locations(ctx,'cities')
        self.assertEqual(len(ranked),10)
        self.assertEqual([r['name'] for r in ranked[:3]],['Alpha','City 13','City 12'])
        self.assertTrue(all(r['count']>0 for r in ranked))
        self.assertEqual(len({r['path'] for r in ranked}),10)
    def test_country_mapping_keeps_california_distinct_from_canada(self):
        self.assertEqual(location.country_of({'name':'California'}),'US')
        self.assertEqual(location.country_of({'name':'Saskatchewan'}),'CA')
        self.assertEqual(location.country_of({'name':'Quebec'}),'CA')
    def test_featured_links_do_not_become_duplicate_filter_results(self):
        rows={'/shows/florida/':{'path':'/shows/florida/','name':'Florida','count':4}}
        doc=Document(location.featured_section({'regions':rows},'states'))
        featured=[n for n in doc.nodes if 'data-featured-location' in n.attrs]
        self.assertEqual(len(featured),1)
        self.assertEqual(featured[0].attrs['data-show-count'],'4')
        self.assertNotIn('data-location-entry',featured[0].attrs)
    def test_new_navigation_contains_five_links_and_current_state(self):
        doc=Document(location.nav('/shows/states/'))
        links=[n for n in doc.nodes if n.tag=='a']
        self.assertEqual([doc.text(n) for n in links],['All Shows','States','Cities','Artists','Festivals'])
        self.assertEqual([doc.text(n) for n in links if n.attrs.get('aria-current')],['States'])
    def test_about_and_date_shortcuts_remain_crawlable(self):
        doc=Document(location.menu())
        names={doc.text(n) for n in doc.nodes if n.tag=='a'}
        self.assertTrue({'About Us','This Weekend','This Month','New Shows','Submit a Show'} <= names)
    def test_transform_preserves_canonical_and_original_artwork_and_archive(self):
        image='<img src="/assets/original.webp" width="500" height="700">'
        archive='<section data-past-shows-archive><dd>Orlando, FL</dd></section>'
        text='<html><head><link rel="canonical" href="https://kingdomcircuit.com/artists/kb/"></head><body><header class="kc-rd-header"><div class="kc-rd-primary"></div></header><main>'+image+'<dl><div><dt>Location</dt><dd>Orlando, FL</dd></div><div><dt>Venue</dt><dd>Orlando, FL</dd></div></dl><div class="event-detail-copy"><dl><div><dt>Location</dt><dd>Orlando, FL</dd></div></dl></div>'+archive+'</main><footer><div class="footer-links"></div></footer></body></html>'
        ctx={'cities':{},'regions':{},'locations':{'Orlando, FL':'/shows/orlando-florida/'}}
        result=location.transform('artists/kb/index.html',text.encode(),ctx).decode()
        self.assertIn(image,result);self.assertIn(archive,result)
        self.assertEqual(result.count('class="kc-location-inline"'), 1)
        self.assertIn('<dt>Venue</dt><dd>Orlando, FL</dd>', result)
        self.assertIn('<link rel="canonical" href="https://kingdomcircuit.com/artists/kb/">',result)
        self.assertEqual(location.transform('artists/kb/index.html',result.encode(),ctx),result.encode())
if __name__=='__main__':unittest.main()
