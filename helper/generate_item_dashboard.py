"""Generate a standalone item dashboard from Java registrations and resource JSON."""
import argparse
import base64
import html
import json
import os
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent
RESOURCES = ROOT / 'source/main/resources'


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def registrations():
    """Inspect literal ITEMS.register calls; do not execute or fully parse Java."""
    for path in sorted((ROOT / 'source/main/java').rglob('*.java')):
        text = path.read_text(encoding='utf-8-sig')
        namespace = re.search(r'String\s+MOD_ID\s*=\s*"([a-z0-9_]+)"', text)
        if not namespace:
            continue
        # Comments are removed so commented-out registrations do not become rows.
        code = re.sub(r'/\*.*?\*/|//[^\n]*', '', text, flags=re.S)
        for match in re.finditer(r'ITEMS\.register\(\s*"([a-z0-9_/]+)"', code):
            start = code.index('(', match.start())
            depth, quoted, escaped = 0, False, False
            for end in range(start, len(code)):
                char = code[end]
                if quoted:
                    if escaped:
                        escaped = False
                    elif char == '\\':
                        escaped = True
                    elif char == '"':
                        quoted = False
                elif char == '"':
                    quoted = True
                elif char == '(':
                    depth += 1
                elif char == ')':
                    depth -= 1
                    if depth == 0:
                        break
            yield namespace.group(1) + ':' + match.group(1), code[start:end + 1], path


