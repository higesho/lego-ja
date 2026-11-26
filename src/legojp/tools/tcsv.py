# Read/write TT Games text CSVs keeping the original byte layout.
# Records: all fields double-quoted, no escaped quotes, fields may contain CR/LF.
import re

def parse(raw):
    """raw str -> list of items: ('rec', [fields]) or ('raw', text)"""
    out = []
    i, n = 0, len(raw)
    while i < n:
        if raw[i] == '"':
            fields = []
            while True:
                j = raw.index('"', i + 1)
                fields.append(raw[i + 1:j])
                i = j + 1
                if i < n and raw[i] == ',' and i + 1 < n and raw[i + 1] == '"':
                    i += 1
                    continue
                break
            out.append(('rec', fields))
        else:
            j = raw.find('"', i)
            # a raw chunk runs until the next line that starts with a quote
            m = re.compile(r'(?:^|\n)"').search(raw, i)
            if m is None:
                out.append(('raw', raw[i:])); break
            k = m.start() + (1 if raw[m.start()] == '\n' else 0)
            if k == i:   # should not happen
                k = i + 1
            out.append(('raw', raw[i:k]))
            i = k
    return out

def build(items):
    s = []
    for kind, v in items:
        if kind == 'rec': s.append('"' + '","'.join(v) + '"')
        else: s.append(v)
    return ''.join(s)

def load(path):
    raw = open(path, 'rb').read().decode('utf-8')
    return parse(raw)

if __name__ == '__main__':
    import sys
    for p in sys.argv[1:]:
        raw = open(p, 'rb').read().decode('utf-8')
        it = parse(raw)
        print(p, build(it) == raw, sum(1 for k, v in it if k == 'rec'))
