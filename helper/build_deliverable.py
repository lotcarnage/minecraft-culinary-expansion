"""Build the deliverables directory with the Gradle-built mod, checksums, and download page."""
import argparse
import hashlib
import html
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parent.parent


def properties(minecraft_version=None):
    values = {}
    for line in (ROOT / 'build/gradle.properties').read_text(encoding='utf-8-sig').splitlines():
        line = line.strip()
        if line and not line.startswith(('#', '!')) and '=' in line:
            key, value = line.split('=', 1)
            values[key.strip()] = value.strip()
    import item_project
    values['mod_version'] = item_project.load(ROOT / 'source/items_project.json')['version']
    if minecraft_version and minecraft_version != values['minecraft_version']:
        versions = json.loads((ROOT / 'build/legacy-versions.json').read_text(encoding='utf-8-sig'))
        if minecraft_version not in versions:
            raise ValueError('Unsupported Minecraft version: ' + minecraft_version)
        values.update(versions[minecraft_version])
        values['minecraft_version'] = minecraft_version
        values['output_suffix'] = '-' + minecraft_version
    return values


def validate_recipe_category(recipe, name):
    kind = recipe.get('type')
    if kind in ('minecraft:crafting_shaped', 'minecraft:crafting_shapeless'):
        allowed = {'building', 'redstone', 'equipment', 'misc'}
    elif kind in ('minecraft:smelting', 'minecraft:smoking', 'minecraft:campfire_cooking', 'minecraft:blasting'):
        allowed = {'food', 'blocks', 'misc'}
    else:
        return
    if recipe.get('category', 'misc') not in allowed:
        raise ValueError(f'Invalid recipe category in {name}: {recipe.get("category")}')


def validate_mod_archive(artifact, config=None):
    """Reject incomplete archives before copying them to the public directory."""
    java_root = ROOT / 'source/main/java'
    resources_root = ROOT / 'source/main/resources'
    project_path = ROOT / 'source/items_project.json'
    disabled = {item['name'] for item in json.loads(project_path.read_text(encoding='utf-8-sig'))['items']
                if not item.get('enabled', item['nutrition'] > 0)} if project_path.exists() else set()
    recipe_root = resources_root / 'data/culinary_expansion/recipe'
    excluded_recipes = {'culinary_expansion:' + path.relative_to(recipe_root).with_suffix('').as_posix()
                        for path in recipe_root.rglob('*.json')
                        if any('"culinary_expansion:' + name + '"' in path.read_text(encoding='utf-8') for name in disabled)}
    def included(path):
        relative = path.relative_to(resources_root).as_posix()
        if relative.startswith(('assets/culinary_expansion/items/', 'assets/culinary_expansion/models/item/',
                                'assets/culinary_expansion/textures/item/')):
            return path.stem not in disabled
        if relative.startswith(('data/culinary_expansion/recipe/', 'data/culinary_expansion/advancement/recipes/food/')) and path.suffix == '.json':
            text = path.read_text(encoding='utf-8')
            return not (any('"culinary_expansion:' + name + '"' in text for name in disabled) or
                        (relative.startswith('data/culinary_expansion/advancement/recipes/food/') and
                         any('"' + recipe + '"' in text for recipe in excluded_recipes)))
        return True
    resource_files = [path for path in resources_root.rglob('*') if path.is_file() and included(path)]
    required = {'META-INF/mods.toml', 'dev/lotcarnage/culinaryexpansion/CulinaryExpansion.class'}
    required.update(path.relative_to(java_root).with_suffix('.class').as_posix()
                    for path in java_root.rglob('*.java'))
    required.update(path.relative_to(resources_root).as_posix()
                    for path in resource_files)
    try:
        with zipfile.ZipFile(artifact) as archive:
            excluded = {path.relative_to(resources_root).as_posix() for path in resources_root.rglob('*')
                        if path.is_file() and not included(path)}
            unwanted = excluded & set(archive.namelist())
            if unwanted:
                raise ValueError('Disabled item resources in mod JAR: ' + ', '.join(sorted(unwanted)))
            missing = required - set(archive.namelist())
            if missing:
                raise ValueError('Incomplete mod JAR; missing: ' + ', '.join(sorted(missing)))
            def expected(path):
                data = path.read_bytes()
                if path.name == 'mods.toml':
                    active = config or properties()
                    data = data.replace(b'${mod_version}', active['mod_version'].encode())
                    if active.get('minecraft_version') == '26.2':
                        data = data.replace(b'[66,)', b'[65,)').replace(b'[66.0.5,67)',
                            ('[' + active['forge_version'] + ',66)').encode()).replace(b'[26.3,26.4)', b'[26.2,26.3)')
                return data
            stale = [path.relative_to(resources_root).as_posix()
                     for path in resource_files
                     if archive.read(path.relative_to(resources_root).as_posix()) !=
                     expected(path)]
            if stale:
                raise ValueError('Outdated mod JAR resources; rebuild required: ' + ', '.join(sorted(stale)))
            corrupt = archive.testzip()
            if corrupt:
                raise ValueError(f'Corrupt mod JAR entry: {corrupt}')
            for name in archive.namelist():
                if name.startswith('data/culinary_expansion/recipe/') and name.endswith('.json'):
                    validate_recipe_category(json.loads(archive.read(name)), name)
            validate_recipe_references(archive)
            entry = archive.read('dev/lotcarnage/culinaryexpansion/CulinaryExpansion.class')
            if not entry.startswith(b'\xca\xfe\xba\xbe') or b'Lnet/minecraftforge/fml/common/Mod;' not in entry or b'culinary_expansion' not in entry:
                raise ValueError('Mod entry class is missing its Forge @Mod declaration')
    except zipfile.BadZipFile as error:
        raise ValueError('Invalid mod JAR') from error