def generate(output):
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    def esc(value):
        return html.escape(str(value), quote=True)

    def link(path, label=None):
        relative = Path(os.path.relpath(path, output.parent)).as_posix()
        return f'<a href="{esc(relative)}">{esc(label if label is not None else path.name)}</a>'

    def asset_path(identifier, folder):
        namespace, name = identifier.split(':', 1)
        return RESOURCES / 'assets' / namespace / folder / (name + '.json')

    recipes = []
    for path in sorted((RESOURCES / 'data').glob('*/recipe/**/*.json')):
        recipes.append((path, read_json(path)))

    rows, seen = [], set()
    extra_attributes = {}
    recipe_rows, ingredient_rows, texture_rows, issue_rows = [], [], [], []
    for identifier, expression, java in registrations():
        if identifier in seen:
            raise ValueError(f'アイテムIDが重複しています: {identifier}')
        seen.add(identifier)
        namespace, name = identifier.split(':', 1)
        key = f'item.{namespace}.{name.replace("/", ".")}'
        names = []
        warnings = []
        for language in ('ja_jp', 'en_us'):
            path = RESOURCES / 'assets' / namespace / 'lang' / (language + '.json')
            value = read_json(path).get(key) if path.exists() else None
            names.append(value or '未定義')
            if not value:
                warnings.append(language + ' 翻訳なし')
        direct = bool(re.search(r'new\s+Item\s*\(', expression))

        def numeric(method):
            match = re.search(r'\.' + method + r'\(\s*(\d+(?:\.\d+)?)[fFdD]?\s*\)', expression)
            return float(match.group(1)) if match else None

        stack = numeric('stacksTo')
        if stack is not None:
            stack_text = f'{stack:g}'
        elif direct and '.durability(' not in expression and '.component(' not in expression:
            stack_text = '64'
        else:
            stack_text = '要確認'
            warnings.append('スタック数をソースで確認')
        nutrition, saturation = numeric('nutrition'), numeric('saturationModifier')
        food = '.food(' in expression
        food_known = food and nutrition is not None and saturation is not None
        nutrition_cell = f'{nutrition:g}' if nutrition is not None else '未解析'
        saturation_cell = f'{saturation:g}' if saturation is not None else '未解析'
        recovery_cell = f'{nutrition * saturation * 2:g}' if food_known else '未解析'
        always_cell = ('可' if '.alwaysEdible(' in expression else '不可') if food_known else '未解析'
        action_cell = '食事' if food_known and direct else '未解析'
        if not food_known or not direct or '.component(' in expression:
            warnings.append('使用効果をソースで確認')

        effect = re.search(r'MobEffects\.([A-Z_]+),\s*(\d+),\s*(\d+)\),\s*([0-9.]+)F', expression)
        remainder = re.search(r'usingConvertsTo\(Items\.([A-Z_]+)\)', expression)
        effect_names = {'SPEED':'移動速度上昇','REGENERATION':'再生能力','FIRE_RESISTANCE':'耐火','NIGHT_VISION':'暗視','STRENGTH':'攻撃力上昇','POISON':'毒','HUNGER':'空腹','WITHER':'衰弱'}
        extra_attributes[identifier] = [str(numeric('consumeSeconds') or 1.6),
            effect_names.get(effect[1], effect[1]) if effect else 'なし', effect[2] if effect else '不要',
            str(int(effect[3])+1) if effect else '不要', effect[4] if effect else '不要',
            {'BOWL':'ボウル','GLASS_BOTTLE':'ガラス瓶','BUCKET':'バケツ'}.get(remainder[1], remainder[1]) if remainder else 'なし']
        recipe_cells, recipe_paths = [], []
        for path, recipe in recipes:
            result = recipe.get('result', {})
            result_id = result.get('id') if isinstance(result, dict) else result
            if result_id != identifier:
                continue
            recipe_paths.append(link(path))
            kind = recipe.get('type', '未指定')
            label = {'minecraft:smelting': 'かまど', 'minecraft:smoking': '燻製器',
                     'minecraft:crafting_shaped': '定形クラフト',
                     'minecraft:crafting_shapeless': '不定形クラフト'}.get(kind, kind)
            count = result.get('count', 1) if isinstance(result, dict) else 1
            relative = path.relative_to(RESOURCES / 'data')
            recipe_id = relative.parts[0] + ':' + Path(*relative.parts[2:]).with_suffix('').as_posix()
            ticks = recipe.get('cookingtime')
            recipe_rows.append([esc(identifier), esc(recipe_id), esc(kind), esc(label), str(count),
                                str(ticks) if ticks is not None else '該当なし',
                                f'{ticks / 20:g}' if ticks is not None else '該当なし',
                                esc(recipe.get('experience', '該当なし')), link(path)])
            recipe_cells.append(recipe_id)
            def add_ingredient(slot, ingredient):
                if isinstance(ingredient, list):
                    for option in ingredient:
                        add_ingredient(slot, option)
                    return
                kind, reference = '未解析', '未解析'
                if isinstance(ingredient, str):
                    kind = 'タグ' if ingredient.startswith('#') else 'アイテム'
                    reference = ingredient.lstrip('#')
                elif isinstance(ingredient, dict):
                    if 'item' in ingredient:
                        kind, reference = 'アイテム', ingredient['item']
                    elif 'tag' in ingredient:
                        kind, reference = 'タグ', ingredient['tag']
                ingredient_rows.append([esc(identifier), esc(recipe_id), esc(slot), esc(kind), esc(reference), '1'])
            if 'ingredient' in recipe:
                add_ingredient('1', recipe['ingredient'])
            for slot, ingredient in enumerate(recipe.get('ingredients', []), 1):
                add_ingredient(str(slot), ingredient)
            for y, pattern_row in enumerate(recipe.get('pattern', []), 1):
                for x, symbol in enumerate(pattern_row, 1):
                    if symbol != ' ':
                        add_ingredient(f'{y}:{x}', recipe.get('key', {}).get(symbol))


        if not recipe_cells:
            warnings.append('出力レシピなし（独自形式は要確認）')

        texture_cells, resource_links = [], []
        definition = asset_path(identifier, 'items')
        if definition.exists():
            resource_links.append(link(definition))
            model = read_json(definition).get('model', {})
            model_id = model.get('model') if model.get('type') == 'minecraft:model' else None
        else:
            model_id = None
        if model_id:
            model_path = asset_path(model_id, 'models')
            if model_path.exists():
                resource_links.append(link(model_path))
                for layer, texture_id in read_json(model_path).get('textures', {}).items():
                    if ':' not in texture_id:
                        continue
                    tex_namespace, tex_name = texture_id.split(':', 1)
                    texture = RESOURCES / 'assets' / tex_namespace / 'textures' / (tex_name + '.png')
                    if texture.exists():
                        encoded = base64.b64encode(texture.read_bytes()).decode('ascii')
                        image = f'<img src="data:image/png;base64,{encoded}" alt="{esc(texture_id)}">'
                        texture_cells.append(image)
                        data = texture.read_bytes()
                        width = int.from_bytes(data[16:20], 'big')
                        height = int.from_bytes(data[20:24], 'big')
                        texture_rows.append([esc(identifier), esc(layer), esc(texture_id), esc(texture.name),
                                             image, str(width), str(height), link(texture, texture.name)])

                    else:
                        warnings.append('テクスチャなし: ' + texture_id)
        if not texture_cells:
            warnings.append('表示定義・モデル・テクスチャを確認')
        if not direct:
            warnings.append('独自アイテムクラス／ファクトリー: 自動解析範囲外')
        definition_cell = link(definition) if definition.exists() else 'なし'
        model_cell = link(model_path) if model_id and model_path.exists() else 'なし'
        cells = [esc(identifier), esc(names[0]), esc(names[1]), stack_text, action_cell,
                 nutrition_cell, saturation_cell, recovery_cell, always_cell,
                 esc(model_id or '未解析'), link(java), definition_cell, model_cell]
        rows.append(cells)
        for warning in warnings:
            issue_rows.append([esc(identifier), esc(warning)])

    if not rows:
        raise ValueError('MOD_IDを指定したアイテム登録が見つかりません。先に定義へ反映してください。')
    def table(title, columns, data):
        heads = ''.join('<th scope="col">' + esc(c) + '</th>' for c in columns)
        body = ''.join('<tr>' + ''.join('<td>' + cell + '</td>' for cell in row) + '</tr>' for row in data)
        return f'<section><h2>{esc(title)}</h2><p class="count" aria-live="polite"></p><div class="scroll"><table><thead><tr>{heads}</tr></thead><tbody>{body}</tbody></table></div></section>'
    def grouped(data):
        result = {}
        for row in data:
            result.setdefault(row[0], []).append(row)
        return result
    recipe_groups = grouped(recipe_rows)
    texture_groups = grouped(texture_rows)
    issue_groups = grouped(issue_rows)
    max_recipes = max((len(v) for v in recipe_groups.values()), default=0)
    max_textures = max((len(v) for v in texture_groups.values()), default=0)
    max_issues = max((len(v) for v in issue_groups.values()), default=0)
    ingredient_counts = {}
    for ingredient in ingredient_rows:
        key = (ingredient[0], ingredient[1])
        ingredient_counts[key] = ingredient_counts.get(key, 0) + 1
    max_ingredients = max(ingredient_counts.values(), default=0)
    crafting_types = {'minecraft:crafting_shaped', 'minecraft:crafting_shapeless'}
    max_crafts = max(1, max((sum(r[2] in crafting_types for r in group) for group in recipe_groups.values()), default=0))
    columns = ['アイテムID', '日本語名', '英語名', '最大スタック数', '使用動作', '満腹度回復量',
               '隠し満腹度係数', '隠し満腹度最大回復量', '満腹時使用']
    columns.extend(['食事時間（秒）','追加効果','効果時間（tick）','効果レベル','効果発生確率','使用後の残り物'])
    columns.extend(['かまど対応', '燻製器対応', '焚き火（tick）', '基準調理時間（tick）', '調理経験値', '出力個数'])
    ingredient_columns = ['スロット', '参照種別', '材料ID', '必要数']
    texture_columns = ['画像']
    for j in range(max_ingredients):
        columns.extend(f'材料{j + 1}・{c}' for c in ingredient_columns)
    craft_slots = [f'{row}:{column}' for row in range(1, 4) for column in range(1, 4)]
    for i in range(max_crafts):
        prefix = 'クラフト' if max_crafts == 1 else f'クラフト{i + 1}'
        columns.extend([f'{prefix}方式', f'{prefix}出力個数'])
        columns.extend(f'{prefix}素材 {slot}' for slot in craft_slots)
    for i in range(max_textures):
        columns.extend(f'テクスチャ{i + 1}・{c}' for c in texture_columns)
    flattened = []
    for item in rows:
        identifier = item[0]
        cells = item[:9] + extra_attributes[identifier]
        item_recipes = recipe_groups.get(identifier, [])
        craft_recipes = [r for r in item_recipes if r[2] in crafting_types]
        cooking_recipes = [r for r in item_recipes if r[2] not in crafting_types]
        by_type = {}
        for recipe in cooking_recipes:
            if recipe[2] in by_type:
                raise ValueError(f'{identifier}に同じ調理方式のレシピが複数あり、一覧にまとめられません。')
            by_type[recipe[2]] = recipe
        smelt = by_type.get('minecraft:smelting')
        smoke = by_type.get('minecraft:smoking')
        campfire = by_type.get('minecraft:campfire_cooking')
        unsupported = set(by_type) - {'minecraft:smelting', 'minecraft:smoking', 'minecraft:campfire_cooking'}
        if unsupported:
            raise ValueError(f'一覧表示に対応していない調理方式です: {unsupported}')
        primary = smelt or smoke or campfire
        base = smelt or smoke
        for recipe in cooking_recipes:
            if primary and recipe[4] != primary[4]:
                raise ValueError(f'{identifier}の調理レシピの出力個数が異なるため、一覧にまとめられません。')
            if primary and recipe[7] != primary[7]:
                raise ValueError(f'{identifier}の調理レシピの経験値が異なるため、一覧にまとめられません。')
        if smelt and smoke and smelt[5] != smoke[5]:
            raise ValueError(f'{identifier}のかまどと燻製器の基準時間が異なります。レシピ定義を確認してください。')
        cells.extend(['可' if smelt else '不可', '可' if smoke else '不可', campfire[5] if campfire else '不可',
                      base[5] if base else '調理不可', primary[7] if primary else '調理不可', primary[4] if primary else '調理不可'])
        materials = [r for r in ingredient_rows if primary and r[0] == identifier and r[1] == primary[1]]
        for recipe in cooking_recipes:
            other = [r[2:] for r in ingredient_rows if r[0] == identifier and r[1] == recipe[1]]
            if other != [r[2:] for r in materials]:
                raise ValueError(f'{identifier}の調理レシピの素材が異なるため、一覧にまとめられません。')
        for j in range(max_ingredients):
            cells.extend(materials[j][2:] if j < len(materials) else ['不要'] * len(ingredient_columns))
        for i in range(max_crafts):
            craft = craft_recipes[i] if i < len(craft_recipes) else None
            if not craft:
                cells.extend(['クラフト不可', '不可'] + ['不可'] * 9)
                continue
            shaped = craft[2] == 'minecraft:crafting_shaped'
            cells.extend(['定型' if shaped else '不定形', craft[4]])
            craft_materials = [r for r in ingredient_rows if r[0] == identifier and r[1] == craft[1]]
            slots = {}
            for material in craft_materials:
                if shaped:
                    slot = material[2]
                    if slot not in craft_slots:
                        raise ValueError(f'クラフト素材の位置が3×3の範囲外です: {slot}')
                else:
                    index = int(material[2]) - 1
                    if not 0 <= index < 9:
                        raise ValueError('不定形レシピの素材数が9個を超えています。')
                    slot = craft_slots[index]
                if slot in slots:
                    raise ValueError(f'素材欄{slot}に複数の候補があります。素材タグを指定してください。')
                slots[slot] = ('#' if material[3] == 'タグ' else '') + material[4]
            cells.extend(slots.get(slot, '不要') for slot in craft_slots)
        item_textures = texture_groups.get(identifier, [])
        for i in range(max_textures):
            cells.append(item_textures[i][4] if i < len(item_textures) else 'なし')
        flattened.append(cells)
    metadata_columns = ['アイテムID', '日本語名', 'モデルID', 'Javaソース', '表示定義ファイル', 'モデルファイル']
    for i in range(max_recipes):
        metadata_columns.extend(f'レシピ{i + 1}・{c}' for c in ['ID', '種別ID', 'ファイル'])
    for i in range(max_textures):
        metadata_columns.extend(f'テクスチャ{i + 1}・{c}' for c in ['レイヤー', 'ID', '画像名', '幅（px）', '高さ（px）', 'ファイル'])
    metadata_columns.extend(f'確認事項{i + 1}' for i in range(max_issues))
    metadata_rows = []
    for item in rows:
        identifier = item[0]
        cells = [item[0], item[1], *item[9:13]]
        item_recipes = recipe_groups.get(identifier, [])
        for i in range(max_recipes):
            cells.extend([item_recipes[i][1], item_recipes[i][2], item_recipes[i][8]] if i < len(item_recipes) else ['なし'] * 3)
        item_textures = texture_groups.get(identifier, [])
        for i in range(max_textures):
            tex = item_textures[i] if i < len(item_textures) else None
            cells.extend([tex[1], tex[2], tex[3], tex[5], tex[6], tex[7]] if tex else ['なし'] * 6)
        item_issues = issue_groups.get(identifier, [])
        cells.extend(item_issues[i][1] if i < len(item_issues) else 'なし' for i in range(max_issues))
        metadata_rows.append(cells)
    metadata_table = table('リソース管理一覧（1行＝1アイテム）', metadata_columns, metadata_rows)
    # Put texture previews directly after the item ID, before display names.
    image_indices = [i for i, column in enumerate(columns) if column.startswith('テクスチャ') and column.endswith('・画像')]
    order = [0] + image_indices + [i for i in range(1, len(columns)) if i not in image_indices]
    columns = [columns[i] for i in order]
    flattened = [[row[i] for i in order] for row in flattened]
    tables = table('アイテム一覧（1行＝1アイテム）', columns, flattened)
    page = '''<!doctype html><html lang="ja"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>追加アイテム一覧</title>
<style>body{font:13px/1.5 system-ui,sans-serif;background:#f6f8fa;color:#17212b;margin:24px}
h1{margin-bottom:8px}a{color:#1753a0}input{padding:10px;width:min(500px,90%);margin:16px 0}
.scroll{overflow:auto;max-height:75vh;border:1px solid #bcc8d4}table{border-collapse:collapse;background:white;width:max-content;min-width:0;table-layout:auto}
th,td{padding:1px 2px;border:1px solid #d6dee5;vertical-align:middle;text-align:left;white-space:nowrap}th{background:#e3ebf2;position:sticky;top:0;z-index:1;writing-mode:vertical-rl;text-orientation:upright;height:auto;white-space:nowrap;line-height:1.05}
th:first-child,td:first-child{position:sticky;left:0;background:#edf2f7;z-index:2}th:first-child{z-index:3}td:first-child{font-weight:600}tr:nth-child(even){background:#f8fafc}img{display:block;width:32px;height:32px;image-rendering:pixelated;background:#e8ecef}
pre{font-size:12px;white-space:pre-wrap;min-width:220px}code,a{white-space:nowrap}hr{border:0;border-top:1px solid #d6dee5;margin:16px 0}</style>
<h1>追加アイテム一覧</h1><p>Java登録・翻訳・レシピ・モデルから生成する開発用ダッシュボード。各列は単一属性です。調理方法は固定列に表示し、焚き火は対応時のみtick数を表示します。基準調理時間はレシピ定義の時間です（燻製器は通常2倍速）。</p>
<p>解析対象はMOD_IDとITEMS.registerの文字列リテラル、直接指定されたItem.Propertiesです。
独自クラス、変数・メソッド経由の属性、動的レシピ、複合モデルはソース確認が必要です。
隠し満腹度の実回復量は食事後の満腹度が上限になります。画像は埋め込み済みでオフライン表示できます。クラフト素材は行:列の順（1:1～3:3）。定型は左上に配置し、不定形は順序を問わない材料を順に表示します。空きマスは「不要」、クラフト不可は「不可」です。</p>
<label>絞り込み（名前・ID・材料・属性）<br><input id="filter" type="search" placeholder="例: fried_egg、minecraft:egg、燻製器"></label>
TABLES
<script>const sections=[...document.querySelectorAll('section')],input=document.querySelector('#filter');
function filter(){const q=input.value.trim().toLowerCase();const matched=new Set();for(const r of sections[0].querySelectorAll('tbody tr'))if(r.textContent.toLowerCase().includes(q))matched.add(r.cells[0].textContent);
for(const section of sections){const rows=[...section.querySelectorAll('tbody tr')];let n=0;for(const row of rows){row.hidden=!(row.textContent.toLowerCase().includes(q)||matched.has(row.cells[0].textContent));if(!row.hidden)n++;}section.querySelector('.count').textContent=`表示 ${n} / 全 ${rows.length} 行`;}}
input.addEventListener('input',filter);filter();</script></html>'''
    metadata_output = output.with_name('resource_dashboard.html')
    if metadata_output == output:
        raise ValueError('アイテム一覧の保存先はリソース管理一覧と別にしてください。')
    metadata_page = page.replace('追加アイテム一覧', 'リソース管理一覧')
    metadata_page = metadata_page.replace('TABLES', metadata_table)
    metadata_page = re.sub(r'<h1>リソース管理一覧</h1><p>.*?</p>', '<h1>リソース管理一覧</h1><p>Javaソース・表示定義・モデル・レシピ・テクスチャの管理用メタ情報。1アイテム1行、各列は単一属性です。</p>', metadata_page, count=1, flags=re.S)
    metadata_page = metadata_page.replace('<label>絞り込み', '<p><a href="' + esc(output.name) + '">アイテム比較一覧</a></p><label>絞り込み')
    page = page.replace('TABLES', tables)
    page = page.replace('<label>絞り込み', '<p><a href="resource_dashboard.html">リソース管理一覧</a></p><label>絞り込み')
    output.write_text(page, encoding='utf-8')
    metadata_output.write_text(metadata_page, encoding='utf-8')
    print(f'Resource metadata: {metadata_output}')
    print(f'Generated {len(rows)} items: {output}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'document/item_dashboard.html')
    generate(parser.parse_args().output)
