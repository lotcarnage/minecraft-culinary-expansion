"""Restore the project's portable Microsoft JDK on Windows x64."""
import hashlib
from pathlib import Path
import platform
import re
import shutil
import tempfile
import urllib.request
import zipfile

VERSION = '25.0.4.1'
URL = f'https://aka.ms/download-jdk/microsoft-jdk-{VERSION}-windows-x64.zip'
CHECKSUM_URL = URL + '.sha256sum.txt'


def ensure_jdk(root):
    if platform.system() != 'Windows' or platform.machine().lower() not in ('amd64', 'x86_64'):
        raise ValueError('Automatic JDK setup supports Windows x64; specify --java-home with JDK 25 on this platform')
    destination = Path(root) / 'intermediate/jdk25'
    home = destination / 'jdk-25.0.4.1+1'
    if (home / 'bin/java.exe').is_file() and (home / 'bin/javac.exe').is_file():
        return home
    destination.mkdir(parents=True, exist_ok=True)
    print(f'Downloading Microsoft OpenJDK {VERSION}: {URL}', flush=True)
    with tempfile.TemporaryDirectory(dir=destination) as temporary:
        temporary = Path(temporary)
        archive_path = temporary / 'jdk.zip'
        with urllib.request.urlopen(CHECKSUM_URL, timeout=60) as response:
            checksum = response.read().decode('utf-8').strip()
        match = re.match(r'([0-9a-fA-F]{64})(?:\s|$)', checksum)
        if not match:
            raise ValueError('Invalid official JDK SHA-256 response')
        digest = hashlib.sha256()
        with urllib.request.urlopen(URL, timeout=60) as response, archive_path.open('wb') as output:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
                output.write(chunk)
        if digest.hexdigest() != match[1].lower():
            raise ValueError('JDK archive SHA-256 mismatch')
        extracted = temporary / 'extracted'
        with zipfile.ZipFile(archive_path) as archive:
            for member in archive.infolist():
                target = (extracted / member.filename).resolve()
                target.relative_to(extracted.resolve())
            archive.extractall(extracted)
        candidate = extracted / home.name
        if not all((candidate / 'bin' / name).is_file() for name in ('java.exe', 'javac.exe')):
            raise ValueError('JDK archive is missing the expected executables')
        if home.exists():
            raise ValueError(f'Incomplete JDK directory; remove it before retrying: {home}')
        shutil.move(str(candidate), str(home))
        (home / 'download-source.txt').write_text(
            f'URL={URL}\nSHA256={digest.hexdigest()}\n', encoding='utf-8')
    return home


if __name__ == '__main__':
    print(ensure_jdk(Path(__file__).resolve().parent.parent))