def validate_recipe_references(archive):
    """Advancements must not bind a mod recipe that is absent from the archive."""
    names=set(archive.namelist())
    for name in names:
        if not name.startswith('data/culinary_expansion/advancement/') or not name.endswith('.json'):continue
        advancement=json.loads(archive.read(name))
        references=list(advancement.get('rewards',{}).get('recipes',[]))
        for criterion in advancement.get('criteria',{}).values():
            if criterion.get('trigger')=='minecraft:recipe_unlocked':
                value=criterion.get('conditions',{}).get('recipes',[])
                references.extend([value] if isinstance(value,str) else value)
        for reference in references:
            if reference.startswith('culinary_expansion:'):
                path='data/culinary_expansion/recipe/'+reference.split(':',1)[1]+'.json'
                if path not in names:raise ValueError(f'Missing recipe {reference} referenced by {name}')


def prepare_pages():
    config = properties()
    name = f"culinary-expansion-{config['minecraft_version']}-{config['mod_version']}.jar"
    artifact = ROOT / 'intermediate/gradle-output/libs' / name
    validate_mod_archive(artifact)
    import generate_food_guide
    guide = generate_food_guide.render(config, ROOT)
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    checksum = f'{digest}  {name}\n'
    template = (ROOT / 'build/download-page.template.html').read_text(encoding='utf-8-sig')
    tokens = {
        'MINECRAFT_VERSION': config['minecraft_version'],
        'FORGE_VERSION': config['forge_version'],
        'MOD_VERSION': config['mod_version'],
        'JAR_NAME': name,
        'JAR_SIZE': f'{artifact.stat().st_size / 1024:.1f}',
        'SHA256': digest,
    }
    for key, value in tokens.items():
        template = template.replace('{{' + key + '}}', html.escape(value, quote=True))
    existing_page = ROOT / 'deliverables/index.html'
    if existing_page.exists():
        paper_section = re.search(r'<!-- PAPER START -->.*?<!-- PAPER END -->',
                                  existing_page.read_text(encoding='utf-8'), re.S)
        if paper_section:
            template = template.replace('<!-- PAPER SLOT -->', paper_section.group())
    if re.search(r'\{\{[A-Z_]+\}\}', template):
        raise ValueError('Unresolved page template token.')
    downloads = ROOT / 'deliverables/downloads'
    assets = ROOT / 'deliverables/assets'
    downloads.mkdir(parents=True, exist_ok=True)
    assets.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(artifact, downloads / name)
    shutil.copyfile(ROOT / 'source/main/resources/assets/culinary_expansion/textures/item/fried_egg.png',
                    assets / 'fried_egg.png')
    (downloads / (name + '.sha256')).write_text(checksum, encoding='utf-8')
    (ROOT / 'deliverables/index.html').write_text(template, encoding='utf-8')
    (ROOT / 'deliverables/foods.html').write_text(guide, encoding='utf-8')
    (ROOT / '.nojekyll').write_text('', encoding='utf-8')
    print(f'Distribution JAR: {downloads / name}')
    print(f'GitHub Pages files: {ROOT / "deliverables"}')


