import asyncio
import subprocess
import sys
import zipfile
from dataclasses import replace

import httpx
import pytest
import yaml
from test_durable_api import approval_spec

from evosprig.core.journal import Scope
from evosprig.core.memory import MemoryScope
from evosprig.core.version import compile_agent
from evosprig.exporters.python import export_python
from evosprig.plugins.document_library import DocumentConfig, DocumentLibrary, extract_document
from evosprig.plugins.sqlite_memory import SQLiteMemory
from evosprig.server.app import create_app
from evosprig.server.auth import Principal
from evosprig.server.standalone import create_service


@pytest.fixture
def library(tmp_path):
    return DocumentLibrary(SQLiteMemory(tmp_path / 'memory.sqlite'))


@pytest.fixture
def scope():
    return MemoryScope(Scope('manuals'), namespace='documents')


def test_replacement_readd_chunking_and_scope(library, scope):
    library.configure(scope, {"chunk_size": 200, "chunk_overlap": 50})
    text = '蓝色电池保修期一年。' * 40
    first = library.ingest_text(scope, title='Warranty', text=text, source='manual.pdf', pages=[{'page': 1, 'start': 0, 'end': len(text)}])
    hits = library.retriever(scope).search(scope, '电池保修')
    assert hits and hits[0]['pages'] == [1]
    assert hits[0]['text'] == text[hits[0]['start']:hits[0]['end']]
    assert library.retriever(scope).search(replace(scope, identity=Scope('manuals', 'bob')), '电池') == []
    with pytest.raises(ValueError):
        library.ingest_text(scope, title='Warranty', text='', source='manual.pdf')
    assert library.list(scope)[0]['id'] == first['document_id']
    second = library.ingest_text(scope, title='Warranty', text='Replacement warranty is three years.', source='manual.pdf')
    assert len(library.list(scope)) == 1
    assert library.retriever(scope).search(scope, '电池') == []
    assert library.retriever(scope).search(scope, 'three')
    library.delete(scope, second['document_id'])
    assert not library.list(scope)
    library.ingest_text(scope, title='Warranty', text=text, source='manual.pdf')
    assert library.retriever(scope).search(scope, '电池')
    assert not library.list(replace(scope, identity=Scope('other')))


def test_limits_are_configurable_and_docx_tables_are_read(library, scope, tmp_path):
    path = tmp_path / 'notes.txt'
    path.write_text('fleet ' * 180_000)
    library.configure(scope, {'max_file_bytes': 100})
    with pytest.raises(ValueError, match='limit'):
        library.ingest_file(scope, path)
    library.configure(scope, {'max_file_bytes': None, 'max_extracted_chars': None, 'chunk_size': 8000})
    assert library.ingest_file(scope, path)['characters'] > 1_000_000
    word = tmp_path / 'contract.docx'
    with zipfile.ZipFile(word, 'w') as archive:
        archive.writestr('word/document.xml', '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Warranty</w:t></w:r></w:p><w:tbl><w:tr><w:tc><w:p><w:r><w:t>Three years</w:t></w:r></w:p></w:tc></w:tr></w:tbl></w:body></w:document>')
    text, _ = extract_document(word, word.name, DocumentConfig())
    assert 'Warranty' in text and 'Three years' in text


def test_index_migrates_and_honors_deletion_ledger(tmp_path, scope):
    path = tmp_path / 'memory.sqlite'
    memory = SQLiteMemory(path)
    library = DocumentLibrary(memory)
    item = library.ingest_text(scope, title='Handbook', text='Silver refund process', source='handbook')
    # Simulate an older store without FTS tables/triggers, then reopen it.
    with memory._transaction() as db:
        for name in ['memory_fts_insert', 'memory_fts_update', 'memory_fts_delete']:
            db.execute('DROP TRIGGER ' + name)
        db.execute('DROP TABLE memory_fts')
    memory = SQLiteMemory(path)
    assert memory.search_indexed(scope, 'silver')
    backup = memory.export(scope)
    DocumentLibrary(memory).delete(scope, item['document_id'])
    assert memory.restore(scope, backup)['restored'] == 0
    assert memory.search_indexed(scope, 'silver') == []


async def wait_job(client, prefix, identifier):
    for _ in range(200):
        response = await client.get(prefix + '/jobs/' + identifier)
        assert response.status_code == 200, response.text
        job = response.json()
        if job['status'] in {'succeeded', 'failed'}:
            return job
        await asyncio.sleep(.05)
    pytest.fail('document job did not finish')


