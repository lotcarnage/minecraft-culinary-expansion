"""Render a portable player guide from enabled items in the canonical project."""
import base64
from collections import Counter
import html
import json
import struct

METHODS = {'minecraft:crafting_shaped': '作業台（定形）',
           'minecraft:crafting_shapeless': 'クラフト（順不同）',
           'minecraft:smelting': 'かまど', 'minecraft:smoking': '燻製器',
           'minecraft:campfire_cooking': '焚き火', 'minecraft:blasting': '溶鉱炉'}


def render(config, root):
    esc = lambda value: html.escape(str(value), quote=True)
    import item_project
    project = item_project.load(root / 'source/items_project.json')
    items = [item for item in project['items'] if item['enabled']]
    names = json.loads((root / 'source/vanilla_item_names.json').read_text(encoding='utf-8-sig'))['names']
    names.update({f'culinary_expansion:{i["name"]}': i['ja_name'] for i in items})
    generated = item_project.generated(project, root)
    disabled = {'culinary_expansion:' + i['name'] for i in project['items'] if not i['enabled']}
    recipes = []
    for path, content in sorted(generated.items()):
        if path.startswith('source/main/resources/data/culinary_expansion/recipe/'):
            recipe = json.loads(content)
            if not any('"' + identifier + '"' in content.decode('utf-8') for identifier in disabled):
                recipes.append(recipe)

    def material(value):
        if isinstance(value, list):
            return ' または '.join(material(v) for v in value)
        if isinstance(value, dict):
            value = value.get('item') or '#' + value['tag']
        if value.startswith('#'):
            label = 'タグのいずれか: ' + value[1:]
        else:
            if value not in names:
                raise ValueError(f'レシピ素材の表示名がありません: {value}。表示名辞書を更新してください。')
            label = names[value]
        return f'<span title="{esc(value)}">{esc(label)}</span>'

    def recipe_html(recipe):
        kind = recipe['type']
        result = recipe['result']
        count = result.get('count', 1) if isinstance(result, dict) else 1
        body = ''
        if kind == 'minecraft:crafting_shaped':
            pattern = recipe['pattern']
            body = '<div class="grid" aria-label="クラフト配置（左上から）">'
            for y in range(3):
                for x in range(3):
                    symbol = pattern[y][x] if y < len(pattern) and x < len(pattern[y]) else ' '
                    body += '<div>' + (material(recipe['key'][symbol]) if symbol != ' ' else '<span class="empty">空き</span>') + '</div>'
            body += '</div>'
        elif 'ingredients' in recipe:
            ingredients = Counter(material(v) for v in recipe['ingredients'])
            body = '<ul>' + ''.join(f'<li>{v} × {n}</li>' for v, n in ingredients.items()) + '</ul>'
        elif 'ingredient' in recipe:
            device = {'minecraft:smelting': 'かまど', 'minecraft:smoking': '燻製器', 'minecraft:campfire_cooking': '焚き火', 'minecraft:blasting': '溶鉱炉'}.get(kind)
            if device is None:
                raise ValueError(f'Unsupported cooking method: {kind}')
            body = '<p>' + material(recipe['ingredient']) + 'を' + device + 'で精錬する。</p>'
            if count != 1:
                body += f'<p>完成個数: {count}個</p>'
        else:
            raise ValueError(f'Unsupported recipe for player guide: {kind}')
        if kind in ('minecraft:crafting_shaped', 'minecraft:crafting_shapeless'):
            return f'<article class="recipe"><h4>{esc(METHODS[kind])} · 完成個数: {count}個</h4>{body}</article>'
        return f'<article class="recipe">{body}</article>'

    rows = []
    for item in items:
        identifier = 'culinary_expansion:' + item['name']
        texture = (root / 'source/main/resources/assets/culinary_expansion/textures/item' / (item['name'] + '.png')).read_bytes()
        width, height = struct.unpack('>II', texture[16:24])
        image = 'data:image/png;base64,' + base64.b64encode(texture).decode('ascii')
        matching = [r for r in recipes if (r['result'].get('id') if isinstance(r['result'], dict) else r['result']) == identifier]
        effect = item['effect']
        if effect != 'なし':
            effect += f' Lv.{item["effect_level"]} · {item["effect_ticks"]/20:g}秒 · {item["effect_probability"]*100:g}%'
        hunger_icons = '<span class="hunger-icon">🍖</span>' * (item['nutrition'] // 2)
        if item['nutrition'] % 2:
            hunger_icons = '<span class="hunger-icon half"><span>🍖</span></span>' + hunger_icons
        hunger_icons = f'<span class="hunger-icons" role="img" aria-label="満腹度アイコン {item["nutrition"]/2:g}個分">{hunger_icons}</span>'
        recovery = item['nutrition'] * item['saturation_modifier'] * 2
        recipe_parts = []
        used = set()
        for index, recipe in enumerate(matching):
            if index in used:
                continue
            if recipe['type'] in ('minecraft:smelting', 'minecraft:smoking'):
                group = [(j, r) for j, r in enumerate(matching)
                         if r['type'] in ('minecraft:smelting', 'minecraft:smoking')
                         and r.get('ingredient') == recipe.get('ingredient')
                         and r['result'] == recipe['result']]
                if {r['type'] for _, r in group} == {'minecraft:smelting', 'minecraft:smoking'}:
                    used.update(j for j, _ in group)
                    combined = recipe_html(recipe)
                    device = 'かまど' if recipe['type'] == 'minecraft:smelting' else '燻製器'
                    combined = combined.replace('を' + device + 'で精錬する。', 'をかまど・燻製器で精錬する。')
                    recipe_parts.append(combined)
                    continue
            recipe_parts.append(recipe_html(recipe))
        details = ''.join(recipe_parts) or '<p>このバージョンには作成レシピがありません。</p>'
        nutrition_cell=f'<span class="hunger-value">{hunger_icons}<span>{item["nutrition"]}</span></span>'
        saturation_cell=f'{recovery:g}'
        time_cell=f'{item["consume_seconds"]:g}秒'
        if not item['edible']:
            nutrition_cell='食べられません'
            saturation_cell=time_cell='—'
            effect='—'
            recovery=0
        rows.append(f'''<tr data-nutrition="{item['nutrition'] if item['edible'] else 0}" data-saturation="{recovery}" data-time="{item['consume_seconds'] if item['edible'] else 0}" data-effect="{str(item['edible'] and item['effect'] != 'なし').lower()}">
<td><img src="{image}" alt="" width="{width * 2}" height="{height * 2}"><strong>{esc(item['ja_name'])}</strong><small>{esc(item['en_name'])}</small><small><code>{esc(identifier)}</code></small></td><td>{item['stack_size']}</td>
<td>{nutrition_cell}</td><td>{saturation_cell}</td>
<td>{time_cell}</td><td>{esc(effect)}</td>
<td>{details}</td></tr>''')
    page = (root / 'build/food-guide.template.html').read_text(encoding='utf-8')
    for key, value in {'MOD_VERSION': esc(config['mod_version']), 'MINECRAFT_VERSION': esc(config['minecraft_version']),
                       'COUNT': str(len(items)), 'RECIPES': str(sum(len([r for r in recipes if isinstance(r['result'], dict) and r['result'].get('id') == 'culinary_expansion:' + i['name']]) for i in items)),
                       'ROWS': ''.join(rows)}.items():
        page = page.replace('{{' + key + '}}', value)
    return page
