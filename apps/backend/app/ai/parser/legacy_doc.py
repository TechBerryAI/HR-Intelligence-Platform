"""Pure-Python text extraction for legacy Word 97-2003 (.doc) documents.

Used when the ``antiword`` binary is unavailable (or fails), so .doc parsing
does not depend on a system package that some hosts (RHEL/Rocky, Windows)
cannot install from their default repositories.

Two layers, both from the published Microsoft specs:

* [MS-CFB] Compound File Binary — the OLE2 container: header, FAT/DIFAT sector
  chains, mini stream, directory. Only reading streams by name is needed.
* [MS-DOC] Word Binary — the FIB at the start of ``WordDocument`` points to the
  CLX in the table stream (``0Table``/``1Table``); its piece table maps character
  positions to byte runs that are either cp1252 ("compressed") or UTF-16LE.

Word 6/95 files (pre-FIB 97), encrypted documents and corrupted containers raise
``ValueError`` with a message suitable for showing to the uploader.
"""
from __future__ import annotations

import email
import email.policy
import io
import re
import struct
import zipfile
from html.parser import HTMLParser
from xml.etree import ElementTree

_OLE2_MAGIC = b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'

_MAX_SECTOR_ID = 0xFFFFFFFA  # higher values are FREESECT / ENDOFCHAIN / FATSECT / DIFSECT

_STGTY_STREAM = 2
_STGTY_ROOT = 5

_WORD_IDENTS = (0xA5EC, 0xA5DC)  # Word 97+ / Word 6
_NFIB_WORD97 = 0x00C1  # Word 97+ FIB; Word 6/95 (nFib ~0x65-0x68) use another layout
_FIB_ENCRYPTED = 0x0100
_FIB_WHICH_TABLE = 0x0200
_FIB_RGFCLCB_CLX = 33