def build(java_home, platform='forge', config=None):
    config = config or properties()
    env = os.environ.copy()
    # Reuse a project-local portable JDK when the Windows PATH still points to Java 8.
    if not java_home and not env.get('JAVA_HOME'):
        candidates = sorted((ROOT / 'intermediate/jdk25').glob('*/bin/javac.exe'))
        if candidates:
            java_home = candidates[-1].parent.parent
    env.setdefault('GRADLE_USER_HOME', str(ROOT / 'intermediate/gradle-user-home'))
    if java_home:
        home = Path(java_home).expanduser().resolve()
        env['JAVA_HOME'] = str(home)
        env['PATH'] = str(home / 'bin') + os.pathsep + env.get('PATH', '')
    elif env.get('JAVA_HOME'):
        env['PATH'] = str(Path(env['JAVA_HOME']) / 'bin') + os.pathsep + env.get('PATH', '')
    for executable in ('java', 'javac'):
        resolved = shutil.which(executable, path=env.get('PATH'))
        if not resolved:
            raise ValueError(f'JDK 25 executable not found: {executable}')
        result = subprocess.run([resolved, '-version'], env=env, capture_output=True, text=True, check=True)
        version = result.stdout + result.stderr
        pattern = r'\b(?:javac\s+|version\s+")25(?:[.\s"-]|$)'
        if not re.search(pattern, version):
            raise ValueError(f'JDK 25 is required; {executable} reports: {version.strip()}')
    # The saved project is the source of truth; never compile stale generated Java.
    import item_project
    project = item_project.load(ROOT / 'source/items_project.json')
    for item in project['items']:
        item_project.ensure_texture(item, ROOT)
    item_project.export(project, ROOT / 'source/items_project.json', ROOT)
    import generate_item_dashboard
    if project['items']:
        generate_item_dashboard.generate(ROOT / 'document/item_dashboard.html')
    command = ([str(ROOT / 'build/gradlew.bat')] if os.name == 'nt'
               else ['sh', str(ROOT / 'build/gradlew')])
    overrides = ['-P' + key + '=' + config[key] for key in
                 ('minecraft_version', 'forge_version', 'paper_api_version', 'output_suffix') if key in config]
    if platform in ('forge', 'all'):
        subprocess.run(command + ['--no-daemon', '--project-dir', str(ROOT / 'build'),
                              '--project-cache-dir', str(ROOT / 'intermediate/gradle-cache'),
                              'clean', 'build'] + overrides, cwd=ROOT, env=env, check=True)
    if platform in ('paper', 'all'):
        import paper_release
        paper_release.generate(ROOT, config)
        subprocess.run(command + ['--no-daemon', '--project-dir', str(ROOT / 'build/paper'),
                                  '--project-cache-dir', str(ROOT / 'intermediate/paper-gradle-cache'),
                                  'clean', 'build'] + overrides, cwd=ROOT, env=env, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--java-home', help='JDK 25 directory (defaults to JAVA_HOME or PATH)')
    parser.add_argument('--pages-only', action='store_true', help='Prepare pages from existing artifacts for the selected Minecraft versions')
    parser.add_argument('--platform', choices=('forge', 'paper', 'all'), default='forge',
                        help='Build/release Forge, Paper, or both (default: forge)')
    parser.add_argument('--minecraft-version', default='all',
                        help='Minecraft target (default: all configured versions)')
    args = parser.parse_args()
    try:
        current = properties()
        legacy_versions = json.loads((ROOT / 'build/legacy-versions.json').read_text(encoding='utf-8-sig'))
        targets = [current['minecraft_version']] + list(legacy_versions) if args.minecraft_version == 'all' else [args.minecraft_version]
        configs = [properties(target) for target in targets]
        if not args.pages_only:
            print('Generating resources and building the mod...', flush=True)
            for config in configs:
                build(args.java_home, args.platform, config)
        import paper_release
        legacy_artifacts = []
        paper_artifacts = None
        for config in configs:
            is_current = config['minecraft_version'] == current['minecraft_version']
            if args.platform in ('forge', 'all'):
                name = f"culinary-expansion-{config['minecraft_version']}-{config['mod_version']}.jar"
                artifact = ROOT / ('intermediate/gradle-output' + config.get('output_suffix', '')) / 'libs' / name
                validate_mod_archive(artifact, config)
                if not is_current:
                    legacy_artifacts.append(artifact)
            if args.platform in ('paper', 'all'):
                artifacts = paper_release.prepare(ROOT, config)
                if is_current:
                    paper_artifacts = artifacts
                else:
                    legacy_artifacts.extend(artifacts)
        if current['minecraft_version'] in targets and args.platform in ('forge', 'all'):
            prepare_pages()
        if paper_artifacts:
            paper_release.publish(ROOT, current, paper_artifacts)
        downloads = ROOT / 'deliverables/downloads'
        downloads.mkdir(parents=True, exist_ok=True)
        for artifact in legacy_artifacts:
            shutil.copyfile(artifact, downloads / artifact.name)
            digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
            (downloads / (artifact.name + '.sha256')).write_text(f'{digest}  {artifact.name}\n', encoding='utf-8')
            print(f'Legacy distribution: {downloads / artifact.name}')
        refresh_legacy_links(current)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f'Build failed: {error}', file=sys.stderr)
        print('Release generation stopped. Existing deliverables may be older; do not use them as this build output.', file=sys.stderr)
        return 1
    print('Release process completed successfully.', flush=True)
    return 0


