"""Paper generation and release regression tests."""
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from unittest.mock import patch
import build_deliverable as release
import paper_release as paper

ROOT = Path(__file__).resolve().parent.parent

class PaperReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        import shutil
        for directory in ('source', 'helper'):
            shutil.copytree(ROOT / directory, self.root / directory,
                            ignore=shutil.ignore_patterns('__pycache__'))
        (self.root / 'build').mkdir()
        shutil.copyfile(ROOT / 'build/food-guide.template.html', self.root / 'build/food-guide.template.html')
        shutil.copytree(ROOT / 'build/paper', self.root / 'build/paper')
        self.config = release.properties()
        paper.generate(self.root, self.config)

    def fake_jar(self):
        path = self.root / 'intermediate/paper-output/libs' / paper.jar_name(self.config)
        path.parent.mkdir(parents=True)
        with zipfile.ZipFile(path, 'w') as archive:
            archive.writestr('dev/lotcarnage/culinaryexpansion/paper/CulinaryExpansionPlugin.class', b'\xca\xfe\xba\xbe')
            archive.writestr('dev/lotcarnage/culinaryexpansion/paper/GeneratedContent.class', b'\xca\xfe\xba\xbe')
            for file in (self.root / 'intermediate/paper-generated/resources').iterdir():
                archive.write(file, file.name)
        return path

    def test_generated_content_and_disabled_items(self):
        java = (self.root / 'intermediate/paper-generated/java/dev/lotcarnage/culinaryexpansion/paper/GeneratedContent.java').read_text()
        self.assertIn('p.item("fried_egg", 64, 2, 2.4F', java)
        self.assertIn('"GLASS_BOTTLE", "NIGHT_VISION", 600, 0, 1.0', java)
        self.assertIn('p.ingredient("culinary_expansion:loaf_bread")', java)
        self.assertNotIn('p.item("salt",', java)
        self.assertNotIn('salt_from_crafting', java)
        with zipfile.ZipFile(self.root / 'intermediate/paper-generated' / paper.pack_name(self.config)) as archive:
            self.assertIn('assets/culinary_expansion/items/fried_egg.json', archive.namelist())
            self.assertNotIn('assets/culinary_expansion/items/salt.json', archive.namelist())
            self.assertIn('item.culinary_expansion.fried_egg', json.loads(archive.read('assets/culinary_expansion/lang/ja_jp.json')))

    def test_stale_item_definitions_stop_release(self):
        self.fake_jar()
        paper.prepare(self.root, self.config)
        project = self.root / 'source/items_project.json'
        project.write_text(project.read_text(encoding='utf-8') + '\n', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'Outdated Paper JAR'):
            paper.prepare(self.root, self.config)

    def test_resource_pack_must_match_plugin(self):
        self.fake_jar()
        pack = self.root / 'intermediate/paper-generated' / paper.pack_name(self.config)
        with zipfile.ZipFile(pack, 'w') as archive:
            archive.writestr('pack.mcmeta', '{}')
            archive.writestr('release-inputs.sha256', 'old')
        with self.assertRaisesRegex(ValueError, 'Outdated Paper resource pack'):
            paper.prepare(self.root, self.config)

    def test_paper_page_preserves_forge_and_has_checksums(self):
        self.fake_jar()
        artifacts = paper.prepare(self.root, self.config)
        page = self.root / 'deliverables/index.html'
        page.parent.mkdir()
        page.write_text('<main><section>Forge</section><footer></footer></main>', encoding='utf-8')
        paper.publish(self.root, self.config, artifacts)
        paper.publish(self.root, self.config, artifacts)
        content = page.read_text(encoding='utf-8')
        self.assertIn('<section>Forge</section>', content)
        self.assertEqual(content.count('id="paper"'), 1)
        for artifact in artifacts:
            self.assertTrue((page.parent / 'downloads' / (artifact.name + '.sha256')).exists())

    def test_all_failure_does_not_publish_either_platform(self):
        with patch('sys.argv', ['build_deliverable.py', '--platform', 'all', '--pages-only']), \
             patch.object(paper, 'prepare', side_effect=ValueError('Outdated Paper JAR')), \
             patch.object(release, 'prepare_pages') as forge, patch.object(paper, 'publish') as publish:
            self.assertEqual(release.main(), 1)
            forge.assert_not_called()
            publish.assert_not_called()

if __name__ == '__main__':
    unittest.main()

