import base64
import json
import zlib


RETENTION_SECONDS = 900


def encode_receipt(result):
    raw = json.dumps(result, separators=(',', ':')).encode()
    if len(raw) <= 4096:
        return raw.decode()
    encoded = 'zlib:' + base64.b64encode(zlib.compress(raw)).decode()
    return encoded if len(encoded) < len(raw) else raw.decode()


def decode_receipt(value):
    if not value.startswith('zlib:'):
        return json.loads(value)
    decompressor = zlib.decompressobj()
    raw = decompressor.decompress(base64.b64decode(value[5:], validate=True), 8 * 1024 * 1024)
    if not decompressor.eof:
        raise ValueError('receipt too large or incomplete')
    return json.loads(raw)


def prune_receipts(connection, now):
    connection.execute('DELETE FROM receipts WHERE (player_id,request_id) IN (SELECT player_id,request_id FROM receipt_expiry WHERE expires<=?)', (now,))
    connection.execute('DELETE FROM receipt_expiry WHERE expires<=?', (now,))
