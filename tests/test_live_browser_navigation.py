"""Exercise browser audit decisions against the actual navigation renderer."""
from pathlib import Path
import sys
import unittest
from urllib.parse import urljoin

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import live_browser_retest as audit
import location_navigation as location
from mobile_discovery import Document


class Link:
    def __init__(self, href, menu=None):
        self.href = urljoin(audit.ORIGIN, href)
        self.menu = menu
        self.visible = True

    def get_attribute(self, name):
        return self.href if name == 'href' else None

    def is_displayed(self):
        return self.visible and (self.menu is None or self.menu.open)


class Navigation:
    def __init__(self, markup, menu=None):
        self.menu = menu
        self.links = [Link(node.attrs['href'], menu) for node in Document(markup).nodes
                      if node.tag == 'a']

    def find_elements(self, by, selector):
        assert (by, selector) == (audit.CSS_SELECTOR, 'a[href]')
        return self.links

    def is_displayed(self):
        return self.menu is None or self.menu.open


class Summary:
    def __init__(self, menu):
        self.menu = menu
        self.visible = True
        self.clicks = 0
        self.working = True

    def is_displayed(self):
        return self.visible

    def click(self):
        self.clicks += 1
        if self.working:
            self.menu.open = not self.menu.open


class Menu:
    def __init__(self):
        self.open = False
        self.summary = Summary(self)
        markup = location.menu()
        doc = Document(markup)
        assert any(n.tag == 'summary' and n.attrs.get('aria-label') == 'More navigation'
                   for n in doc.nodes)
        assert any(n.tag == 'nav' and n.attrs.get('aria-label') == 'More navigation'
                   for n in doc.nodes)
        self.nav = Navigation(markup, self)

    def get_attribute(self, name):
        return 'true' if name == 'open' and self.open else None

    def find_element(self, by, selector):
        assert by == audit.CSS_SELECTOR
        return {'summary[aria-label="More navigation"]': self.summary,
                'nav[aria-label="More navigation"]': self.nav}[selector]


class Driver:
    def __init__(self):
        self.primary = [Navigation(location.nav(''))]
        self.menus = [Menu()]

    def find_elements(self, by, selector):
        assert by == audit.CSS_SELECTOR
        return {'nav[aria-label="Primary navigation"]': self.primary,
                'details.kc-location-menu': self.menus}[selector]


class Wait:
    def __init__(self, driver):
        self.driver = driver

    def until(self, predicate):
        if not predicate(self.driver):
            raise TimeoutError('Interaction did not reach the expected state')


class BrowserNavigationTests(unittest.TestCase):
    def run_audit(self, driver, width=390):
        results = []
        audit.audit_navigation(driver, Wait(driver),
                               lambda name, passed, detail='': results.append((name, passed, detail)), width)
        return [name for name, passed, _ in results if not passed]

    def test_real_renderer_passes_at_every_audited_width_and_menu_is_operated(self):
        for width in (1440, 390, 320, 768):
            with self.subTest(width=width):
                driver = Driver()
                self.assertFalse(driver.menus[0].nav.is_displayed())
                self.assertEqual(self.run_audit(driver, width), [])
                self.assertEqual(driver.menus[0].summary.clicks, 2)
                self.assertFalse(driver.menus[0].open)

    def test_previous_sixteen_failures_are_secondary_links_and_still_checked(self):
        for path in ('/shows/this-weekend/', '/shows/this-month/', '/new-shows/', '/about-us/'):
            with self.subTest(path=path):
                driver = Driver()
                self.assertFalse(any(link.href == audit.ORIGIN + path for link in driver.primary[0].links))
                driver.menus[0].nav.links = [link for link in driver.menus[0].nav.links
                                           if link.href != audit.ORIGIN + path]
                self.assertIn(f'390px navigation More {path}', self.run_audit(driver))

    def test_states_and_cities_are_required_primary_links(self):
        for path in ('/shows/states/', '/shows/cities/'):
            with self.subTest(path=path):
                driver = Driver()
                driver.primary[0].links = [link for link in driver.primary[0].links
                                           if link.href != audit.ORIGIN + path]
                self.assertIn(f'390px navigation primary {path}', self.run_audit(driver))

    def test_hidden_primary_link_is_rejected(self):
        driver = Driver()
        driver.primary[0].links[0].visible = False
        self.assertIn('390px navigation primary /shows/', self.run_audit(driver))

    def test_hidden_secondary_link_is_rejected_even_when_menu_opens(self):
        driver = Driver()
        driver.menus[0].nav.links[1].visible = False
        self.assertIn('390px navigation More /about-us/', self.run_audit(driver))

    def test_duplicate_and_wrong_destination_links_are_rejected(self):
        driver = Driver()
        driver.primary[0].links.append(driver.primary[0].links[0])
        self.assertIn('390px navigation primary /shows/', self.run_audit(driver))
        driver = Driver()
        driver.menus[0].nav.links[1].href = 'https://example.com/about-us/'
        self.assertIn('390px navigation More /about-us/', self.run_audit(driver))

    def test_missing_regions_and_menu_are_rejected(self):
        driver = Driver()
        driver.primary = []
        driver.menus = []
        self.assertEqual(self.run_audit(driver), ['390px navigation primary region',
                                                 '390px navigation More menu'])

    def test_broken_menu_toggle_is_rejected(self):
        driver = Driver()
        driver.menus[0].summary.working = False
        self.assertIn('390px navigation More interaction', self.run_audit(driver))

    def test_menu_that_starts_open_is_rejected(self):
        driver = Driver()
        driver.menus[0].open = True
        self.assertIn('390px navigation More initially collapsed', self.run_audit(driver))

    def test_every_menu_destination_gets_a_real_page_check_in_ci(self):
        generated_routes = {node.attrs['href'] for node in
                            Document(location.nav('') + location.menu()).nodes if node.tag == 'a'}
        self.assertEqual(set(audit.PRIMARY_ROUTES) | set(audit.MORE_ROUTES), generated_routes)
        self.assertTrue(generated_routes <= set(audit.PAGE_ROUTES))
        self.assertIn('/artists/kb/', audit.PAGE_ROUTES)
        self.assertEqual(len(audit.PAGE_ROUTES), len(set(audit.PAGE_ROUTES)))

    def test_state_shortcuts_use_current_options_without_requiring_texas_or_florida(self):
        destinations = {'ON': {'name': 'Ontario', 'href': '/shows/ontario/'},
                        'NY': {'name': 'New York', 'href': '/shows/new-york/'},
                        'TX': {'name': 'Texas', 'href': '/shows/texas/'}}
        self.assertEqual(audit.available_state_shortcuts(['', 'ON', 'NY'], destinations),
                         [('ON', 'Ontario', '/shows/ontario/'), ('NY', 'New York', '/shows/new-york/')])
        self.assertEqual(audit.available_state_shortcuts(['', 'ON'], destinations),
                         [('ON', 'Ontario', '/shows/ontario/')])

    def test_missing_state_destinations_do_not_create_a_successful_sample(self):
        self.assertEqual(audit.available_state_shortcuts(['', 'ON'], {}), [])


if __name__ == '__main__':
    unittest.main()
