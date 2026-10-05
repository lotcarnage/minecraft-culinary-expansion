"""Regression checks for Minecraft recipe category validation."""
import unittest
from build_deliverable import validate_recipe_category


class RecipeCategoryTests(unittest.TestCase):
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


if __name__=='__main__':unittest.main()
