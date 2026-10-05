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


def properties():
    values = {}
    for line in (ROOT / 'build/gradle.properties').read_text(encoding='utf-8-sig').splitlines():
        line = line.strip()
        if line and not line.startswith(('#', '!')) and '=' in line:
            key, value = line.split('=', 1)
            values[key.strip()] = value.strip()
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


def validate_mod_archive(artifact):
    """Reject incomplete archives before copying them to the public directory."""
    java_root = ROOT / 'source/main/java'
    resources_root = ROOT / 'source/main/resources'
    required = {'META-INF/mods.toml', 'dev/lotcarnage/culinaryexpansion/CulinaryExpansion.class'}
    required.update(path.relative_to(java_root).with_suffix('.class').as_posix()
                    for path in java_root.rglob('*.java'))
    required.update(path.relative_to(resources_root).as_posix()
                    for path in resources_root.rglob('*') if path.is_file())
    try:
        with zipfile.ZipFile(artifact) as archive:
            missing = required - set(archive.namelist())
            if missing:
                raise ValueError('Incomplete mod JAR; missing: ' + ', '.join(sorted(missing)))
            corrupt = archive.testzip()
            if corrupt:
                raise ValueError(f'Corrupt mod JAR entry: {corrupt}')
            for name in archive.namelist():
                if name.startswith('data/culinary_expansion/recipe/') and name.endswith('.json'):
                    validate_recipe_category(json.loads(archive.read(name)), name)
            entry = archive.read('dev/lotcarnage/culinaryexpansion/CulinaryExpansion.class')
            if not entry.startswith(b'\xca\xfe\xba\xbe') or b'Lnet/minecraftforge/fml/common/Mod;' not in entry or b'culinary_expansion' not in entry:
                raise ValueError('Mod entry class is missing its Forge @Mod declaration')
    except zipfile.BadZipFile as error:
        raise ValueError('Invalid mod JAR') from error


def prepare_pages():
    config = properties()
    name = f"culinary-expansion-{config['minecraft_version']}-{config['mod_version']}.jar"
    artifact = ROOT / 'intermediate/gradle-output/libs' / name
    validate_mod_archive(artifact)
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
    (ROOT / '.nojekyll').write_text('', encoding='utf-8')
    print(f'Distribution JAR: {downloads / name}')
    print(f'GitHub Pages files: {ROOT / "deliverables"}')


def build(java_home):
    env = os.environ.copy()
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
    subprocess.run(command + ['--no-daemon', '--project-dir', str(ROOT / 'build'),
                              '--project-cache-dir', str(ROOT / 'intermediate/gradle-cache'),
                              'clean', 'build'], cwd=ROOT, env=env, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--java-home', help='JDK 25 directory (defaults to JAVA_HOME or PATH)')
    parser.add_argument('--pages-only', action='store_true', help='Prepare the page from an existing intermediate/gradle-output/libs JAR')
    args = parser.parse_args()
    try:
        if not args.pages_only:
            build(args.java_home)
        prepare_pages()
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f'Build failed: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
