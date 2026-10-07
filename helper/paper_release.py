"""Generate Paper content and validate/package its plugin and resource pack."""
import hashlib
import html
import json
from pathlib import Path
import shutil
import zipfile
import item_project


def input_digest(root, config):
    digest = hashlib.sha256(json.dumps(config, sort_keys=True).encode())
    paths = [root / path for path in ('source/items_project.json', 'helper/paper_release.py',
                                     'helper/item_project.py', 'build/paper/build.gradle',
                                     'build/paper/settings.gradle')]
    for directory in ('source/paper/java', 'source/main/resources'):
        paths.extend(path for path in (root / directory).rglob('*') if path.is_file())
    for path in sorted(paths):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def generate(root, config):
    project = item_project.load(root / 'source/items_project.json')
    enabled = {item['name'] for item in project['items'] if item['enabled']}
    generated = root / ('intermediate/paper-generated' + config.get('output_suffix', ''))
    if generated.exists():
        # Never follow a redirected generated directory outside the working area.
        generated.resolve().relative_to((root / 'intermediate').resolve())
        shutil.rmtree(generated)
    resources = generated / 'resources'
    resources.mkdir(parents=True)
    fingerprint = input_digest(root, config)
    (resources / 'release-inputs.sha256').write_text(fingerprint, encoding='utf-8')
    (resources / 'plugin.yml').write_text(
        'name: CulinaryExpansion\nversion: ' + json.dumps(project['version']) + '\n'
        'main: dev.lotcarnage.culinaryexpansion.paper.CulinaryExpansionPlugin\n'
        'api-version: ' + json.dumps(config['minecraft_version']) + '\n'
        'commands:\n  culinary:\n    description: Give a Culinary Expansion item\n'
        '    permission: culinary.give\npermissions:\n  culinary.give:\n    default: op\n', encoding='utf-8')
    lines = ['package dev.lotcarnage.culinaryexpansion.paper;',
             'import org.bukkit.inventory.*;',
             'final class GeneratedContent { static void register(CulinaryExpansionPlugin p) {']
    quote = lambda value: json.dumps(value, ensure_ascii=True)
    for item in project['items']:
        if item['name'] not in enabled:
            continue
        values = [quote(item['name']), str(item['stack_size']), str(item['nutrition']),
                  str(2 * item['nutrition'] * item['saturation_modifier']) + 'F',
                  str(item['always_edible']).lower(), str(item['consume_seconds']) + 'F',
                  quote(item_project.REMAINDERS[item['remainder']] or ''),
                  quote(item_project.EFFECTS[item['effect']] or ''), str(item['effect_ticks']),
                  str(item['effect_level'] - 1), str(item['effect_probability'])]
        lines.append('p.item(' + ', '.join(values) + ');')
    recipe_root = root / 'source/main/resources/data/culinary_expansion/recipe'
    disabled = {i['name'] for i in project['items']} - enabled
    for path in sorted(recipe_root.glob('*.json')):
        recipe = json.loads(path.read_text(encoding='utf-8'))
        text = json.dumps(recipe)
        if any('"culinary_expansion:' + name + '"' in text for name in disabled):
            continue
        result = recipe['result']
        output = 'p.result(' + quote(result['id'].split(':')[1]) + ', ' + str(result.get('count', 1)) + ')'
        key = 'p.recipeKey(' + quote(path.stem) + ')'
        kind = recipe['type'].split(':')[1]
        lines.append('{')
        if kind == 'crafting_shaped':
            lines.append(f'ShapedRecipe r = new ShapedRecipe({key}, {output});')
            lines.append('r.shape(' + ', '.join(map(quote, recipe['pattern'])) + ');')
            for symbol, ingredient in recipe['key'].items():
                lines.append(f"r.setIngredient('{symbol}', p.ingredient({quote(ingredient)}));")
        elif kind == 'crafting_shapeless':
            lines.append(f'ShapelessRecipe r = new ShapelessRecipe({key}, {output});')
            for ingredient in recipe['ingredients']:
                lines.append('r.addIngredient(p.ingredient(' + quote(ingredient) + '));')
        else:
            classes = {'smelting': 'FurnaceRecipe', 'smoking': 'SmokingRecipe',
                       'blasting': 'BlastingRecipe', 'campfire_cooking': 'CampfireRecipe'}
            if kind not in classes:
                raise ValueError('Unsupported Paper recipe: ' + kind)
            lines.append(f"{classes[kind]} r = new {classes[kind]}({key}, {output}, "
                         f"p.ingredient({quote(recipe['ingredient'])}), {recipe['experience']}F, {recipe['cookingtime']});")
        lines.extend(['p.recipe(r);', '}'])
    lines.append('} }')
    java = generated / 'java/dev/lotcarnage/culinaryexpansion/paper/GeneratedContent.java'
    java.parent.mkdir(parents=True)
    java.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    pack = root / ('intermediate/paper-generated' + config.get('output_suffix', '')) / pack_name(config)
    pack.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(pack, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('release-inputs.sha256', fingerprint)
        source = root / 'source/main/resources'
        archive.write(source / 'pack.mcmeta', 'pack.mcmeta')
        for path in sorted((source / 'assets').rglob('*')):
            if not path.is_file():
                continue
            if path.parent.name in ('item', 'items') and path.stem not in enabled:
                continue
            if path.parent.name == 'lang':
                translations = json.loads(path.read_text(encoding='utf-8'))
                translations = {k: v for k, v in translations.items() if k.split('.')[-1] in enabled}
                archive.writestr(path.relative_to(source).as_posix(), json.dumps(translations, ensure_ascii=False))
            else:
                archive.write(path, path.relative_to(source).as_posix())


def jar_name(config):
    return f"culinary-expansion-paper-{config['minecraft_version']}-{config['mod_version']}.jar"


def pack_name(config):
    return f"culinary-expansion-paper-resources-{config['minecraft_version']}-{config['mod_version']}.zip"


def prepare(root, config):
    jar = root / ('intermediate/paper-output' + config.get('output_suffix', '')) / 'libs' / jar_name(config)
    pack = root / ('intermediate/paper-generated' + config.get('output_suffix', '')) / pack_name(config)
    with zipfile.ZipFile(jar) as archive:
        for entry in ('dev/lotcarnage/culinaryexpansion/paper/CulinaryExpansionPlugin.class',
                      'dev/lotcarnage/culinaryexpansion/paper/GeneratedContent.class', 'plugin.yml',
                      'release-inputs.sha256'):
            if entry not in archive.namelist():
                raise ValueError('Incomplete Paper JAR: ' + entry)
        if archive.read('release-inputs.sha256').decode() != input_digest(root, config):
            raise ValueError('Outdated Paper JAR; rebuild required')
        for entry in ('dev/lotcarnage/culinaryexpansion/paper/CulinaryExpansionPlugin.class',
                      'dev/lotcarnage/culinaryexpansion/paper/GeneratedContent.class'):
            if not archive.read(entry).startswith(b'\xca\xfe\xba\xbe'):
                raise ValueError('Invalid Paper class: ' + entry)
        if archive.testzip():
            raise ValueError('Corrupt Paper JAR')
    with zipfile.ZipFile(pack) as archive:
        if not {'pack.mcmeta', 'release-inputs.sha256'} <= set(archive.namelist()) or archive.testzip():
            raise ValueError('Invalid Paper resource pack')
        if archive.read('release-inputs.sha256').decode() != input_digest(root, config):
            raise ValueError('Outdated Paper resource pack; rebuild required')
    return [jar, pack]


def publish(root, config, artifacts):
    import generate_food_guide
    guide = generate_food_guide.render(config, root)
    downloads = root / 'deliverables/downloads'
    downloads.mkdir(parents=True, exist_ok=True)
    links = []
    for artifact in artifacts:
        digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
        shutil.copyfile(artifact, downloads / artifact.name)
        (downloads / (artifact.name + '.sha256')).write_text(f'{digest}  {artifact.name}\n', encoding='utf-8')
        print(f'Paper distribution: {downloads / artifact.name}')
        name = html.escape(artifact.name)
        label = 'プラグインJAR' if artifact.suffix == '.jar' else 'リソースパックZIP'
        links.append(f'<div class="artifact">\n'
                     f'  <a class="button" href="downloads/{name}" download>{label}をダウンロード（v{html.escape(config["mod_version"])}）</a>\n'
                     f'  <p class="small">{name} · {artifact.stat().st_size / 1024:.1f} KB</p>\n'
                     '  <details>\n    <summary>ハッシュ値（SHA-256）</summary>\n'
                     f'    <code class="hash">{digest}</code>\n'
                     f'    <p><a href="downloads/{name}.sha256" download>ハッシュ値ファイルをダウンロード</a></p>\n'
                     '  </details>\n</div>')
    content = ('<section class="card" id="paper" aria-labelledby="paper-title">\n'
               '  <h3 id="paper-title" style="margin-top:0">PaperMC版</h3>\n'
               '  <div class="badges">\n'
               f'    <span class="badge">Minecraft {html.escape(config["minecraft_version"])}</span>\n'
               '    <span class="badge">PaperMC</span>\n'
               '  </div>\n' +
               '\n'.join(links) + '\n'
               '  <details class="install-guide" style="margin-top:24px">\n'
               '  <summary>導入方法</summary>\n'
               '  <ol>\n'
               f'    <li>Java 25を使用するPaperMC {html.escape(config["minecraft_version"])}サーバーを用意します。</li>\n'
               '    <li>JARをサーバーの<code>plugins</code>に入れて再起動します。</li>\n'
               '    <li>リソースパックZIPを参加者の<code>resourcepacks</code>に入れて有効にします。</li>\n'
               '  </ol>\n'
               '  <p class="small">リソースパックはserver.propertiesのresource-pack URLでも配布できます。'
               '管理者は<code>/culinary アイテムID</code>で料理を取得できます。'
               'Forge版とはアイテムの保存形式が異なります。</p>\n'
               '  </details>\n</section>')
    page = root / 'deliverables/index.html'
    section = '<!-- PAPER START -->\n' + content + '\n<!-- PAPER END -->'
    if page.exists():
        text = page.read_text(encoding='utf-8')
        import re
        pattern = r'<!-- PAPER START -->.*?<!-- PAPER END -->'
        if re.search(pattern, text, flags=re.S):
            text = re.sub(pattern, lambda match: section, text, flags=re.S)
        elif '<!-- PAPER SLOT -->' in text:
            text = text.replace('<!-- PAPER SLOT -->', section)
        else:
            text = text.replace('<footer>', section + '\n<footer>')
        text = '\n'.join(line.rstrip() for line in text.split('\n'))
    else:
        text = '<!doctype html><html lang="ja"><meta charset="utf-8"><title>Culinary Expansion</title><main>' + section + '<footer></footer></main></html>'
    page.write_text(text, encoding='utf-8')
    (root / 'deliverables/foods.html').write_text(guide, encoding='utf-8')
    (root / '.nojekyll').write_text('', encoding='utf-8')

