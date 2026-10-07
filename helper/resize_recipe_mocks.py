"""Resize the generated prototypes; reuse related subjects for pending mocks."""
import json
from pathlib import Path
from PIL import Image
from convert_mock_pngs import indexed_icon

ROOT = Path(__file__).resolve().parent.parent
GENERATED = Path('C:/Users/carnage/.codex/generated_images/01a10f45-9d9b-7112-83fc-87451e1223e6')
FILES = [
    'exec-02b532d2-87ba-4bf9-980c-2b8e314be344.png',
    'exec-18cb1e66-afe5-4fe2-8e73-042b0b714c6c.png',
    'exec-220b9a24-3343-40fe-a2c8-13aecdd83df7.png',
    'exec-44a3aa29-088c-460b-a1c3-977713975111.png',
    'exec-571bb21c-8e9f-43d9-9505-0848060da782.png',
    'exec-60bfba29-be67-4509-b015-4bf5872d9d80.png',
    'exec-6226fe91-0955-459f-925a-83d3bdae0205.png',
    'exec-a5eb83a6-e507-4925-ab7e-3b58a434c3dd.png',
    'exec-cc10ba8b-c4d0-43cf-9637-d8d92f2f4acd.png',
    'exec-ef797164-5648-472e-8999-a6c237f0e68a.png',
]
MAPPING = {
    'raw_meat_patty': 1, 'hamburg_steak': 2, 'hamburger': 3,
    'sweet_berry_juice': 0, 'melon_juice': 5, 'milk_bottle': 4,
    'milk_cocoa': 8, 'sweet_berry_milk': 6, 'loaf_bread': 9,
    'salt_bucket': 7, 'salt': 7, 'salted_pork': 1, 'bacon': 2,
    'pork_block': 1, 'lard_block': 4, 'lard_grain': 4,
    'raw_french_fries': 9, 'fresh_french_fries': 9, 'french_fries': 9,
    'kelp_stock': 8,
}
target = ROOT / 'source/main/resources/assets/culinary_expansion/textures/item'
target.mkdir(parents=True, exist_ok=True)
for name, index in MAPPING.items():
    with Image.open(GENERATED / FILES[index]) as original:
        image = original.convert('RGBA')
        bounds = image.getbbox()
        if bounds:
            image = image.crop(bounds)
        image.thumbnail((14, 14), Image.Resampling.LANCZOS)
        icon = Image.new('RGBA', (16, 16))
        icon.alpha_composite(image, ((16-image.width)//2, (16-image.height)//2))
        indexed_icon(icon).save(target / f'{name}.png', transparency=0)
    with Image.open(target / f'{name}.png') as check:
        assert check.size == (16, 16)
project = json.loads((ROOT / 'source/items_project.json').read_text(encoding='utf-8'))
assert set(MAPPING) == {i['name'] for i in project['items']} - {'fried_egg', 'chocolate'}
print('20 mock textures saved and verified at 16x16.')
