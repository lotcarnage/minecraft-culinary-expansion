"""Save the added item mocks as indexed PNGs with transparent palette index 0."""
import json
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent


def indexed_icon(image):
    rgba = image.convert('RGBA')
    # A transparent color uses binary alpha; remove resize-edge translucency.
    colors = list(dict.fromkeys(rgb[:3] for rgb in rgba.getdata() if rgb[3] >= 128))
    if len(colors) > 255:
        raise ValueError('Mock requires more than 255 opaque palette colors')
    lookup = {color: index + 1 for index, color in enumerate(colors)}
    result = Image.new('P', rgba.size)
    palette = [0, 0, 0] + [channel for color in colors for channel in color]
    result.putpalette(palette + [0] * (768 - len(palette)))
    result.putdata([lookup[pixel[:3]] if pixel[3] >= 128 else 0 for pixel in rgba.getdata()])
    result.info['transparency'] = 0
    return result


if __name__ == '__main__':
    project = json.loads((ROOT / 'source/items_project.json').read_text(encoding='utf-8'))
    paths = [ROOT / 'source/main/resources/assets/culinary_expansion/textures/item' / (item['name'] + '.png')
             for item in project['items'] if item['name'] not in ('fried_egg', 'chocolate')]
    for path in paths:
        with Image.open(path) as image:
            result = indexed_icon(image)
        result.save(path, transparency=0)
        with Image.open(path) as check:
            assert check.size == (16, 16) and check.mode == 'P'
            assert check.info['transparency'] == 0
            assert path.read_bytes()[25] == 3  # PNG IHDR color type: indexed.
    print(f'{len(paths)} PNGs verified: 16x16, indexed palette, transparent index 0.')