class _CompoundFile:
    """Minimal read-only [MS-CFB] reader: enough to fetch a stream by name."""

    def __init__(self, data: bytes) -> None:
        if len(data) < 512 or not data.startswith(_OLE2_MAGIC):
            raise ValueError('Not an OLE2 compound file')
        self._data = data
        sector_shift, mini_shift = struct.unpack_from('<HH', data, 0x1E)
        num_fat, first_dir = struct.unpack_from('<II', data, 0x2C)
        mini_cutoff, first_minifat, num_minifat, first_difat, num_difat = struct.unpack_from(
            '<IIIII', data, 0x38
        )
        if sector_shift not in (9, 12) or mini_shift != 6:
            raise ValueError('Unsupported compound file sector size')
        self._sector_size = 1 << sector_shift
        self._mini_size = 1 << mini_shift
        self._mini_cutoff = mini_cutoff

        fat_sectors = [s for s in struct.unpack_from('<109I', data, 0x4C) if s <= _MAX_SECTOR_ID]
        per_difat = self._sector_size // 4 - 1
        difat = first_difat
        for _ in range(num_difat):
            if difat > _MAX_SECTOR_ID:
                break
            entries = struct.unpack_from(f'<{per_difat + 1}I', self._sector(difat))
            fat_sectors.extend(s for s in entries[:-1] if s <= _MAX_SECTOR_ID)
            difat = entries[-1]
        fat_sectors = fat_sectors[:num_fat] if num_fat else fat_sectors
        self._fat = self._read_u32_array(b''.join(self._sector(s) for s in fat_sectors))

        self._directory = self._parse_directory(self._chain_bytes(first_dir, self._fat))
        root = next((e for e in self._directory if e['type'] == _STGTY_ROOT), None)
        if root is None:
            raise ValueError('Compound file has no root entry')
        self._mini_stream = (
            self._chain_bytes(root['start'], self._fat)[: root['size']]
            if root['size'] else b''
        )
        self._minifat = (
            self._read_u32_array(self._chain_bytes(first_minifat, self._fat))
            if num_minifat and first_minifat <= _MAX_SECTOR_ID else []
        )

    @staticmethod
    def _read_u32_array(buf: bytes) -> list[int]:
        return list(struct.unpack(f'<{len(buf) // 4}I', buf[: len(buf) // 4 * 4]))

    def _sector(self, sid: int) -> bytes:
        start = (sid + 1) * self._sector_size
        chunk = self._data[start: start + self._sector_size]
        if len(chunk) < self._sector_size:
            # Truncated final sector is common in the wild; pad rather than fail.
            chunk = chunk.ljust(self._sector_size, b'\x00')
        return chunk

    def _chain(self, start: int, table: list[int]) -> list[int]:
        chain: list[int] = []
        sid = start
        while sid <= _MAX_SECTOR_ID:
            if sid >= len(table) or len(chain) > len(table):
                raise ValueError('Corrupted compound file (bad sector chain)')
            chain.append(sid)
            sid = table[sid]
        return chain

    def _chain_bytes(self, start: int, table: list[int]) -> bytes:
        if start > _MAX_SECTOR_ID:
            return b''
        return b''.join(self._sector(s) for s in self._chain(start, table))

    @staticmethod
    def _parse_directory(buf: bytes) -> list[dict]:
        entries = []
        for off in range(0, len(buf) - 127, 128):
            name_len = struct.unpack_from('<H', buf, off + 0x40)[0]
            obj_type = buf[off + 0x42]
            if obj_type == 0 or name_len < 2 or name_len > 64:
                continue
            name = buf[off: off + name_len - 2].decode('utf-16-le', errors='replace')
            start, size_lo, size_hi = struct.unpack_from('<III', buf, off + 0x74)
            entries.append({'name': name, 'type': obj_type, 'start': start,
                            'size': size_lo | (size_hi << 32) if size_hi < 0x80000000 else size_lo})
        return entries

    def has_stream(self, name: str) -> bool:
        return any(e['type'] == _STGTY_STREAM and e['name'] == name for e in self._directory)

    def read_stream(self, name: str) -> bytes:
        entry = next(
            (e for e in self._directory if e['type'] == _STGTY_STREAM and e['name'] == name), None
        )
        if entry is None:
            raise ValueError(f'Stream {name!r} not found')
        size = entry['size']
        if size < self._mini_cutoff and self._minifat:
            out = bytearray()
            for sid in self._chain(entry['start'], self._minifat):
                off = sid * self._mini_size
                out += self._mini_stream[off: off + self._mini_size]
            return bytes(out[:size])
        return self._chain_bytes(entry['start'], self._fat)[:size]


def _fib_header(word: bytes) -> tuple[int, int]:
    """Validate the FibBase; return (nFib, flags)."""
    if len(word) < 0x22:
        raise ValueError('WordDocument stream is too short')
    ident, nfib = struct.unpack_from('<HH', word, 0)
    if ident not in _WORD_IDENTS:
        raise ValueError('Not a Word document (bad FIB signature)')
    flags = struct.unpack_from('<H', word, 0x0A)[0]
    if flags & _FIB_ENCRYPTED:
        raise ValueError('This .doc file is password-protected; please upload an unprotected copy')
    return nfib, flags


def _word6_text(word: bytes) -> str:
    """Word 6/95: text is a single cp1252 run between fcMin and fcMac. A
    fast-saved (complex) file may also carry later edits elsewhere; the base
    run still holds the document as last fully saved."""
    fc_min, fc_mac = struct.unpack_from('<II', word, 0x18)
    if not (0 < fc_min < fc_mac <= len(word)):
        raise ValueError('Corrupted Word 6/95 .doc file (bad text range)')
    return word[fc_min:fc_mac].decode('cp1252', errors='replace')


def _fib_clx_location(word: bytes, flags: int) -> tuple[int, int, bool]:
    """Word 97+: return (fcClx, lcbClx, use_1table) from the FIB."""
    pos = 0x20
    csw = struct.unpack_from('<H', word, pos)[0]
    pos += 2 + csw * 2
    cslw = struct.unpack_from('<H', word, pos)[0]
    pos += 2 + cslw * 4
    cb_fclcb = struct.unpack_from('<H', word, pos)[0]
    pos += 2
    if cb_fclcb <= _FIB_RGFCLCB_CLX:
        raise ValueError('Unsupported Word file layout (FIB too short)')
    fc_clx, lcb_clx = struct.unpack_from('<II', word, pos + _FIB_RGFCLCB_CLX * 8)
    return fc_clx, lcb_clx, bool(flags & _FIB_WHICH_TABLE)


def _piece_table(table: bytes, fc_clx: int, lcb_clx: int) -> list[tuple[int, int, int, bool]]:
    """Parse the CLX into (cp_start, cp_end, byte_offset, compressed) pieces."""
    clx = table[fc_clx: fc_clx + lcb_clx]
    pos = 0
    while pos < len(clx) and clx[pos] == 0x01:  # Prc: skip property modifiers
        cb = struct.unpack_from('<h', clx, pos + 1)[0]
        pos += 3 + max(cb, 0)
    if pos >= len(clx) or clx[pos] != 0x02:
        raise ValueError('Word piece table not found')
    lcb = struct.unpack_from('<I', clx, pos + 1)[0]
    plc = clx[pos + 5: pos + 5 + lcb]
    n = (len(plc) - 4) // 12
    if n <= 0:
        raise ValueError('Word piece table is empty')
    cps = struct.unpack_from(f'<{n + 1}I', plc, 0)
    pieces = []
    for i in range(n):
        fc = struct.unpack_from('<I', plc, (n + 1) * 4 + i * 8 + 2)[0]
        compressed = bool(fc & 0x40000000)
        fc &= 0x3FFFFFFF
        pieces.append((cps[i], cps[i + 1], fc // 2 if compressed else fc, compressed))
    return pieces


_FIELD_RE = re.compile(r'\x13[^\x13\x14\x15]*(?:\x14([^\x13\x14\x15]*))?\x15')


def _clean(text: str) -> str:
    # Fields: keep the displayed result, drop the code ({HYPERLINK "..."} etc.).
    # Nested fields are resolved innermost-first.
    for _ in range(8):
        new = _FIELD_RE.sub(lambda m: m.group(1) or '', text)
        if new == text:
            break
        text = new
    text = text.replace('\x13', '').replace('\x14', '').replace('\x15', '')
    text = text.replace('\x07\x07', '\n')           # last cell mark + end-of-row mark
    text = text.replace('\x07', ' | ')              # end of table cell
    text = text.replace('\r', '\n').replace('\x0b', '\n').replace('\x0c', '\n')
    text = text.replace('\x1e', '-').replace('\x1f', '').replace('\xa0', ' ')
    text = text.replace('\t', ' ')
    text = re.sub(r'[\x00-\x08\x0e-\x1f]', '', text)  # pictures, footnote refs, etc.
    text = re.sub(r'[ \t]*\|[ \t]*(\n|$)', r'\1', text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r' *\n *', '\n', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


_HTML_HEAD_RE = re.compile(rb'^\s*(?:<\?xml[^>]*>\s*)?(?:<!--.*?-->\s*)*<(?:!doctype\s+html|html)\b', re.I | re.S)
_MHTML_HEAD_RE = re.compile(rb'^\s*(?:[A-Za-z-]+:[^\r\n]*\r?\n)*?MIME-Version:', re.I)


def is_html_document(data: bytes) -> bool:
    """HTML or Word "single file web page" (MHTML) saved with a .doc extension —
    job portals such as Naukri export resumes this way."""
    head = data[:2048]
    return bool(_HTML_HEAD_RE.match(head) or _MHTML_HEAD_RE.match(head))


class _HtmlText(HTMLParser):
    _BLOCK = {'p', 'div', 'br', 'tr', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
              'table', 'ul', 'ol', 'section', 'article', 'header', 'footer', 'title'}
    _SKIP = {'script', 'style', 'head', 'xml', 'noscript'}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP:
            self._skip += 1
        elif tag in self._BLOCK:
            self.parts.append('\n')
        elif tag in ('td', 'th'):
            self.parts.append(' | ')

    def handle_endtag(self, tag):
        if tag in self._SKIP:
            self._skip = max(0, self._skip - 1)
        elif tag in self._BLOCK:
            self.parts.append('\n')

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data.replace('\r', ' ').replace('\n', ' '))


def _html_bytes_from_mhtml(data: bytes) -> bytes:
    msg = email.message_from_bytes(data, policy=email.policy.default)
    for part in msg.walk():
        if part.get_content_type() == 'text/html':
            payload = part.get_payload(decode=True) or b''
            charset = part.get_content_charset() or 'utf-8'
            return payload.decode(charset, errors='replace').encode('utf-8')
    raise ValueError('Web-page .doc file has no HTML content')


def extract_html_text(data: bytes) -> str:
    """Visible text of an HTML/MHTML document."""
    if _MHTML_HEAD_RE.match(data[:2048]):
        data = _html_bytes_from_mhtml(data)
    meta = re.search(rb'charset=["\']?([A-Za-z0-9_-]+)', data[:4096], re.I)
    encoding = meta.group(1).decode('ascii') if meta else 'utf-8'
    try:
        markup = data.decode(encoding, errors='replace')
    except LookupError:
        markup = data.decode('utf-8', errors='replace')
    parser = _HtmlText()
    parser.feed(markup)
    parser.close()
    text = ''.join(parser.parts)
    text = re.sub(r'(\n\s*)\|\s*', r'\1', text)  # no leading pipe on a row's first cell
    return _clean(text)


_ODT_MIMETYPE = b'application/vnd.oasis.opendocument.text'


def is_odt_document(data: bytes) -> bool:
    """OpenDocument text (LibreOffice / WPS) saved with a .doc/.docx extension."""
    if not data.startswith(b'PK\x03\x04'):
        return False
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            names = set(zf.namelist())
            if 'content.xml' not in names or 'word/document.xml' in names:
                return False
            return 'mimetype' not in names or zf.read('mimetype').strip() == _ODT_MIMETYPE
    except zipfile.BadZipFile:
        return False


def extract_odt_text(data: bytes) -> str:
    """Visible text of an OpenDocument text file (paragraphs, headings, lists, tables)."""
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        root = ElementTree.fromstring(zf.read('content.xml'))
    ns_text = '{urn:oasis:names:tc:opendocument:xmlns:text:1.0}'
    ns_table = '{urn:oasis:names:tc:opendocument:xmlns:table:1.0}'
    lines: list[str] = []

    def inline(el) -> str:
        out = [el.text or '']
        for child in el:
            tag = child.tag
            if tag == f'{ns_text}s':
                out.append(' ' * int(child.get(f'{ns_text}c', '1')))
            elif tag == f'{ns_text}tab':
                out.append(' ')
            elif tag == f'{ns_text}line-break':
                out.append('\n')
            elif tag != f'{ns_text}note':
                out.append(inline(child))
            out.append(child.tail or '')
        return ''.join(out)

    def walk(el) -> None:
        for child in el:
            if child.tag in (f'{ns_text}p', f'{ns_text}h'):
                lines.append(inline(child))
            elif child.tag == f'{ns_table}table-row':
                cells = [' '.join(inline(p) for p in cell.iter(f'{ns_text}p'))
                         for cell in child if cell.tag == f'{ns_table}table-cell']
                lines.append(' | '.join(c for c in cells if c.strip()))
            else:
                walk(child)

    walk(root)
    return _clean('\n'.join(lines))


def extract_doc_text(data: bytes) -> str:
    """Return the visible text of a Word 97-2003 .doc file (body, then headers,
    footnotes and text boxes, in storage order)."""
    try:
        cfb = _CompoundFile(data)
        if not cfb.has_stream('WordDocument'):
            raise ValueError('This OLE2 file is not a Word document (no WordDocument stream)')
        word = cfb.read_stream('WordDocument')
        nfib, flags = _fib_header(word)
        if nfib < _NFIB_WORD97:
            return _clean(_word6_text(word))
        fc_clx, lcb_clx, use_1table = _fib_clx_location(word, flags)
        table_name = '1Table' if use_1table else '0Table'
        if not cfb.has_stream(table_name):
            raise ValueError(f'Word table stream {table_name} is missing')
        table = cfb.read_stream(table_name)
        pieces = _piece_table(table, fc_clx, lcb_clx)
    except (struct.error, IndexError) as exc:
        raise ValueError(f'Corrupted .doc file ({exc.__class__.__name__})') from exc

    parts: list[str] = []
    for cp_start, cp_end, offset, compressed in pieces:
        count = max(0, cp_end - cp_start)
        if compressed:
            parts.append(word[offset: offset + count].decode('cp1252', errors='replace'))
        else:
            parts.append(word[offset: offset + count * 2].decode('utf-16-le', errors='replace'))
    return _clean(''.join(parts))
