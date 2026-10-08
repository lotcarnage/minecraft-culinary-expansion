"""Player guide regression checks for canonical project filtering and recipe details."""
from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import patch
import item_project
import generate_food_guide as guide

ROOT = Path(__file__).resolve().parent.parent
CONFIG = {'mod_version': '0.1.3', 'minecraft_version': '26.3'}


class FoodGuideTests(unittest.TestCase):
    def test_arbitrary_vanilla_cooking_material_uses_display_name(self):
        project=deepcopy(item_project.load(ROOT/'source/items_project.json'))
        project['items'][0].update(cooking_ingredient='minecraft:gravel',smelting=True)
        with patch.object(item_project,'load',return_value=project):
            page=guide.render(CONFIG,ROOT)
        self.assertIn('<span title="minecraft:gravel">砂利</span>を',page)
        self.assertNotIn('>minecraft:gravel</span>',page)

    def test_unknown_material_name_stops_generation(self):
        project=deepcopy(item_project.load(ROOT/'source/items_project.json'))
        project['items'][0].update(cooking_ingredient='example:unknown',smelting=True)
        with patch.object(item_project,'load',return_value=project):
            with self.assertRaisesRegex(ValueError,'表示名がありません: example:unknown'):
                guide.render(CONFIG,ROOT)

    def test_enabled_items_and_recipe_details(self):
        project = item_project.load(ROOT / 'source/items_project.json')
        page = guide.render(CONFIG, ROOT)
        self.assertEqual(page.count('<tr data-nutrition='), sum(i['enabled'] for i in project['items']))
        self.assertIn('data:image/png;base64,', page)
        self.assertEqual(page.count('width="32" height="32"'), sum(i['enabled'] for i in project['items']))
        self.assertNotIn('調理 1.25秒', page)
        self.assertNotIn('経験値', page)
        self.assertNotIn('係数', page)
        self.assertEqual(page.count('<span class="hunger-icon">🍖</span>'), sum(i['nutrition'] // 2 for i in project['items'] if i['enabled']))
        self.assertEqual(page.count('<span class="hunger-icon half"><span>🍖</span></span>'), sum(i['nutrition'] % 2 for i in project['items'] if i['enabled']))
        self.assertNotIn('満腹時:', page)
        self.assertNotIn('食後に残る物:', page)
        self.assertIn('minecraft:egg', page)
        self.assertIn('<span title="minecraft:wheat">小麦</span>', page)
        self.assertNotIn('>minecraft:wheat</span>', page)
        self.assertIn('をかまど・燻製器で精錬する。', page)
        self.assertIn('完成個数:', page)
        self.assertNotIn('<details', page)
        self.assertNotIn('材料・配置を開く', page)
        self.assertIn('<th scope="col">最大スタック数</th>', page)
        self.assertNotIn('最大スタック:', page)
        self.assertNotIn('{{ROWS}}', page)
        self.assertNotIn('source/main/', page)

    def test_nonfood_has_no_recovery_time_or_consumption_effect(self):
        project=deepcopy(item_project.load(ROOT/'source/items_project.json'))
        project['items'][0].update(edible=False,effect='毒',nutrition=10,consume_seconds=9)
        with patch.object(item_project,'load',return_value=project):
            page=guide.render(CONFIG,ROOT)
        row=page.split('<tr data-nutrition=',1)[1].split('</tr>',1)[0]
        self.assertIn('食べられません',row)
        self.assertNotIn('hunger-icon',row)
        self.assertNotIn('9秒',row)
        self.assertNotIn('毒',row)
        self.assertIn('data-effect="false"',row)
        self.assertIn('で精錬する。',row)

    def test_default_order_follows_project_editor(self):
        project = item_project.load(ROOT / 'source/items_project.json')
        page = guide.render(CONFIG, ROOT)
        positions = [page.index('<strong>' + guide.html.escape(i['ja_name'], quote=True) + '</strong>')
                     for i in project['items'] if i['enabled']]
        self.assertEqual(positions, sorted(positions))
        self.assertIn('<select id="sort"><option value="original">標準</option>', page)
        self.assertIn("sort.value==='original'?[...rows]", page)

    def test_disabled_items_and_dependent_recipes_are_excluded(self):
        project = deepcopy(item_project.load(ROOT / 'source/items_project.json'))
        project['items'][0]['enabled'] = False
        with patch.object(item_project, 'load', return_value=project):
            page = guide.render(CONFIG, ROOT)
        self.assertNotIn('<strong>目玉焼き</strong>', page)
        self.assertNotIn('title="culinary_expansion:fried_egg"', page)

    def test_names_are_html_escaped(self):
        project = deepcopy(item_project.load(ROOT / 'source/items_project.json'))
        project['items'][0]['ja_name'] = '<script>alert(1)</script>'
        with patch.object(item_project, 'load', return_value=project):
            page = guide.render(CONFIG, ROOT)
        self.assertIn('&lt;script&gt;alert(1)&lt;/script&gt;', page)
        self.assertNotIn('<script>alert(1)</script>', page)


if __name__ == '__main__':
    unittest.main()
