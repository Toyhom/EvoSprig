"""Use the same document library outside Studio: python library.py FILE --project ID."""
import argparse
from pathlib import Path

from evosprig.core.journal import Scope
from evosprig.core.memory import MemoryScope
from evosprig.plugins.document_library import DocumentConfig, DocumentLibrary
from evosprig.plugins.sqlite_memory import SQLiteMemory


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('file', type=Path)
    p.add_argument('--project', default='rag-classroom')
    p.add_argument('--workspace', type=Path, default=Path('.evosprig/rag-lesson'))
    p.add_argument('--source', default='manuals/warranty')
    p.add_argument('--query', default='电池保修期')
    p.add_argument('--delete', action='store_true')
    a = p.parse_args()
    scope = MemoryScope(Scope(a.project), namespace='documents')
    library = DocumentLibrary(SQLiteMemory(a.workspace/'memory.sqlite'), DocumentConfig(ocr_languages='chi_sim+eng'))
    result = library.ingest_file(scope, a.file, source=a.source)
    print(library.retriever(scope).search(scope, a.query))
    if a.delete:
        print(library.delete(scope, result['document_id']))


if __name__ == '__main__':
    main()
