"""Store large checkpoint strings once per run, in the journal transaction."""

import hashlib
import json

from evosprig.core.spec import canonical_json

FORMAT = "evosprig.checkpoint/1"
BLOB = "$evosprig.blob"
ESCAPE = "$evosprig.object"
THRESHOLD = 16384


def pack(checkpoint):
    blobs = {}

    def encode(value):
        if isinstance(value, str) and len(value) >= THRESHOLD:
            digest = hashlib.sha256(value.encode()).hexdigest()
            blobs[digest] = value
            return {BLOB: digest}
        if isinstance(value, dict):
            items = {key: encode(item) for key, item in value.items()}
            if BLOB in items or ESCAPE in items:
                return {ESCAPE: list(items.items())}
            return items
        if isinstance(value, list):
            return [encode(item) for item in value]
        return value

    return canonical_json([FORMAT, encode(checkpoint)]), blobs


def write(db, run_id, body, blobs):
    existing = {row[0] for row in db.execute(
        "SELECT digest FROM runtime_checkpoint_blobs WHERE run_id=?", (run_id,)
    )}
    db.executemany("INSERT INTO runtime_checkpoint_blobs VALUES (?, ?, ?)",
                   [(run_id, key, value) for key, value in blobs.items() if key not in existing])
    db.execute("UPDATE runtime_checkpoints SET body=? WHERE id=?", (body, run_id))


def unpack(db, run_id, body):
    value = json.loads(body)
    if isinstance(value, dict):
        return value  # Journals written before blob storage.
    if not isinstance(value, list) or len(value) != 2 or value[0] != FORMAT:
        raise ValueError("unsupported checkpoint encoding")
    cache = {}

    def decode(item):
        if isinstance(item, dict):
            if set(item) == {BLOB}:
                digest = item[BLOB]
                if digest not in cache:
                    row = db.execute(
                        "SELECT body FROM runtime_checkpoint_blobs WHERE run_id=? AND digest=?",
                        (run_id, digest),
                    ).fetchone()
                    if row is None:
                        raise ValueError("checkpoint blob is missing")
                    cache[digest] = row[0]
                return cache[digest]
            if set(item) == {ESCAPE}:
                return {key: decode(v) for key, v in item[ESCAPE]}
            return {key: decode(v) for key, v in item.items()}
        if isinstance(item, list):
            return [decode(v) for v in item]
        return item

    return decode(value[1])
