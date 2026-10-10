"""Release guards for promotion of the approved artist form."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('artist_intake', ROOT / 'scripts/apply_artist_intake.py')
intake = importlib.util.module_from_spec(spec)
spec.loader.exec_module(intake)


class ArtistIntakeTests(unittest.TestCase):
    def test_preserves_shell_and_is_idempotent_after_refresh(self):
        with tempfile.TemporaryDirectory() as temp:
            site = Path(temp)
            (site / 'assets').mkdir()
            page = site / intake.ROUTE
            page.parent.mkdir(parents=True)
            head = '<html><head><link rel="canonical" href="' + intake.URL + '"><meta name="robots" content="index,follow"><meta http-equiv="Content-Security-Policy" content="form-action \'self\' https://formspree.io"><script>G-N2KK9XF4TJ</script>'
            nav = '<body><header class="kc-rd-header">Existing navigation</header>'
            footer = '<footer>Existing footer</footer><script src="/assets/kc-redesign-v1.js"></script></body></html>'
            page.write_text(head + '</head>' + nav + '<main>Old generated form</main>' + footer)
            intake.apply(site)
            approved = page.read_text()
            self.assertTrue(approved.startswith(head))
            self.assertIn(nav, approved)
            self.assertTrue(approved.endswith(footer))
            intake.apply(site)
            self.assertEqual(approved, page.read_text())
            page.write_text(approved.replace('name="email" type="email"', 'name="email" type="text"'))
            with self.assertRaises(AssertionError):
                intake.verify(site)
            intake.apply(site)
            self.assertEqual(approved, page.read_text())

    def test_workflow_applies_and_checks_after_imported_redesign(self):
        workflow = (ROOT / '.github/workflows/update-and-deploy.yml').read_text()
        self.assertLess(workflow.index('python _redesign_source/scripts/apply_test_redesign.py'), workflow.index('python scripts/apply_artist_intake.py _site'))
        self.assertLess(workflow.index('python scripts/apply_artist_intake.py _site'), workflow.index('python scripts/apply_artist_intake.py _site --check'))
        self.assertIn('node --test tests/artist-intake-submit.test.cjs', workflow)


if __name__ == '__main__':
    unittest.main()
