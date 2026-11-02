"""Bounded component transport; directory traversal lives on the PC. GPL-3.0-or-later."""
import struct

TOKEN = b'/__crpc_browser_file__'

def make_request(action, path, read_size=512, dedicated=True):
    if action not in ('L', 'C') or not path.startswith('/'):
        raise ValueError('invalid browser request')
    parts = tuple(p for p in path.split('/') if p)
    if len(parts)>65534 or (action=='C' and not parts):
        raise ValueError('too many path components or no file selected')
    if read_size not in (256,512):
        raise ValueError('invalid read size')
    for part in parts:
        encoded=part.encode('utf-8')
        if part in ('.','..') or len(encoded)>255 or any(c in encoded for c in (0,10,13,9)):
            raise ValueError('unsupported path component')
    return {'action':action,'path':'/'+ '/'.join(parts), 'parts':parts,
            'read_size':read_size,'dedicated':bool(dedicated)}

def response(request, payload):
    if not isinstance(request,dict) or len(payload)!=2:
        raise ValueError('no pending browser request')
    index=struct.unpack('<H',payload)[0]
    if index==0:
        return struct.pack('<BHHB',ord(request['action']),len(request['parts']),
                           request['read_size'],request['dedicated'])
    if index>len(request['parts']):
        raise ValueError('invalid component index')
    return request['parts'][index-1].encode('utf-8')+b'\0'
