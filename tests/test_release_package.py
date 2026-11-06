import json
import subprocess
import sys
import zipfile
from pathlib import Path


def test_release_packager_uses_selected_source_and_accepts_lock_spacing(tmp_path):
    source = tmp_path / 'tagged-source'
    source.mkdir()
    (source / 'pyproject.toml').write_text('[project]\nname="example"\nversion="1.2.3"\n')
    (source / 'requirements-dev.lock').write_text('# Locked dependencies\n\nhttpx==0.28.1\n\npydantic==2.12.3\n')
    output = tmp_path / 'assets'
    script = Path(__file__).parents[1] / 'scripts/release/package.py'
    subprocess.run([sys.executable, str(script), '--root', str(source), '--out', str(output)],
                   check=True, capture_output=True)
    with zipfile.ZipFile(output / 'evosprig-1.2.3-source.zip') as archive:
        assert set(archive.namelist()) == {'pyproject.toml', 'requirements-dev.lock'}
    packages = json.loads((output / 'sbom.spdx.json').read_text())['packages']
    assert [(p['name'], p['versionInfo']) for p in packages] == [('httpx', '0.28.1'), ('pydantic', '2.12.3')]
    assert 'evosprig-1.2.3-source.zip' in (output / 'SHA256SUMS').read_text()