async def test_studio_upload_jobs_identity_limits_and_settings(tmp_path):
    app = create_app(tmp_path, principals={'a': Principal('alice'), 'b': Principal('bob')})
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://localhost', headers={'Authorization': 'Bearer a'}) as client:
            await client.post('/api/projects', json={'spec': approval_spec().model_dump()})
            prefix = '/api/projects/approval/documents'
            assert (await client.put(prefix + '/settings', json={'max_file_bytes': 4_000_000})).status_code == 200
            response = await client.post(prefix + '/upload?filename=manual.txt', content=b'Large document warranty. ' * 100_000)
            assert response.status_code == 202, response.text
            job = await wait_job(client, prefix, response.json()['id'])
            assert job['status'] == 'succeeded', job
            assert (await client.get(prefix + '/search?query=warranty')).json()
            assert (await client.get(prefix + '/jobs/' + job['id'], headers={'Authorization': 'Bearer b'})).status_code == 404
            await client.put(prefix + '/settings', json={'max_file_bytes': 10})
            async def body():
                yield b'a' * 6
                yield b'b' * 6
            assert (await client.post(prefix + '/upload?filename=large.txt', content=body())).status_code == 413
            assert len((await client.get(prefix)).json()) == 1
            assert (await client.post(prefix + '/upload?filename=../secret.txt', content=b'x')).status_code == 422


async def test_export_customer_upload_and_replace_without_reexport(spec, example_root, tmp_path):
    root = tmp_path / 'export'
    export_python(compile_agent(spec, example_root), root, target='http', document_config={'customer_uploads': True, 'chunk_size': 800, 'max_file_bytes': None})
    profile = root / 'deployment.example.yaml'
    assert yaml.safe_load(profile.read_text())['documents']['chunk_size'] == 800
    assert yaml.safe_load(profile.read_text())['documents']['max_file_bytes'] is None
    workspace = tmp_path / 'deployed'
    app = create_service(root, workspace, token='service', profile=profile, mock=True)
    prefix = '/documents'
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://localhost', headers={'Authorization': 'Bearer service'}) as client:
            first = await client.post(prefix + '/upload?filename=policy.txt', content=b'Warranty: one year.')
            assert (await wait_job(client, prefix, first.json()['id']))['status'] == 'succeeded'
            second = await client.post(prefix + '/upload?filename=policy.txt', content=b'Warranty: three years.')
            assert (await wait_job(client, prefix, second.json()['id']))['status'] == 'succeeded'
            assert not (await client.get(prefix + '/search?query=one')).json()
            assert (await client.get(prefix + '/search?query=three')).json()
            assert len((await client.get(prefix)).json()) == 1
            assert (await client.put(prefix + '/settings', json={})).status_code == 405
    # Start a fresh interpreter using ONLY the exported runtime for configuration and search.
    result = subprocess.run([sys.executable, '-c', "from pathlib import Path; from evosprig.config import make_tools; from evosprig.core.journal import Scope; import asyncio; t=make_tools(Path('" + str(workspace) + "'),Scope('" + spec.id + "')); print(asyncio.run(t.resolve('documents.search').invoke({'query':'three'})))"], cwd=root, env={'PATH': '/usr/bin:/bin', 'PYTHONPATH': str(root/'src')}, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert 'three years' in result.stdout
    disabled = create_service(root, workspace, token='service', mock=True)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=disabled), base_url='http://localhost', headers={'Authorization': 'Bearer service'}) as client:
        assert (await client.get(prefix)).status_code == 403


def test_slow_older_upload_cannot_overwrite_newer(library, scope):
    from evosprig.core.memory import MemoryConflict
    library.ingest_text(scope, title='Policy', text='New policy', source='policy.txt', submitted_at=200)
    with pytest.raises(MemoryConflict, match='newer upload'):
        library.ingest_text(scope, title='Policy', text='Old policy', source='policy.txt', submitted_at=100)
    assert library.retriever(scope).search(scope, 'New')
    assert not library.retriever(scope).search(scope, 'Old')


def test_deletion_prevents_pending_upload_from_restoring_source(library, scope):
    import time

    from evosprig.core.memory import MemoryConflict

    first = library.ingest_text(scope, title='Policy', text='Original warranty', source='policy.txt')
    pending_submission = time.time()
    library.delete(scope, first['document_id'])
    # A parser that started before deletion must not restore the customer's source.
    reopened = DocumentLibrary(SQLiteMemory(library.memory.path))
    with pytest.raises(MemoryConflict, match='deleted after the upload'):
        reopened.ingest_text(scope, title='Policy', text='Pending warranty update', source='policy.txt', submitted_at=pending_submission)
    assert not reopened.list(scope)
    reopened.ingest_text(scope, title='Policy', text='Explicit new upload', source='policy.txt')
    assert reopened.retriever(scope).search(scope, 'Explicit')


