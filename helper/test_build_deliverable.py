"""Regression checks for Minecraft recipe category validation."""
import unittest
import json
from pathlib import Path
import tempfile
from unittest.mock import patch
import subprocess
import zipfile
import build_deliverable as release
from build_deliverable import validate_recipe_category


class RecipeCategoryTests(unittest.TestCase):
    def test_missing_recipe_references_are_rejected(self):
        for advancement in (
            {'rewards':{'recipes':['culinary_expansion:disabled_from_crafting']}},
            {'criteria':{'unlock':{'trigger':'minecraft:recipe_unlocked',
                                  'conditions':{'recipes':'culinary_expansion:disabled_from_crafting'}}}},
        ):
            with tempfile.TemporaryDirectory() as temp:
                artifact=Path(temp)/'test.jar'
                with zipfile.ZipFile(artifact,'w') as archive:
                    archive.writestr('data/culinary_expansion/advancement/test.json',json.dumps(advancement))
                with zipfile.ZipFile(artifact) as archive:
                    with self.assertRaisesRegex(ValueError,'Missing recipe culinary_expansion:disabled_from_crafting'):
                        release.validate_recipe_references(archive)
                with zipfile.ZipFile(artifact,'a') as archive:
                    archive.writestr('data/culinary_expansion/recipe/disabled_from_crafting.json','{}')
                with zipfile.ZipFile(artifact) as archive:release.validate_recipe_references(archive)

    def test_crafting_food_category_is_rejected(self):
        for kind in ('crafting_shaped','crafting_shapeless'):
            with self.assertRaisesRegex(ValueError,'Invalid recipe category'):
                validate_recipe_category({'type':'minecraft:'+kind,'category':'food'},'chocolate.json')
            validate_recipe_category({'type':'minecraft:'+kind,'category':'misc'},'chocolate.json')

    def test_cooking_food_category_is_valid(self):
        for kind in ('smelting','smoking','campfire_cooking'):
            validate_recipe_category({'type':'minecraft:'+kind,'category':'food'},'fried_egg.json')
            with self.assertRaises(ValueError):
                validate_recipe_category({'type':'minecraft:'+kind,'category':'equipment'},'fried_egg.json')


class ReleaseTests(unittest.TestCase):
    def test_package_version_comes_from_project_metadata(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            (root/'build').mkdir();(root/'source').mkdir()
            (root/'build/gradle.properties').write_text('minecraft_version=26.3\nforge_version=66.0.5\nmod_version=old\n',encoding='utf-8')
            (root/'source/items_project.json').write_text('{"schema_version":1,"version":"2.0.0-beta","items":[]}',encoding='utf-8')
            with patch.object(release,'ROOT',root):
                self.assertEqual(release.properties()['mod_version'],'2.0.0-beta')
    def test_same_name_outdated_resource_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            resources = root / 'source/main/resources'
            resources.mkdir(parents=True)
            (resources / 'META-INF').mkdir()
            (resources / 'META-INF/mods.toml').write_bytes(b'current metadata')
            artifact = root / 'old.jar'
            with zipfile.ZipFile(artifact, 'w') as archive:
                archive.writestr('META-INF/mods.toml', b'old metadata')
                archive.writestr('dev/lotcarnage/culinaryexpansion/CulinaryExpansion.class', b'unused')
            with patch.object(release, 'ROOT', root), patch.object(release, 'properties', return_value={'mod_version': '0.1.0'}):
                with self.assertRaisesRegex(ValueError, 'Outdated mod JAR resources'):
                    release.validate_mod_archive(artifact)

    def test_build_failure_does_not_publish(self):
        with patch('sys.argv', ['build_deliverable.py']), \
             patch.object(release, 'build', side_effect=subprocess.CalledProcessError(1, 'gradle')), \
             patch.object(release, 'prepare_pages') as publish:
            self.assertEqual(release.main(), 1)
            publish.assert_not_called()


if __name__=='__main__':unittest.main()