def refresh_legacy_links(config):
    page = ROOT / 'deliverables/index.html'
    if not page.exists():
        return
    links = []
    pattern = r'culinary-expansion-(?:(paper)(-resources)?-)?(\d+\.\d+(?:\.\d+)?)-(.+)\.(jar|zip)'
    for artifact in sorted((ROOT / 'deliverables/downloads').iterdir()):
        match = re.fullmatch(pattern, artifact.name)
        if not match or match[3] == config['minecraft_version']:
            continue
        checksum = artifact.with_name(artifact.name + '.sha256')
        if not checksum.exists() or checksum.read_text().split()[0] != hashlib.sha256(artifact.read_bytes()).hexdigest():
            raise ValueError('Missing or invalid legacy hash: ' + artifact.name)
        label = 'PaperMC リソースパック' if match[2] else 'PaperMC プラグイン' if match[1] else 'Forge MOD'
        name = html.escape(artifact.name)
        links.append(f'<li>Minecraft {html.escape(match[3])} · {label}（v{html.escape(match[4])}）：'
                     f'<a href="downloads/{name}" download>{name}</a> · '
                     f'<a href="downloads/{name}.sha256" download>ハッシュ値</a></li>')
    section = ('<!-- LEGACY START -->\n<section class="page-section" aria-labelledby="legacy-title">\n'
               '<h2 class="section-title" id="legacy-title">旧バージョンのダウンロード</h2>\n<ul>\n' +
               '\n'.join(links) + '\n</ul>\n</section>\n<!-- LEGACY END -->') if links else '<!-- LEGACY SLOT -->'
    text = page.read_text(encoding='utf-8')
    if '<!-- LEGACY START -->' in text:
        text = re.sub(r'<!-- LEGACY START -->.*?<!-- LEGACY END -->', lambda _: section, text, flags=re.S)
    elif '<!-- LEGACY SLOT -->' in text:
        text = text.replace('<!-- LEGACY SLOT -->', section)
    else:
        text = text.replace('<footer>', section + '\n<footer>')
    page.write_text(text, encoding='utf-8')


if __name__ == '__main__':
    sys.exit(main())