def test_embedding_cache_survives_new_retriever_and_hides_deleted(tmp_path, scope):
    from test_memory_extended import Embedder

    from evosprig.plugins.semantic_memory import HybridMemory
    memory = SQLiteMemory(tmp_path / 'memory.sqlite')
    record = memory.write(scope, 'commutes by bicycle', source='user')
    first = Embedder()
    HybridMemory(memory, first, cache_path=tmp_path/'vectors.sqlite').search(scope, 'bike')
    second = Embedder()
    assert HybridMemory(memory, second, cache_path=tmp_path/'vectors.sqlite').search(scope, 'bike')
    assert second.texts == ['bike']
    memory.delete(scope, record['id'])
    assert not HybridMemory(memory, second, cache_path=tmp_path/'vectors.sqlite').search(scope, 'bike')


async def test_queue_recovers_interrupted_parser_and_keeps_processing_after_bad_file(library, scope, tmp_path):
    from evosprig.server.document_api import DocumentJobs
    first = DocumentJobs(library, tmp_path/'uploads')
    interrupted = first.reserve(scope, 'policy.txt', None, library.config(scope))
    (first.directory/interrupted).write_text('Recovery warranty lasts three years.')
    first.update(interrupted, 'queued')
    row = first.claim()
    old_token = row[2]
    with library.memory._transaction() as db:
        db.execute('UPDATE document_jobs SET lease=0 WHERE id=?', (interrupted,))
    second = DocumentJobs(library, first.directory)
    recovered = second.claim()
    assert recovered[0] == interrupted and recovered[2] != old_token
    assert not first.update(interrupted, 'failed', error='late worker', claim_token=old_token)
    second.update(interrupted, 'queued')
    bad = second.reserve(scope, 'broken.docx', None, library.config(scope))
    (second.directory/bad).write_bytes(b'not a ZIP')
    second.update(bad, 'queued')
    abandoned = second.reserve(scope, 'partial.txt', None, library.config(scope))
    (second.directory/abandoned).write_text('partial')
    with library.memory._transaction() as db:
        db.execute('UPDATE document_jobs SET lease=0 WHERE id=?', (abandoned,))
    await second.start()
    try:
        for _ in range(200):
            if second.get(scope, bad)['status'] == 'failed' and second.get(scope, interrupted)['status'] == 'succeeded':
                break
            await asyncio.sleep(.02)
        assert second.get(scope, interrupted)['status'] == 'succeeded'
        assert second.get(scope, bad)['status'] == 'failed'
        assert second.get(scope, abandoned)['status'] == 'failed'
        assert library.retriever(scope).search(scope, 'Recovery')
    finally:
        await second.stop()
    assert not list(second.directory.iterdir())


def test_pdf_text_and_scanned_page_ocr(tmp_path, monkeypatch):
    pdfium = pytest.importorskip('pypdfium2')
    from PIL import Image
    image = Image.new('RGB', (80, 80), 'white')
    path = tmp_path/'scan.pdf'
    image.save(path, 'PDF')
    import evosprig.plugins.document_library as module
    calls = []
    def ocr(path, config):
        assert path.is_file()
        calls.append(config.ocr_languages)
        return 'Warranty covers three years.'
    monkeypatch.setattr(module, '_ocr', ocr)
    text, pages = extract_document(path, path.name, DocumentConfig(ocr_languages='chi_sim+eng'))
    assert 'three years' in text and pages == [{'page': 1, 'start': 0, 'end': len(text)}]
    assert calls == ['chi_sim+eng']
    with pytest.raises(ValueError, match='no selectable text'):
        extract_document(path, path.name, DocumentConfig(ocr='disabled'))
    # Native PDFium text extraction: a PDF assembled from its text objects.
    doc = pdfium.PdfDocument.new()
    doc.new_page(200, 100)
    doc.save(tmp_path/'empty.pdf')
    doc.close()
    with pytest.raises(ValueError, match='no selectable text'):
        extract_document(tmp_path/'empty.pdf', 'empty.pdf', DocumentConfig(ocr='disabled'))


def test_export_reimport_preserves_nullable_intake_settings(spec, example_root, tmp_path):
    import io

    from evosprig.exporters.importer import inspect_archive
    root = tmp_path/'export'
    export_python(compile_agent(spec, example_root), root, target='container', document_config={'customer_uploads': True, 'max_file_bytes': None, 'ocr_languages': 'chi_sim+eng'})
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, 'w') as output:
        for file in root.rglob('*'):
            if file.is_file():
                output.write(file, file.relative_to(root))
    _, report = inspect_archive(archive.getvalue())
    assert report['documents']['max_file_bytes'] is None
    assert report['documents']['customer_uploads'] is True
    assert 'DOCUMENT_PARSERS' in (root/'Dockerfile').read_text()
