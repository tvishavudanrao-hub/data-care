#!/usr/bin/env python3
"""formula_infer.py - Data Care formula rebuilder (Python 3.8+, standard library only).

Takes a financial model .xlsx whose formulas were pasted over as plain values (some cells blank or #REF!),
infers the formula behind each computed row from the values that survived, fills what it can, and writes
model.xlsx, rules.json, report_items.json, gaps.json, question.json and summary.json (see CONTRACTS.md).
It never runs the client's file: it reads the zip as data.

  python3 formula_infer.py --workbook model_damaged.xlsx [--evidence evidence.json] [--case C-0001]
                           [--answer R-0001-03=1 ...] --out-dir rebuilt/
"""
import argparse, json, os, random, re, sys, zipfile
import xml.etree.ElementTree as ET
from decimal import Decimal, ROUND_HALF_UP, ROUND_UP, ROUND_DOWN
from xml.sax.saxutils import escape

sys.setrecursionlimit(20000)
M = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
RID = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'
REC, TESTED, UNTESTED, UNRES = 'recovered', 'reconstructed and tested', 'reconstructed but untested', 'unresolved'
LABELS = (REC, TESTED, UNTESTED, UNRES)


class Err(str):
    """An Excel error value such as #REF! or #DIV/0!."""


# ---------------------------------------------------------------- A1 helpers
def col2n(s):
    n = 0
    for ch in s.upper():
        n = n * 26 + ord(ch) - 64
    return n


def n2col(n):
    s = ''
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def a1(r, c, absolute=False):
    return ('$%s$%d' if absolute else '%s%d') % (n2col(c), r)


def qsheet(name):
    if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.]*', name) and not re.fullmatch(r'[A-Za-z]{1,3}\d+', name):
        return name
    return "'%s'" % name.replace("'", "''")


def cref(key):
    return '%s!%s' % (key[0], a1(key[1], key[2]))


def fmtnum(v):
    return str(int(v)) if float(v).is_integer() and abs(v) < 1e15 else repr(float(v))


def tol(y):
    return 1e-9 * max(1.0, abs(y))


def xround(x, d, mode=ROUND_HALF_UP):
    q = Decimal(repr(float('%.15g' % x)))
    return float(q.quantize(Decimal(1).scaleb(-int(d)), rounding=mode))


# ---------------------------------------------------------------- formula tokenizer, parser, evaluator
TOK = re.compile(r"""(?P<sp>\s+)|(?P<str>"(?:[^"]|"")*")|(?P<err>\#(?:REF!|DIV/0!|N/A|VALUE!|NAME\?|NUM!|NULL!))|
 (?P<ref>(?:(?:'(?:[^']|'')+'|[A-Za-z_][\w.]*)!)?\$?[A-Za-z]{1,3}\$?\d+(?::\$?[A-Za-z]{1,3}\$?\d+)?)(?![\w(!])|
 (?P<num>(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)|(?P<fn>[A-Za-z_][\w.]*)\(|(?P<bool>TRUE|FALSE)(?![\w(])|
 (?P<op><=|>=|<>|[-+*/^&=<>%(),])""", re.X)
REFPART = re.compile(r'(\$?)([A-Za-z]{1,3})(\$?)(\d+)')
SHEETMAP = {}
PCACHE = {}


def tokenize(text):
    out, pos = [], 0
    while pos < len(text):
        m = TOK.match(text, pos)
        if not m or m.end() == pos:
            raise ValueError('cannot read formula near %r' % text[pos:pos + 12])
        if m.lastgroup != 'sp':
            out.append((m.lastgroup, m.group(m.lastgroup), m.start(), m.end()))
        pos = m.end()
    return out


def split_sheet(tok):
    if '!' in tok:
        sh, rest = tok.rsplit('!', 1)
        return sh, rest
    return '', tok


def unq(sh):
    return sh[1:-1].replace("''", "'") if sh.startswith("'") else sh


def map_refs(text, fn):
    """Rewrite every reference token in a formula with fn(prefix, [(cabs, col, rabs, row), ...])."""
    out, last = [], 0
    for kind, val, a, b in tokenize(text):
        if kind == 'ref':
            sh, rest = split_sheet(val)
            parts = [REFPART.fullmatch(p).groups() for p in rest.split(':')]
            out.append(text[last:a] + fn(sh, parts))
            last = b
    return ''.join(out) + text[last:]


def shift(text, dr, dc):
    def f(sh, parts):
        res = []
        for cabs, cl, rabs, rw in parts:
            cn, rr = col2n(cl) + (0 if cabs else dc), int(rw) + (0 if rabs else dr)
            if cn < 1 or rr < 1:
                raise ValueError('shifted off the sheet')
            res.append('%s%s%s%d' % (cabs, n2col(cn), rabs, rr))
        return (sh + '!' if sh else '') + ':'.join(res)
    return map_refs(text, f)


def to_r1c1(text, r0, c0):
    def f(sh, parts):
        res = []
        for cabs, cl, rabs, rw in parts:
            rr, cn = int(rw), col2n(cl)
            rs = 'R%d' % rr if rabs else ('R' if rr == r0 else 'R[%d]' % (rr - r0))
            cs = 'C%d' % cn if cabs else ('C' if cn == c0 else 'C[%d]' % (cn - c0))
            res.append(rs + cs)
        return (sh + '!' if sh else '') + ':'.join(res)
    return '=' + map_refs(text, f)


class Parser:
    def __init__(self, text, sheet):
        self.t, self.i, self.sheet = tokenize(text), 0, sheet

    def peek(self):
        return self.t[self.i][1] if self.i < len(self.t) and self.t[self.i][0] == 'op' else None

    def take(self):
        if self.i >= len(self.t):
            raise ValueError('formula ends early')
        self.i += 1
        return self.t[self.i - 1]

    def binary(self, ops, sub):
        a = sub()
        while self.peek() in ops:
            a = ('bin', self.take()[1], a, sub())
        return a

    def expr(self):
        return self.binary(('=', '<>', '<', '>', '<=', '>='), self.cat)

    def cat(self):
        return self.binary(('&',), self.add)

    def add(self):
        return self.binary(('+', '-'), self.mul)

    def mul(self):
        return self.binary(('*', '/'), self.pw)

    def pw(self):
        return self.binary(('^',), self.unary)

    def unary(self):
        if self.peek() in ('-', '+'):
            op = self.take()[1]
            v = self.unary()
            return ('neg', v) if op == '-' else v
        a = self.prim()
        while self.peek() == '%':
            self.take()
            a = ('bin', '/', a, ('n', 100.0))
        return a

    def prim(self):
        kind, v, _, _ = self.take()
        if kind == 'num':
            return ('n', float(v))
        if kind == 'str':
            return ('s', v[1:-1].replace('""', '"'))
        if kind == 'bool':
            return ('b', v.upper() == 'TRUE')
        if kind == 'err':
            return ('e', v)
        if kind == 'ref':
            sh, rest = split_sheet(v)
            sh = SHEETMAP.get(unq(sh).lower(), unq(sh)) if sh else self.sheet
            ps = [REFPART.fullmatch(p).groups() for p in rest.split(':')]
            (r1, c1), (r2, c2) = [(int(p[3]), col2n(p[1])) for p in (ps[0], ps[-1])]
            if len(ps) == 1:
                return ('ref', sh, r1, c1)
            return ('rng', sh, min(r1, r2), min(c1, c2), max(r1, r2), max(c1, c2))
        if kind == 'fn':
            args = []
            if self.peek() == ')':
                self.take()
                return ('fn', v.upper(), args)
            while True:
                args.append(('blank',) if self.peek() in (',', ')') else self.expr())
                t = self.take()[1]
                if t == ')':
                    return ('fn', v.upper(), args)
                if t != ',':
                    raise ValueError('bad argument list')
        if v == '(':
            e = self.expr()
            if self.take()[1] != ')':
                raise ValueError('missing )')
            return e
        raise ValueError('unexpected %r' % v)


def parse(text, sheet):
    k = (text, sheet)
    if k not in PCACHE:
        p = Parser(text.lstrip('='), sheet)
        e = p.expr()
        if p.i != len(p.t):
            raise ValueError('trailing tokens')
        PCACHE[k] = e
    return PCACHE[k]


def num(v):
    if isinstance(v, Err):
        return v
    if v is None:
        return 0.0
    if isinstance(v, bool):
        return 1.0 if v else 0.0
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, list):
        return Err('#VALUE!')
    try:
        return float(v)
    except ValueError:
        return Err('#VALUE!')


def flat(args, get):
    out = []
    for a in args:
        if a[0] == 'rng':
            for v in ev(a, get):
                if isinstance(v, Err):
                    return v
                if isinstance(v, float):
                    out.append(v)
            continue
        v = ev(a, get)
        if a[0] == 'ref' and not isinstance(v, (float, Err)):
            continue
        v = num(v)
        if isinstance(v, Err):
            return v
        out.append(v)
    return out


def ev(n, get):
    k = n[0]
    if k in ('n', 's', 'b'):
        return n[1]
    if k == 'e':
        return Err(n[1])
    if k == 'blank':
        return None
    if k == 'ref':
        return get(n[1], n[2], n[3])
    if k == 'rng':
        return [get(n[1], r, c) for r in range(n[2], n[4] + 1) for c in range(n[3], n[5] + 1)]
    if k == 'neg':
        v = num(ev(n[1], get))
        return v if isinstance(v, Err) else -v
    if k == 'fn':
        return call(n[1], n[2], get)
    op, a, b = n[1], ev(n[2], get), ev(n[3], get)
    for v in (a, b):
        if isinstance(v, Err):
            return v
    if op == '&':
        return ''.join('' if v is None else (fmtnum(v) if isinstance(v, float) else str(v)) for v in (a, b))
    if op in ('=', '<>', '<', '>', '<=', '>='):
        if a is None:
            a = '' if isinstance(b, str) else 0.0
        if b is None:
            b = '' if isinstance(a, str) else 0.0
        if isinstance(a, str) and isinstance(b, str):
            a, b = a.lower(), b.lower()
        elif isinstance(a, str) or isinstance(b, str):
            a, b = (1, 0) if isinstance(a, str) else (0, 1)
        return {'=': a == b, '<>': a != b, '<': a < b, '>': a > b, '<=': a <= b, '>=': a >= b}[op]
    a, b = num(a), num(b)
    for v in (a, b):
        if isinstance(v, Err):
            return v
    if op == '+':
        return a + b
    if op == '-':
        return a - b
    if op == '*':
        return a * b
    if op == '/':
        return Err('#DIV/0!') if b == 0 else a / b
    try:
        return float(a ** b)
    except (OverflowError, ZeroDivisionError, TypeError):
        return Err('#NUM!')


def call(name, args, get):
    if name == 'IF':
        c = num(ev(args[0], get))
        if isinstance(c, Err):
            return c
        if c != 0:
            return ev(args[1], get) if len(args) > 1 else True
        return ev(args[2], get) if len(args) > 2 else False
    if name == 'IFERROR':
        v = ev(args[0], get)
        return ev(args[1], get) if isinstance(v, Err) else v
    if name in ('SUM', 'AVERAGE', 'MIN', 'MAX', 'COUNT', 'AND', 'OR'):
        vals = flat(args, get)
        if isinstance(vals, Err):
            return vals
        if name == 'SUM':
            return float(sum(vals))
        if name == 'COUNT':
            return float(len(vals))
        if name in ('AND', 'OR'):
            return (all if name == 'AND' else any)(v != 0 for v in vals)
        if not vals:
            return Err('#DIV/0!') if name == 'AVERAGE' else 0.0
        return {'AVERAGE': sum(vals) / len(vals), 'MIN': min(vals), 'MAX': max(vals)}[name]
    if name in ('ROUND', 'ROUNDUP', 'ROUNDDOWN'):
        x = num(ev(args[0], get))
        d = num(ev(args[1], get)) if len(args) > 1 else 0.0
        for v in (x, d):
            if isinstance(v, Err):
                return v
        return xround(x, int(d), {'ROUND': ROUND_HALF_UP, 'ROUNDUP': ROUND_UP, 'ROUNDDOWN': ROUND_DOWN}[name])
    if name in ('ABS', 'NOT'):
        x = num(ev(args[0], get))
        if isinstance(x, Err):
            return x
        return abs(x) if name == 'ABS' else x == 0
    raise ValueError('unsupported function ' + name)


def refs_of(node, out):
    if node[0] == 'ref':
        out.add((node[1], node[2], node[3]))
    elif node[0] == 'rng':
        for r in range(node[2], node[4] + 1):
            for c in range(node[3], node[5] + 1):
                out.add((node[1], r, c))
    elif node[0] in ('bin', 'neg', 'fn'):
        for ch in node[1:]:
            for x in (ch if isinstance(ch, list) else [ch]):
                if isinstance(x, tuple):
                    refs_of(x, out)
    return out


def make_getter(F, base, ov):
    """Evaluate a model: F maps cell key -> formula text, base holds plain values, ov overrides inputs."""
    memo, busy = {}, object()

    def get(sh, r, c):
        k = (sh, r, c)
        if k in ov:
            return ov[k]
        if k not in F:
            return base.get(k)
        if k in memo:
            return Err('#CIRC!') if memo[k] is busy else memo[k]
        memo[k] = busy
        try:
            v = ev(parse(F[k], sh), get)
        except (ValueError, TypeError, OverflowError, KeyError, AttributeError):
            v = Err('#VALUE!')
        memo[k] = v
        return v
    return get


# ---------------------------------------------------------------- reading the workbook
class Book:
    def __init__(self, path):
        z = zipfile.ZipFile(path)
        self.names = set(z.namelist())
        wb = ET.fromstring(z.read('xl/workbook.xml'))
        rmap = {r.get('Id'): r.get('Target', '') for r in ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
        ss = []
        if 'xl/sharedStrings.xml' in self.names:
            for si in ET.fromstring(z.read('xl/sharedStrings.xml')).iter(M + 'si'):
                ss.append(''.join(t.text or '' for t in si.iter(M + 't')))
        self.sheets, self.spath, self.cells, self.formula = [], {}, {}, {}
        for s in wb.iter(M + 'sheet'):
            tgt = rmap.get(s.get(RID), '')
            self.sheets.append(s.get('name'))
            self.spath[s.get('name')] = tgt[1:] if tgt.startswith('/') else 'xl/' + tgt.replace('../', '')
        SHEETMAP.update({n.lower(): n for n in self.sheets})
        for name in self.sheets:
            if self.spath[name] in self.names:
                self.read_sheet(z.read(self.spath[name]), name, ss)

    def read_sheet(self, data, name, ss):
        masters, pend, rn = {}, [], 0
        for row in ET.fromstring(data).iter(M + 'row'):
            rn = int(row.get('r')) if row.get('r') else rn + 1
            col = 0
            for c in row.findall(M + 'c'):
                m = re.match(r'([A-Z]+)(\d+)', c.get('r') or '')
                col = col2n(m.group(1)) if m else col + 1
                t, v, f = c.get('t', 'n'), c.find(M + 'v'), c.find(M + 'f')
                txt = v.text if v is not None and v.text is not None else None
                if t == 's':
                    val = ss[int(txt)] if txt is not None else None
                elif t == 'inlineStr':
                    val = ''.join(x.text or '' for x in c.iter(M + 't'))
                elif t == 'str':
                    val = txt or ''
                elif t == 'b':
                    val = None if txt is None else txt.strip() == '1'
                elif t == 'e':
                    val = Err(txt or '#N/A')
                else:
                    try:
                        val = float(txt) if txt not in (None, '') else None
                    except ValueError:
                        val = None
                key = (name, rn, col)
                if val is not None:
                    self.cells[key] = val
                if f is not None:
                    if f.get('t') == 'shared' and not (f.text or '').strip():
                        pend.append((key, f.get('si')))
                    else:
                        if f.get('t') == 'shared':
                            masters[f.get('si')] = (rn, col, f.text)
                        self.formula[key] = f.text or ''
        for key, si in pend:
            if si in masters:
                mr, mc, txt = masters[si]
                try:
                    self.formula[key] = shift(txt, key[1] - mr, key[2] - mc)
                except ValueError:
                    self.formula[key] = '#REF!'


# ---------------------------------------------------------------- layout: label column, period header, rows
WORD = re.compile(r'[a-z]+\d*|\d+')
PTOK = re.compile(r'(q\d{1,2}|h[12]|m\d{1,2}|y\d{1,2}|p\d{1,2}|w\d{1,2}|fy\d*|cy\d*|(19|20)\d\d|quarter|month|year|period|week)$')
SUBTOK = re.compile(r'(q\d{1,2}|h[12]|m\d{1,2}|p\d{1,2}|w\d{1,2}|quarter|month|week)$')
MONTHS = 'january february march april may june july august september october november december'.split()


def mon(t):
    for m in MONTHS:
        if t == m or (3 <= len(t) <= 4 and m.startswith(t)):
            return m[:3]
    return None


def period_like(v):
    if isinstance(v, float):
        return v.is_integer() and 1900 < v < 2100
    if not isinstance(v, str) or len(v) > 24:
        return False
    ts = WORD.findall(v.lower())
    return any(PTOK.match(t) or mon(t) for t in ts) or total_like(v)


def total_like(v):
    ts = set(WORD.findall(str(v).lower()))
    return bool(ts & {'total', 'sum', 'ytd', 'annual'}) or {'full', 'year'} <= ts


def gran(v):
    """Granularity of a header: m(onth) w(eek) q(uarter) p(eriod) h(alf) y(ear), t(otal) or x."""
    if isinstance(v, float):
        return 'y'
    ts = WORD.findall(str(v).lower())
    if total_like(v):
        return 't'
    for t in ts:
        if re.match(r'q\d', t) or t == 'quarter':
            return 'q'
        if re.match(r'h[12]$', t):
            return 'h'
        if mon(t) or re.match(r'm\d', t) or t == 'month':
            return 'm'
        if re.match(r'w\d', t) or t == 'week':
            return 'w'
        if re.match(r'p\d', t) or t == 'period':
            return 'p'
    return 'y' if any(re.match(r'(fy|cy)\d*$|(19|20)\d\d$|y\d|year', t) for t in ts) else 'x'


def sub_annual(v):
    return any(SUBTOK.match(t) or mon(t) for t in WORD.findall(str(v).lower()))


def pkey(s):
    if isinstance(s, float) and s.is_integer():
        s = str(int(s))
    return frozenset(mon(t) or t for t in WORD.findall(str(s).lower()))


def garbled(v):
    """Text where a number should be: '2?.4', '#####', '3\ufffd.5' (a damaged cell, not a label)."""
    return isinstance(v, str) and bool(re.search(r'\d|[?#\ufffd]', v) or any(ord(ch) > 127 for ch in v))


def lkey(s):
    return ' '.join(re.findall(r'[a-z0-9%]+', str(s).lower()))


class Grid:
    pass


class Row:
    def __init__(self, g, r, label):
        self.g, self.r, self.rid, self.label = g, r, (g.name, r), label
        self.vals, self.state, self.surv = [], [], {}
        self.choice, self.cands, self.rivals, self.equiv, self.seed = None, [], [], [], None
        self.rule, self.waiting, self.answered, self.probe, self.worded, self.round_by = None, False, False, None, False, None


def layout(book, name):
    cells = {(r, c): v for (s, r, c), v in book.cells.items() if s == name}
    byrow = {}
    for (r, c), v in cells.items():
        byrow.setdefault(r, {})[c] = v
    lab = None
    for c in sorted({c for r, c in cells}):
        txt = sum(1 for (r, cc), v in cells.items() if cc == c and isinstance(v, str) and v.strip() and not period_like(v))
        nums = sum(1 for (r, cc), v in cells.items() if cc == c and isinstance(v, float))
        if txt >= 2 and txt >= nums:
            lab = c
            break
    if lab is None:
        return None
    hr, best = None, 1
    for r in sorted(byrow):
        n = sum(1 for c, v in byrow[r].items() if c > lab and period_like(v))
        if n > best:
            hr, best = r, n
    if hr is None:
        return None
    heads = [(c, v) for c, v in sorted(byrow[hr].items()) if c > lab and period_like(v)]
    kinds = [gran(v) for c, v in heads]
    order_k = 'mwqphyx'
    main = max((k for k in kinds if k != 't'), key=lambda k: (kinds.count(k), -order_k.index(k)), default=None)
    per = [(c, v) for (c, v), k in zip(heads, kinds) if k == main]  # the finest common granularity; others are totals
    g = Grid()
    g.name, g.lab, g.hr = name, lab, hr
    g.pcols = [c for c, v in per]
    g.plabels = [str(int(v)) if isinstance(v, float) else str(v) for c, v in per]
    g.tcols = [c for c, v in heads if c not in g.pcols]
    g.tlabels = {c: str(v) for c, v in heads if c not in g.pcols}
    low = ' '.join(g.plabels).lower()
    g.pw = 'quarter' if re.search(r'\bq[1-4]', low) else 'month' if any(mon(t) for t in WORD.findall(low)) else \
        'year' if re.search(r'(19|20)\d\d|fy', low) else 'period'
    g.rows = []
    for r in sorted(byrow):
        lbl = byrow[r].get(lab)
        if r <= hr or not isinstance(lbl, str) or not lbl.strip():
            continue
        if any(isinstance(byrow[r].get(c), (float, Err)) or (name, r, c) in book.formula for c in g.pcols):
            g.rows.append(r)
    return g if g.rows else None


# ---------------------------------------------------------------- formula templates (expression trees)
# ('R', rowid, lag) row operand in the same sheet (lag 1 = previous period) | ('S', cellkey) assumption cell
# ('K', v) literal | ('+'|'-'|'*'|'/', a, b) | ('SUM', (r1, r2), rowids) | ('IF', op, x, t, a, b) | ('RND', e, d)
# ('HSUM'|'HAVG', c1, c2) horizontal sum/average on the row itself (totals column) | ('F', {col: text}) survived
ROWS, SV, SL, RULEK, META, PCOLS, UNK, SOLVED = {}, {}, {}, {}, {}, {}, {}, {}
USE_UNK, ZG = [False], [False]


def cell_formula(e, c, g, row, colof=None):
    """The formula text for one cell, with IF(den=0,0,...) around divisions when the evidence asks for it."""
    txt = ren(e, c, g, row, colof)
    if ZG[0] and e[0] != 'F':
        for d in dict.fromkeys(ren(n[2], c, g, row, colof) for n in nodes(e) if n[0] == '/' and n[2][0] == 'R'):
            txt = 'IF(%s=0,0,%s)' % (d, txt)
    return txt


def all_text(o):
    if isinstance(o, str):
        yield o
    elif isinstance(o, dict):
        for v in o.values():
            yield from all_text(v)
    elif isinstance(o, list):
        for v in o:
            yield from all_text(v)
PREC = {'+': 1, '-': 1, '*': 2, '/': 2}
K1 = ('K', 1.0)


def vev(e, c, g):
    k = e[0]
    if k == 'R':
        return g(e[1], c - e[2]) if c - e[2] >= 0 else None
    if k == 'S':
        return SV.get(e[1])
    if k == 'K':
        return e[1]
    if k == 'SUM':
        s = 0.0
        for rid in e[2]:
            v = g(rid, c)
            if v is None:
                return None
            s += v
        return s
    if k == 'IF':
        x, t = vev(e[2], c, g), vev(e[3], c, g)
        if x is None or t is None:
            return None
        return vev(e[4] if (x > t if e[1] == '>' else x >= t) else e[5], c, g)
    if k == 'RND':
        v = vev(e[1], c, g)
        return None if v is None else xround(v, e[2])
    if k in ('MIN', 'MAX'):
        a, b = vev(e[1], c, g), vev(e[2], c, g)
        return None if a is None or b is None else (min if k == 'MIN' else max)(a, b)
    if k not in PREC:
        return None
    a = vev(e[1], c, g)
    if a is None:
        return None
    b = vev(e[2], c, g)
    if b is None:
        return None
    if k == '+':
        return a + b
    if k == '-':
        return a - b
    if k == '*':
        return a * b
    return a / b if b else None


def ren(e, c, g, row, colof=None):
    colof = colof or (lambda cc, lag: g.pcols[cc - lag])
    k = e[0]
    if k == 'R' and len(e[1]) == 3:  # a row on another sheet, aligned by period header
        return '%s!%s%d' % (qsheet(e[1][0]), n2col(PCOLS[(e[1][0], e[1][2])][c - e[2]]), e[1][1])
    if k == 'R':
        return '%s%d' % (n2col(colof(c, e[2])), e[1][1])
    if k == 'S':
        return ('' if e[1][0] == g.name else qsheet(e[1][0]) + '!') + a1(e[1][1], e[1][2], True)
    if k == 'K':
        return fmtnum(e[1])
    if k == 'F':
        return e[1][c]
    if k == 'SUM':
        col = n2col(colof(c, 0))
        return 'SUM(%s%d:%s%d)' % (col, e[1][0], col, e[1][1])
    if k in ('HSUM', 'HAVG'):  # only the period columns, skipping any subtotal columns in between
        runs = []
        for cc in g.pcols[e[1]:e[2] + 1]:
            if runs and cc == runs[-1][1] + 1:
                runs[-1][1] = cc
            else:
                runs.append([cc, cc])
        parts = [('%s%d' % (n2col(x), row)) + ('' if x == y else ':%s%d' % (n2col(y), row)) for x, y in runs]
        return '%s(%s)' % ('SUM' if k == 'HSUM' else 'AVERAGE', ','.join(parts))
    if k == 'IF':
        return 'IF(%s%s%s,%s,%s)' % tuple([ren(e[2], c, g, row, colof), e[1]] + [ren(x, c, g, row, colof) for x in e[3:]])
    if k == 'RND':
        return 'ROUND(%s,%d)' % (ren(e[1], c, g, row, colof), e[2])
    if k in ('MIN', 'MAX'):
        return '%s(%s,%s)' % (k, ren(e[1], c, g, row, colof), ren(e[2], c, g, row, colof))
    a, b = ren(e[1], c, g, row, colof), ren(e[2], c, g, row, colof)
    if e[1][0] in PREC and PREC[e[1][0]] < PREC[k]:
        a = '(%s)' % a
    if e[2][0] in PREC and (PREC[e[2][0]] < PREC[k] or (PREC[e[2][0]] == PREC[k] and k in '-/')):
        b = '(%s)' % b
    return a + k + b


def desc(e, pw='period'):
    k = e[0]
    if k == 'R':
        lab = ROWS[e[1]].label + (' on %s' % e[1][0] if len(e[1]) == 3 else '')
        return lab if e[2] == 0 else "previous %s's %s" % (pw, lab)
    if k == 'S':
        return '%s (%s)' % (SL.get(e[1], 'assumption'), cref(e[1]))
    if k == 'K':
        return fmtnum(e[1])
    if k == 'F':
        return 'the formula that survived in this row'
    if k == 'SUM':
        return 'sum of %s through %s' % (ROWS[e[2][0]].label, ROWS[e[2][-1]].label)
    if k in ('HSUM', 'HAVG'):
        return ('sum' if k == 'HSUM' else 'average') + ' of the row across the periods'
    if k == 'IF':
        return 'if %s %s %s then %s, otherwise %s' % (desc(e[2], pw), e[1], desc(e[3], pw), desc(e[4], pw), desc(e[5], pw))
    if k == 'RND':
        return '%s, rounded to %d decimals' % (desc(e[1], pw), e[2])
    if k in ('MIN', 'MAX'):
        return '%s of %s and %s' % ('the smaller' if k == 'MIN' else 'the larger', desc(e[1], pw), desc(e[2], pw))
    sym = {'+': '+', '-': '-', '*': 'x', '/': '/'}[k]
    a, b = desc(e[1], pw), desc(e[2], pw)
    if e[1][0] in PREC and PREC[e[1][0]] < PREC[k]:
        a = '(%s)' % a
    if e[2][0] in PREC and (PREC[e[2][0]] <= PREC[k]):
        b = '(%s)' % b
    return '%s %s %s' % (a, sym, b)


def nodes(e):
    yield e
    if e[0] in PREC or e[0] in ('IF', 'RND', 'MIN', 'MAX'):
        for x in e[1:]:
            if isinstance(x, tuple) and x and isinstance(x[0], str):
                yield from nodes(x)


def uses_lag(e):
    return any(n[0] == 'R' and n[2] == 1 for n in nodes(e))


def leaves(e):
    return [n for n in nodes(e) if n[0] in ('R', 'S', 'K', 'SUM')]


def gv(rid, c):
    vals = ROWS[rid].vals
    return vals[c] if 0 <= c < len(vals) else None


def checker(T, allow_round, miss=0, start=0):
    """start=-1: the formula only holds from some column on (actuals typed first, a forecast after)."""
    auto, start = start < 0, max(start, 0)
    S = [c for c, v in enumerate(T.vals) if v is not None and c >= start]
    need = 2 if len(S) < 3 else 3
    dec = None
    if S and all(abs(T.vals[c] * 100 - round(T.vals[c] * 100)) < 1e-6 for c in S):
        dec = 0 if all(float(T.vals[c]).is_integer() for c in S) else 2

    def chk(e):
        unk = {n[1] for n in leaves(e) if n[0] == 'S' and n[1] not in SV}
        if not unk:
            return core(e)
        u = unk.pop()
        x = None if unk else solve_unknown(e[1] if e[0] == 'RND' else e, u, T, S)
        if x is None:
            return None
        SV[u] = x
        try:
            res = core(e)
        finally:
            del SV[u]
        if res is not None:
            SOLVED[(T.rid, res)] = (u, x)
        return res

    def core(e):
        n, loose, bad = 0, False, []
        for c in S:
            p = vev(e, c, gv)
            if p is None:
                continue
            y = T.vals[c]
            d = abs(p - y)
            if d > tol(y):
                if dec is not None and allow_round and d <= 0.5 * 10 ** -dec + tol(y):
                    loose = True
                else:
                    bad.append(c)
                    if len(bad) > miss and not auto:
                        return None
                    continue
            n += 1
        k = start
        if auto:
            if not bad:
                return None
            k = max(bad) + 1
            n = sum(1 for c in S if c >= k and vev(e, c, gv) is not None)
            bad = []
        if n < need or (bad and n < 3) or (auto and n < 3):
            return None
        e2 = ('RND', e, dec) if loose else e
        for c in S:
            p = vev(e2, c, gv)
            if c >= k and c not in bad and p is not None and abs(p - T.vals[c]) > tol(T.vals[c]):
                return None
        META[(T.rid, e2)] = (k, tuple(bad))
        return e2
    return chk


def solve_unknown(e, u, T, S):
    """Value of a damaged assumption cell that makes the template reproduce the row (a nice number only)."""
    best = None
    for c in S:
        SV[u] = 0.0
        f0 = vev(e, c, gv)
        SV[u] = 1.0
        f1 = vev(e, c, gv)
        del SV[u]
        if f0 is not None and f1 is not None and f0 != f1 and (best is None or abs(f1 - f0) > abs(best[1] - best[0])):
            best = (f0, f1, T.vals[c])
    if best is None:
        return None
    f0, f1, y = best
    x = (y - f0) / (f1 - f0)
    for d in (0, 2, 3, 4):
        if abs(round(x, d) - x) <= 1e-6 * max(1.0, abs(x)) + 0.0051 / abs(f1 - f0):
            return round(x, d)
    return None


def words(s):
    stop = {'of', 'the', 'and', 'per', 'to', 'in', 'on', 'for', 'by', 'net', 'total', 'rate', 'value'}
    return {w for w in re.findall(r'[a-z]+', s.lower()) if len(w) > 2 and w not in stop}


THRK = set()


def threshold_like(node):
    if node[0] == 'K':
        return node[1] == 0.0 or node[1] in THRK
    lab = SL.get(node[1], '').lower()
    return bool(re.search(r'thresh|minimum|\bmin\b|cap|limit|tier|over|above|cutoff|cut-off|break|floor|ceiling|target', lab)) \
        and not re.search(r'rate|%|percent|pct|share|price|cost|fee', lab)


def unknowns(T):
    """Damaged assumption cells this row may solve: their label shares a word with the row's label."""
    return [('S', u) for u in UNK if u not in SV and words(SL[u]) & words(T.label)] if USE_UNK[0] else []


def tier1(T, ops, same, scs, consts):
    R = lambda rid, lag=0: ('R', rid, lag)
    scs = scs + unknowns(T)
    vals = [v for v in T.vals if v is not None]
    for A in ops:
        yield 1.0, R(A)
    for s in scs:  # a row that repeats an assumption (one typed override allowed later)
        sv = SV.get(s[1]) if s[0] == 'S' else None
        if s[0] == 'S' and len(vals) >= 2 and (sv is None and len(set(vals)) == 1 or sv is not None and sum(
                1 for v in vals if abs(sv - v) <= tol(v)) >= max(2, len(vals) - 1)):
            yield 1.0 if sv is not None else 1.5, s
    for j in range(len(ops)):
        for i in range(j - 1, -1, -1):
            rids = tuple(x for x in same if ops[i][1] <= x[1] <= ops[j][1])
            yield 2.0 + 0.01 * len(rids), ('SUM', (ops[i][1], ops[j][1]), rids)
    for A in ops:
        for B in ops:
            if A != B:
                yield 2.0, ('-', R(A), R(B))
                yield 2.0, ('/', R(A), R(B))
                if A < B:
                    yield 2.0, ('+', R(A), R(B))
                    yield 2.0, ('*', R(A), R(B))
    for A in [R(x) for x in ops] + [R(x, 1) for x in same if x != T.rid]:
        lagc = 0.3 * A[2]
        if A[2]:
            yield 2.2, A
        for s in scs:
            c = 2.1 + lagc + (0.5 if s[0] == 'K' else 0)
            yield c, ('*', A, s)
            yield c + 0.1, ('/', A, s)
            if not A[2]:
                yield c + 1, ('*', A, ('+', K1, s))
                yield c + 1, ('*', A, ('-', K1, s))
                yield c + 1.2, ('+', A, s)
                yield c + 1.2, ('-', A, s)
        if not A[2]:
            for v in consts:
                yield 3.5, ('*', A, ('K', v))
                yield 3.6, ('/', A, ('K', v))
    P = R(T.rid, 1)
    for s in scs:
        yield 3.2 + (0.5 if s[0] == 'K' else 0), ('*', P, ('+', K1, s))
        yield 3.4 + (0.5 if s[0] == 'K' else 0), ('+', P, s)
    for B in ops:
        yield 3.2, ('+', P, R(B))
        yield 3.3, ('-', P, R(B))
        yield 3.3, ('*', P, ('+', K1, R(B)))
        yield 3.0, ('-', ('/', R(B), R(B, 1)), K1)


def tier2(T, ops, same, scs):
    R = lambda rid, lag=0: ('R', rid, lag)
    scs = scs + unknowns(T)
    for i in range(len(ops)):
        for j in range(i + 1, len(ops)):
            for k in range(j + 1, len(ops)):
                trio = (ops[i], ops[j], ops[k])
                for signs in ((1, 1, 1), (1, 1, -1), (1, -1, 1), (-1, 1, 1), (1, -1, -1), (-1, 1, -1), (-1, -1, 1)):
                    pos = [R(x) for x, s in zip(trio, signs) if s > 0]
                    neg = [R(x) for x, s in zip(trio, signs) if s < 0]
                    e = pos[0]
                    for x in pos[1:]:
                        e = ('+', e, x)
                    for x in neg:
                        e = ('-', e, x)
                    yield 4.0, e
    P = R(T.rid, 1)
    for B in ops:
        for C in ops:
            if B != C:
                yield 4.2, ('-', ('+', P, R(B)), R(C))
            if B < C:
                yield 4.1, ('/', ('+', R(B), R(C)), ('K', 2.0))
                for sc in scs:
                    yield 4.3, ('*', ('*', R(B), R(C)), sc)
                    yield 4.4, ('*', ('*', R(B), R(C)), ('-', K1, sc))
    S = [c for c, v in enumerate(T.vals) if v is not None]
    sval = lambda s: SV.get(s[1]) if s[0] == 'S' else s[1]
    loose = 0.0051 if all(abs(T.vals[c] * 100 - round(T.vals[c] * 100)) < 1e-6 for c in S) else 0.0
    near = lambda a, b: abs(a - b) <= tol(b) + loose
    for A in ops:  # linear: x*b + a, and caps or floors: MIN(x*b, cap), MAX(x*b, floor)
        xs = ROWS[A].vals
        cols = [c for c in S if xs[c] is not None]
        if len(cols) < 2:
            continue
        for s1 in [K1] + [x for x in scs if sval(x) is not None]:
            b = sval(s1)
            p = {c: xs[c] * b for c in cols}
            if s1 is not K1:
                need = T.vals[cols[0]] - p[cols[0]]
                for s2 in scs:
                    if sval(s2) is not None and abs(sval(s2) - need) <= tol(need) + loose:
                        yield 3.8, ('+', ('*', R(A), s1), s2)
                    if sval(s2) is not None and abs(sval(s2) + need) <= tol(need) + loose:
                        yield 3.8, ('-', ('*', R(A), s1), s2)
            diff = [c for c in cols if not near(p[c], T.vals[c])]
            if not diff or len(diff) == len(cols) or any(not near(T.vals[c], T.vals[diff[0]]) for c in diff):
                continue
            cap = T.vals[diff[0]]
            kind = 'MIN' if all(p[c] > cap for c in diff) else 'MAX' if all(p[c] < cap for c in diff) else None
            base = R(A) if s1 is K1 else ('*', R(A), s1)
            for s2 in (scs + [('K', 0.0)] if kind else []):
                if sval(s2) is not None and near(sval(s2), cap):
                    yield 4.5, (kind, base, s2)
    # tiered IF: the data must fall on both sides of the threshold
    S = [c for c, v in enumerate(T.vals) if v is not None]
    for A in ops:
        xs = ROWS[A].vals
        for t in sorted([x for x in scs if sval(x) is not None], key=lambda s: not threshold_like(s)) + [('K', 0.0)]:
            tv = sval(t)
            hi = [c for c in S if xs[c] is not None and xs[c] > tv]
            lo = [c for c in S if xs[c] is not None and xs[c] < tv]
            if not hi or not lo:
                continue
            for a in branch(T, A, hi, scs):
                for b in branch(T, A, lo, scs):
                    if a != b:
                        for op in ('>=', '>'):
                            yield 5.0 + (0 if threshold_like(t) else 0.5), ('IF', op, R(A), t, a, b)
    ths = sorted([s for s in scs if threshold_like(s) and sval(s) is not None], key=sval)
    rates = [x for x in scs if not threshold_like(x) and (sval(x) is None or 0 < abs(sval(x)) < 1)]
    for i, t1 in enumerate(ths):  # tiered schedules on one row (e.g. units), applied to another (e.g. price)
        for t2 in [None] + ths[i + 1:]:
            for A in ops:
                for B in ops:
                    if A == B:
                        continue
                    for r1 in rates:
                        if t2 is None:  # one marginal band: B x MAX(0, A - t1) x r1
                            yield 5.2, ('*', ('*', R(B), ('MAX', ('K', 0.0), ('-', R(A), t1))), r1)
                            continue
                        for r2 in rates:
                            if r2 == r1:
                                continue
                            yield 5.2, ('*', R(B), ('+', ('*', ('MAX', ('K', 0.0), ('-', ('MIN', R(A), t2), t1)), r1),
                                                    ('*', ('MAX', ('K', 0.0), ('-', R(A), t2)), r2)))
                            for o2 in ('>=', '>'):  # whole-band rate on B decided by A
                                for o1 in ('>=', '>'):
                                    yield 5.3, ('*', R(B), ('IF', o2, R(A), t2, r2, ('IF', o1, R(A), t1, r1, ('K', 0.0))))
    for A in ops:  # two tiers: IF(x>t2, hi, IF(x>t1, mid, lo))
        xs = ROWS[A].vals
        for i, t1 in enumerate(ths):
            for t2 in ths[i + 1:]:
                v1, v2 = sval(t1), sval(t2)
                if v2 <= v1:
                    continue
                lo = [c for c in S if xs[c] is not None and xs[c] < v1]
                mid = [c for c in S if xs[c] is not None and v1 < xs[c] < v2]
                hi = [c for c in S if xs[c] is not None and xs[c] > v2]
                if not (lo and mid and hi):
                    continue
                for a in branch(T, A, hi, scs):
                    for m in branch(T, A, mid, scs):
                        for b in branch(T, A, lo, scs):
                            for o2 in ('>=', '>'):
                                for o1 in ('>=', '>'):
                                    yield 5.5, ('IF', o2, R(A), t2, a, ('IF', o1, R(A), t1, m, b))


def branch(T, A, cols, scs):
    ys = [T.vals[c] for c in cols]
    xs = [ROWS[A].vals[c] for c in cols]
    loose = 0.0051 if all(abs(y * 100 - round(y * 100)) < 1e-6 for y in ys) else 0.0
    if all(abs(y) <= tol(y) + loose for y in ys):
        return [('K', 0.0)]
    if any(x == 0 for x in xs):
        return []
    big = max(range(len(xs)), key=lambda i: abs(xs[i]))
    r = ys[big] / xs[big]
    val = lambda s: SV.get(s[1]) if s[0] == 'S' else s[1]
    unk = [s for s in scs if s[0] == 'S' and val(s) is None]
    if any(abs(y - x * r) > tol(y) + 2 * loose for x, y in zip(xs, ys)):
        consts = [s for s in scs if val(s) is not None and all(abs(val(s) - y) <= tol(y) + loose for y in ys)]
        flat = all(abs(y - ys[0]) <= tol(y) + loose for y in ys)
        return consts[:2] or (unk[:2] if flat else [])  # a flat amount in this tier
    slack = 1e-9 * max(1, abs(r)) + (2 * loose / abs(xs[big]) if loose else 0)
    return [('*', ('R', A, 0), s) for s in scs if val(s) is not None and abs(val(s) - r) <= slack] or \
        [('*', ('R', A, 0), s) for s in unk[:2]]


def tierx(T, ops, px, scs):
    """Pulls from rows on other sheets aligned by period header: =Model!C8, a rate per period, a ratio."""
    R = lambda rid, lag=0: ('R', rid, lag)
    for X in px:
        yield 1.1, R(X)
    same = [x for x in px if len(x) == 2]
    for i in range(len(same)):  # a total placed above its lines: =SUM(C9:C12)
        for j in range(i + 1, len(same)):
            rids = tuple(x for x in same if same[i][1] <= x[1] <= same[j][1])
            if all(T.rid not in reach(x) for x in rids):
                yield 2.0, ('SUM', (same[i][1], same[j][1]), rids)
    for X in px:
        for A in ops:
            for op in ('*', '/', '+', '-'):
                yield 2.1, (op, R(A), R(X))
                if op in '/-':
                    yield 2.2, (op, R(X), R(A))
        for sc in scs:
            yield 2.2, ('*', R(X), sc)
            yield 2.3, ('/', R(X), sc)
            yield 3.2, ('*', R(X), ('+', K1, sc))
            yield 3.2, ('*', R(X), ('-', K1, sc))
        yield 3.3, ('*', R(T.rid, 1), ('+', K1, R(X)))
        yield 3.3, ('+', R(T.rid, 1), R(X))


def make_proxies(grids):
    out = {}
    for g in grids:
        for h in grids:
            idx = []
            for lab in g.plabels:
                js = [j for j, l2 in enumerate(h.plabels) if pkey(l2) == pkey(lab)]
                idx.append(js[0] if len(js) == 1 else None)
            if h is g or None in idx:
                continue
            PCOLS[(h.name, g.name)] = [h.pcols[j] for j in idx]
            for r in h.rows:
                X, Y = ROWS[(h.name, r)], Row(h, r, ROWS[(h.name, r)].label)
                Y.rid, Y.src = (h.name, r, g.name), X.rid
                Y.vals, Y.state = [X.vals[j] for j in idx], [X.state[j] for j in idx]
                ROWS[Y.rid] = Y
                out.setdefault(g.name, []).append(Y.rid)
    return out


def reach(rid, seen=None):
    """Every row a row's chosen formula depends on, following pulls to other sheets."""
    seen = set() if seen is None else seen
    T = ROWS.get(rid)
    if T is None or rid in seen:
        return seen
    seen.add(rid)
    for e in (T.choice, T.seed):
        if e is not None and e[0] != 'F':
            for n in leaves(e):
                for x in (n[2] if n[0] == 'SUM' else [n[1]] if n[0] == 'R' else []):
                    reach(x[:2], seen)
    return seen


def tier3(T, ops, same, scs):
    vals = [v for v in T.vals if v is not None]
    S = [c for c, v in enumerate(T.vals) if v is not None]
    nice = lambda k: k not in (0.0, 1.0) and abs(k * 1e4 - round(k * 1e4)) < 1e-6 * max(1.0, abs(k))
    for A in (ops if len(S) >= 4 else []):  # a constant typed inside the formula, e.g. =B5*1.1 or =B5+500
        xs = ROWS[A].vals
        c = next((c for c in S if xs[c]), None)
        if c is None:
            continue
        for k, mk in ((T.vals[c] / xs[c], lambda k: ('*', ('R', A, 0), ('K', k))),
                      (T.vals[c] - xs[c], lambda k: ('+', ('R', A, 0), ('K', k)))):
            k = round(k, 4)
            if nice(k):
                yield 5.5, mk(k)
    if len(vals) >= 3 and len(set(vals)) == 1:
        yield 6.0, ('R', T.rid, 1)


HINTS = [(r'total|sum|subtotal', ('SUM', '+')), (r'^net|net ', ('-',)), (r'%|margin|ratio|share|per ', ('/',)),
         (r'growth|change', ('G',)), (r'cumulative|running|to date', ('+',)), (r'discount|commission|bonus|tier', ('IF',))]


def hint_bonus(T, e):
    kind = 'G' if e[0] == '-' and e[1][0] == '/' and uses_lag(e) else e[0] if e[0] != 'RND' else e[1][0]
    lab = T.label.lower()
    return -0.25 if any(re.search(p, lab) and kind in ks for p, ks in HINTS) else 0.0


def infer_row(T, ops, same, scs, consts, gen=None):
    found, tw = [], words(T.label)
    P, n = len(T.vals), sum(1 for v in T.vals if v is not None)
    # exact fits first; ROUND(...) next; then one typed override; then a forecast that starts partway
    passes = [(False, 0, 0, 3), (True, 0, 0, 3)] + ([('unk', 0, 0, 2), ('unk', 1, 0, 2)] if UNK and not gen else []) + \
        ([(False, 1, 0, 2), (True, 1, 0, 1)] if n >= 4 else []) + [(False, 0, -1, 1), (True, 0, -1, 1)]
    for allow_round, miss, start, ntier in passes:
        USE_UNK[0] = allow_round == 'unk'
        if USE_UNK[0]:
            allow_round = bool(miss)
            miss = 0
        chk = checker(T, allow_round, miss, start)
        tiers = (gen(),) if gen else (tier1(T, ops, same, scs, consts), tier2(T, ops, same, scs),
                                      tier3(T, ops, same, scs))[:ntier]
        for tier in tiers:
            seen = set()
            for cost, e in tier:
                e2 = chk(e)
                if e2 is not None and e2 not in seen:
                    seen.add(e2)
                    lv = leaves(e2)
                    dist = sum(abs(T.r - n[1][1]) for n in lv if n[0] == 'R') * 0.001
                    lw = set().union(*[words(ROWS[n[1]].label) for n in lv if n[0] == 'R' and n[1] != T.rid] +
                                     [words(SL.get(n[1], '')) for n in lv if n[0] == 'S'])
                    found.append((cost + hint_bonus(T, e2) + dist - 0.15 * len(tw & lw) + 0.05 * meta(T, e2)[0],
                                  len(found), e2))
            if found:
                break
        if found:
            break
    USE_UNK[0] = False
    is_if = lambda e: any(n[0] == 'IF' for n in nodes(e))
    good_t = lambda e: all(threshold_like(n[3]) for n in nodes(e) if n[0] == 'IF')
    if any(good_t(e) for _, _, e in found if is_if(e)):
        found = [f for f in found if good_t(f[2])]  # plain rates are not thresholds when a real threshold fits
    rel = lambda e: all(n[3][0] == 'K' or words(SL.get(n[3][1], '')) & (tw | words(desc(n[2]))) for n in nodes(e) if n[0] == 'IF')
    if any(rel(e) for _, _, e in found if is_if(e)):
        found = [f for f in found if not is_if(f[2]) or rel(f[2])]  # thresholds that belong to this row win
    if any(n[0] in ('MIN', 'MAX') for _, _, e in found for n in nodes(e)):
        found = [f for f in found if not is_if(f[2])]  # a cap or floor explains the switch without a guessed cut-off
    found.sort()
    return [e for _, _, e in found]


def one_sided(T, ops, scs):
    """The data never cross a threshold assumption that belongs to this row: offer the tiered readings too."""
    tw, K0 = words(T.label), ('K', 0.0)
    ths = [s for s in scs if s[0] == 'S' and threshold_like(s) and words(SL[s[1]]) & tw]
    known = [c for c, v in enumerate(T.vals) if v is not None]
    out = []
    for t in ths:
        tv = SV[t[1]]
        e = T.choice[1] if T.choice and T.choice[0] == 'RND' else T.choice
        if e and e[0] == '*' and e[1][0] == 'R' and e[1][2] == 0:
            xs = [gv(e[1][1], c) for c in known if gv(e[1][1], c) is not None]
            if xs and min(xs) > tv:
                out += [('IF', op, e[1], t, T.choice, K0) for op in ('>', '>=')]
        elif T.choice is None and known and not any(T.vals[c] for c in known):
            rates = [s for s in scs if s[0] == 'S' and not threshold_like(s) and words(SL[s[1]]) & tw]
            for A in reversed(ops if len(rates) == 1 else []):
                xs = [gv(A, c) for c in known if gv(A, c) is not None]
                if len(xs) >= 2 and tv / 10 < max(xs) < tv:
                    out += [('IF', op, ('R', A, 0), t, ('*', ('R', A, 0), rates[0]), K0) for op in ('>', '>=')]
                    break
    return out


def find_seed(T, ops, scs):
    y = T.vals[0]
    if y is None:
        return None
    cands = [s for s in scs if s[0] == 'S' and abs(SV[s[1]] - y) <= tol(y)]
    cands += [('R', A, 0) for A in ops if gv(A, 0) is not None and abs(gv(A, 0) - y) <= tol(y) and y != 0]
    if len(cands) > 1:
        best = [x for x in cands if words(desc(x)) & words(T.label)]
        cands = best if len(best) == 1 else cands
    return cands[0] if len(cands) == 1 else None


# ---------------------------------------------------------------- probing alternatives
def close(a, b, rel=1e-7):
    if isinstance(a, float) and isinstance(b, float):
        return abs(a - b) <= rel * max(1.0, abs(a), abs(b))
    return type(a) == type(b) and (isinstance(a, Err) or a == b)


def meta(T, e):
    return META.get((T.rid, e), (0, ()))


def covered(T, i):
    """A blank cell gets the row's formula only when the row's pattern clearly runs through that column."""
    if T.state[i] != 'blank':
        return True
    has = [j for j, st in enumerate(T.state) if st in ('num', 'form', 'err', 'broken')]
    blanks = sum(1 for st in T.state if st == 'blank')
    return (any(j < i for j in has) and any(j > i for j in has)) or (blanks <= 1 and len(has) >= 3)


def has_formula(T, e, i):
    st, bad = meta(T, e)
    return T.state[i] not in ('form', 'text') and not (i == 0 and e[0] != 'F' and uses_lag(e)) and \
        i >= st and i not in bad and covered(T, i)


def threshold_probe(T, e0, e1):
    for e in (e0, e1):
        for n in nodes(e):
            if n[0] != 'IF' or n[2][0] != 'R':
                continue
            tv = vev(n[3], 0, gv)
            for i in range(len(T.vals)):
                if not (has_formula(T, e0, i) and has_formula(T, e1, i)):
                    continue
                for d in (-0.01, 0.0, 0.01):
                    g2 = (lambda x, i, val: (lambda rid, c: val if (rid == x and c == i) else gv(rid, c)))(n[2][1], i, tv + d)
                    a, b = vev(e0, i, g2), vev(e1, i, g2)
                    if a is None or b is None:
                        break
                    if not close(a, b):
                        return {'kind': 'threshold', 'x': n[2][1], 'value': tv + d, 'col': i, 'outputs': [a, b]}
                else:
                    break
    return None


def pair_diff(T, e0, e1, getters):
    g = T.g
    for k, get in enumerate(getters):
        for i in range(len(T.vals)):
            if not (has_formula(T, e0, i) and has_formula(T, e1, i)):
                continue
            try:
                a = ev(parse(ren(e0, i, g, T.r), g.name), get)
                b = ev(parse(ren(e1, i, g, T.r), g.name), get)
            except ValueError:
                continue
            if not close(a, b):
                return {'kind': 'scenario', 'probe': k + 1, 'col': i, 'outputs': [a, b]}
    return threshold_probe(T, e0, e1)


def subst(e, old, new):
    if e == old:
        return new
    return tuple(subst(x, old, new) if isinstance(x, tuple) else x for x in e)


def op_from_words(rules_ev, tv):
    """'1,000 units or more' / 'at least' / 'below 1,000: none' -> '>=', 'more than' -> '>', 'over'/'above' -> None."""
    for r in rules_ev:
        txt = str(r.get('text', ''))
        for m in re.finditer(r'\$?(\d[\d,]*(?:\.\d+)?)', txt):
            try:
                if abs(float(m.group(1).replace(',', '')) - tv) > tol(tv):
                    continue
            except ValueError:
                continue
            before, after = txt[max(0, m.start() - 24):m.start()].lower(), txt[m.end():m.end() + 30].lower()
            if re.search(r'^\s*(\w+\s+){0,2}(or more|or above|or over|and above|and over|and up|or higher|\+)', after) or \
                    re.search(r'(at least|minimum of|min\.?|from|>=|\u2265)\s*$', before) or \
                    re.search(r'(below|under|less than|fewer than)\s*$', before):
                return '>='
            if re.search(r'(more than|greater than|exceeding|exceeds|in excess of)\s*$', before):
                return '>'
    return None


def unround(e):
    return e[1] if e and e[0] == 'RND' else e


def strip_s(e):
    if isinstance(e, tuple) and e and e[0] == 'S':
        return ('S',)
    return tuple(strip_s(x) if isinstance(x, tuple) else x for x in e)


def support(T, e):
    lw = set().union(*[words(ROWS[n[1]].label) for n in leaves(e) if n[0] == 'R' and n[1] != T.rid] +
                     [words(SL.get(n[1], '')) for n in leaves(e) if n[0] == 'S'])
    return len(words(T.label) & lw)


def label_score(T, e):
    ctx = words(T.label) | {w for n in leaves(e) if n[0] == 'R' for w in words(ROWS[n[1]].label)}
    return sum(len(words(SL.get(n[1], '')) & ctx) for n in leaves(e) if n[0] == 'S')


def build_F(book, rows):
    F = {k: f for k, f in book.formula.items() if '#REF!' not in f.upper()}
    for T in rows:
        e = T.choice
        if e is None:
            continue
        for i in range(len(T.vals)):
            key = (T.g.name, T.r, T.g.pcols[i])
            if i == 0 and T.seed is not None and T.state[0] not in ('form', 'text') and e[0] != 'F':
                F[key] = cell_formula(T.seed, 0, T.g, T.r)
            elif has_formula(T, e, i):
                F[key] = cell_formula(e, i, T.g, T.r)
    return F


def scenario(vals, F, rng):
    ov = {}
    for key, v in vals.items():
        if key not in F and isinstance(v, float) and v != 0:
            ov[key] = v * rng.uniform(0.6, 1.4)
    for T in ROWS.values():
        if len(T.rid) == 3:
            continue
        known = [v for v in T.vals if v is not None]
        for i, v in enumerate(T.vals):
            key = (T.g.name, T.r, T.g.pcols[i])
            if v is None and key not in F and T.state[i] in ('blank', 'err', 'broken'):
                ov[key] = (sum(known) / len(known) if known else 1.0) * rng.uniform(0.6, 1.4)
    return ov


# ---------------------------------------------------------------- evidence matching
def match_row(label, rows):
    best = [T for T in rows if lkey(T.label) == lkey(label)]  # exact after normalising first
    if not best:  # else all words of one inside the other ('list price' / 'List price per unit'), never a near miss
        stop = {'per', 'the', 'of', 'a', 'an', 'and', 'in', 'for', 'vs', 'to', 'by', 'on'}
        ws = lambda x: set(lkey(x).split()) - stop
        best = [T for T in rows if ws(label) and ws(T.label) and (ws(label) <= ws(T.label) or ws(T.label) <= ws(label))]
    return best[0] if len(best) == 1 else None


def match_period(period, g):
    pk = pkey(period)
    if not pk:
        return None
    hit = lambda lab: bool(pkey(lab)) and (pk <= pkey(lab) or pkey(lab) <= pk)
    hits = [('p', i) for i, lab in enumerate(g.plabels) if hit(lab)] + [('t', c) for c in g.tcols if hit(g.tlabels[c])]
    return hits[0] if len(hits) == 1 else None


def ev_index(items, rows):
    out = {}
    for it in items:
        T = match_row(it.get('label', ''), rows)
        p = match_period(it.get('period', ''), T.g) if T else None
        if T and p and isinstance(it.get('value'), (int, float)):
            key = (T.g.name, T.r, T.g.pcols[p[1]] if p[0] == 'p' else p[1])
            out[key] = it
    return out


def ev_tol(v):
    s = repr(float(v))
    d = len(s.split('.')[1]) if '.' in s and 'e' not in s else 0
    if s.endswith('.0'):
        d = 0
    return max(0.005, 0.5 * 10 ** -d) + 1e-9 * abs(v)


def money_like(label):
    return '%' not in label and bool(re.search(
        r'revenue|sales|price|cost|cogs|amount|order|income|spend|opex|expense|salar|rent|margin|profit|mrr|arr|cash|'
        r'discount|fee|commission|bonus|\$', label.lower()))


def fmtv(v, money):
    if not isinstance(v, float):
        return str(v)
    if money:
        return ('-$' if v < 0 else '$') + '{:,.2f}'.format(abs(v))
    return '{:,.0f}'.format(v) if v.is_integer() else '{:,.4g}'.format(v) if abs(v) < 1 else '{:,.2f}'.format(v)


def where_to_look(label, period):
    l = label.lower()
    if re.search(r'unit|volume|order|customer|user|subscri|seat|sold|churn|signup', l):
        first = ['sales, order or CRM export with %s for %s' % (label, period), 'billing or invoicing system records for %s' % period]
    elif re.search(r'salar|payroll|headcount|wage|staff', l):
        first = ['payroll export for %s' % period, 'general ledger (salaries account) for %s' % period]
    elif re.search(r'price|rate|arpu|fee', l):
        first = ['price list or rate card in force in %s' % period, 'invoices issued in %s' % period]
    else:
        first = ['general ledger or accounting export for %s' % period, 'vendor invoices and bank statement for %s' % period]
    return first + ['board report or investor update that quotes %s for %s' % (label, period),
                    'an older copy of the model (email attachments, shared drive version history)',
                    'the person who maintains the model']


# ---------------------------------------------------------------- writing model.xlsx
def cell_xml(ref, style, f, v):
    attrs = ' r="%s"' % ref + (' s="%s"' % style if style else '')
    t, vs = '', None
    if isinstance(v, Err):
        t, vs = ' t="e"', str(v)
    elif isinstance(v, bool):
        t, vs = ' t="b"', '1' if v else '0'
    elif isinstance(v, str):
        t, vs = ' t="str"', v
    elif isinstance(v, float) and v == v and abs(v) != float('inf'):
        vs = repr(v)
    if f is None and vs is None:
        return '<c%s/>' % attrs
    body = ('<f>%s</f>' % escape(f) if f is not None else '') + ('<v>%s</v>' % escape(vs) if vs is not None else '')
    return '<c%s%s>%s</c>' % (attrs, t if f is not None or not isinstance(v, str) else ' t="inlineStr"', body)


def patch_sheet(xml, cells):
    for (r, c), (f, v) in sorted(cells.items()):
        ref = a1(r, c)
        m = re.search(r'<c\b[^>]*?\br="%s"[^>]*?(?:/>|>.*?</c>)' % ref, xml, re.S)
        if m:
            sm = re.search(r'\bs="(\d+)"', m.group(0).split('>', 1)[0])
            xml = xml[:m.start()] + cell_xml(ref, sm.group(1) if sm else None, f, v) + xml[m.end():]
            continue
        m = re.search(r'<row\b[^>]*?\br="%d"[^>]*?(?:/>|>.*?</row>)' % r, xml, re.S)
        if m:
            row = m.group(0)
            head = re.sub(r'\sspans="[^"]*"', '', row.split('>', 1)[0].rstrip('/')) + '>'
            body = '' if row.endswith('/>') else row.split('>', 1)[1][:-len('</row>')]
            cs = list(re.finditer(r'<c\b[^>]*?\br="([A-Z]+)\d+"[^>]*?(?:/>|>.*?</c>)', body, re.S))
            left = [x for x in cs if col2n(x.group(1)) < c]
            sm = re.search(r'\bs="(\d+)"', left[-1].group(0).split('>', 1)[0]) if left else None
            pos = next((x.start() for x in cs if col2n(x.group(1)) > c), len(body))
            body = body[:pos] + cell_xml(ref, sm.group(1) if sm else None, f, v) + body[pos:]
            xml = xml[:m.start()] + head + body + '</row>' + xml[m.end():]
            continue
        new = '<row r="%d">%s</row>' % (r, cell_xml(ref, None, f, v))
        later = [x for x in re.finditer(r'<row\b[^>]*?\br="(\d+)"', xml) if int(x.group(1)) > r]
        if later:
            xml = xml[:later[0].start()] + new + xml[later[0].start():]
        elif '<sheetData/>' in xml:
            xml = xml.replace('<sheetData/>', '<sheetData>%s</sheetData>' % new, 1)
        else:
            xml = xml.replace('</sheetData>', new + '</sheetData>', 1)
    return xml


def write_model(src, dst, book, cells):
    bypath = {book.spath[s]: s for s in book.sheets}
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(dst, 'w', zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            name, data = item.filename, zin.read(item.filename)
            if name == 'xl/calcChain.xml':
                continue
            if name == '[Content_Types].xml':
                data = re.sub(rb'<Override[^>]*?/xl/calcChain\.xml"[^>]*?/>', b'', data)
            elif name == 'xl/_rels/workbook.xml.rels':
                data = re.sub(rb'<Relationship[^>]*?calcChain\.xml"[^>]*?/>', b'', data)
            elif name == 'xl/workbook.xml':
                s = data.decode('utf-8')
                m = re.search(r'<(\w+:)?calcPr\b[^>]*?/?>', s)
                if m:
                    tag = re.sub(r'\sfullCalcOnLoad="[^"]*"', '', m.group(0))
                    tag = re.sub(r'^<((?:\w+:)?calcPr)', r'<\1 fullCalcOnLoad="1"', tag)
                    s = s[:m.start()] + tag + s[m.end():]
                else:
                    m = re.search(r'</(\w+:)?definedNames>', s) or re.search(r'</(\w+:)?sheets>', s)
                    s = s[:m.end()] + '<%scalcPr fullCalcOnLoad="1"/>' % (m.group(1) or '') + s[m.end():]
                data = s.encode('utf-8')
            elif name in bypath and cells.get(bypath[name]):
                data = patch_sheet(data.decode('utf-8'), cells[bypath[name]]).encode('utf-8')
            zout.writestr(item, data)


# ---------------------------------------------------------------- records
def ranges(keys):
    """Compress cell keys into 'Sheet!C5:J5' strings (runs along a row, or down a column)."""
    keys = set(keys)
    vert = len({(k[0], k[2]) for k in keys}) == 1
    out, keys = [], sorted(keys, key=lambda k: (k[0], k[2], k[1]) if vert else (k[0], k[1], k[2]))
    nxt = (lambda a, b: a[2] == b[2] and b[1] == a[1] + 1) if vert else (lambda a, b: a[1] == b[1] and b[2] == a[2] + 1)
    i = 0
    while i < len(keys):
        j = i
        while j + 1 < len(keys) and keys[j + 1][0] == keys[i][0] and nxt(keys[j], keys[j + 1]):
            j += 1
        out.append(cref(keys[i]) + ('' if i == j else ':' + a1(keys[j][1], keys[j][2])))
        i = j + 1
    return out


def item_name(keys, T=None, extra=''):
    g = T.g if T else None
    if g and len(keys) == 1:
        k = keys[0]
        per = g.plabels[g.pcols.index(k[2])] if k[2] in g.pcols else g.tlabels.get(k[2], '')
        return '%s (%s, %s)' % (cref(k), T.label, per)
    names = [g.plabels[g.pcols.index(k[2])] if k[2] in g.pcols else g.tlabels.get(k[2], '') for k in keys] if g else []
    span = '%s-%s' % (names[0], names[-1]) if len(names) > 1 else (names[0] if names else '')
    return '%s (%s%s)' % (', '.join(ranges(keys)), (T.label + ', ' if T else '') + span, extra)


def scalar_label(book, key):
    sh, r, c = key
    for cc in range(c - 1, 0, -1):
        v = book.cells.get((sh, r, cc))
        if isinstance(v, str) and v.strip():
            return v.strip()
    for rr in range(r - 1, max(0, r - 3), -1):
        v = book.cells.get((sh, rr, c))
        if isinstance(v, str) and v.strip():
            return v.strip()
    return cref(key)


def surv_choice(T, book):
    g, exprs = T.g, {}
    for i in range(len(g.pcols)):
        j = i if i in T.surv else min(T.surv, key=lambda j: abs(j - i))
        try:
            exprs[i] = T.surv[i] if i == j else shift(T.surv[j], 0, g.pcols[i] - g.pcols[j])
        except ValueError:
            return None
    base = lambda sh, r, c: book.cells.get((sh, r, c))
    for i, st in enumerate(T.state):
        if st == 'num':
            try:
                v = ev(parse(exprs[i], g.name), base)
            except ValueError:
                return None
            if not isinstance(v, float) or abs(v - T.vals[i]) > max(tol(T.vals[i]), 1e-6):
                return None
    return ('F', exprs)


def back_solve(key, T, F, base, book):
    deps = []
    for k2, f in F.items():
        y = book.cells.get(k2)
        if isinstance(y, float) and k2 not in book.formula:
            try:
                if key in refs_of(parse(f, k2[0]), set()):
                    deps.append((k2, y))
            except ValueError:
                pass
    if not deps:
        return None
    f_at = lambda x, k2: num(make_getter(F, base, {key: x})(*k2))
    known = [v for v in T.vals if v is not None]
    x0 = sum(known) / len(known) if known else 1.0
    sol = None
    for k2, y in deps:
        a, b = x0, x0 * 1.1 + 1.0
        fa, fb = f_at(a, k2), f_at(b, k2)
        for _ in range(60):
            if not (isinstance(fa, float) and isinstance(fb, float)) or fa == fb:
                break
            a, b, fa = b, b - (fb - y) * (b - a) / (fb - fa), fb
            fb = f_at(b, k2)
            if isinstance(fb, float) and abs(fb - y) <= tol(y):
                slope = f_at(b + 1.0, k2)
                if isinstance(slope, float) and abs(slope - fb) > 1e-12:
                    sol = b
                break
        if sol is not None:
            break
    if sol is None:
        return None
    for x in [round(sol, d) for d in (0, 2, 4, 6)] + [sol]:
        if all(isinstance(f_at(x, k2), float) and abs(f_at(x, k2) - y) <= tol(y) for k2, y in deps):
            return x, [k2 for k2, _ in deps]
    return None


def differs_text(T, d, lab_money):
    if not d:
        return 'never: agrees with the chosen formula on every surviving value and every probe; the simpler reading is kept'
    if d['kind'] == 'label':
        return d['note']
    if d['kind'] == 'client':
        return 'rejected by the client answer'
    o = [fmtv(v, lab_money) for v in d['outputs']]
    if d['kind'] == 'threshold':
        X = ROWS[d['x']]
        return 'when %s is exactly %s: gives %s instead of %s' % (X.label, fmtv(d['value'], money_like(X.label)), o[1], o[0])
    return 'when inputs change (probe %d, %s): gives %s instead of %s' % (
        d['probe'], T.g.plabels[d['col']], o[1], o[0])


def rule_bit(rules_ev, tv):
    """A short quote from the evidence rule around the threshold, e.g. 'Orders over $50,000'."""
    for r in rules_ev:
        txt = str(r.get('text', '')).strip().rstrip('.')
        if '|' in txt or '=' in txt:
            continue
        for m in re.finditer(r'\$?(\d[\d,]*(?:\.\d+)?)', txt):
            try:
                hit = abs(float(m.group(1).replace(',', '')) - tv) <= max(tol(tv), 0.011)
            except ValueError:
                hit = False
            if hit:
                a = len(' '.join(txt[:m.start()].split()[-3:]))
                bit = (txt[:m.start()].rstrip()[-a:] + ' ' if a else '') + txt[m.start():m.end()] + \
                    ' '.join([''] + txt[m.end():].split()[:3])
                return ' (your note says "%s")' % bit.strip()[:60]
    return ''


def short(e, pw):
    return re.sub(r' \([^()]*![A-Z]+\d+\)', '', desc(e, pw))


def leaf_name(n, pw):
    if n[0] == 'R':
        lab = ROWS[n[1]].label + (' on %s' % n[1][0] if len(n[1]) == 3 else '')
        return lab if not n[2] else "the previous %s's %s" % (pw, lab)
    if n[0] == 'S':
        return SL.get(n[1], 'an assumption')
    if n[0] == 'SUM':
        return 'the lines %s to %s' % (ROWS[n[2][0]].label, ROWS[n[2][-1]].label)
    return fmtnum(n[1])


def make_question(T, d, rules_ev, opts):
    """One plain sentence a CFO can answer: what differs between the readings, in business words, never a formula."""
    lab, pw, lm = T.label, T.g.pw, money_like(T.label)
    outs = d['outputs'] if d else []
    if any(n[0] == 'IF' for e in opts for n in nodes(e)):
        d = threshold_probe(T, opts[0], opts[1]) or d
    cut = lambda t: t if len(t) <= 200 else t[:196].rsplit(' ', 1)[0] + '...?'
    if d and d['kind'] == 'threshold':
        X = ROWS[d['x']]
        xm = money_like(X.label)
        g2 = lambda rid, c: d['value'] if (rid == d['x'] and c == d['col']) else gv(rid, c)
        outs = [vev(e, d['col'], g2) for e in opts]
        ifs = [n for e in opts for n in nodes(e) if n[0] == 'IF']
        tv = vev(ifs[0][3], 0, gv) if ifs else d['value']
        tvs = fmtv(tv, xm)
        probe = {'input': {X.label: d['value'], 'period': T.g.plabels[d['col']]}, 'outputs': outs}
        plain = [e for e in opts if not any(n[0] == 'IF' for n in nodes(e))]
        heads = []
        for e in opts:
            op = next((n[1] for n in nodes(e) if n[0] == 'IF'), None)
            heads.append(op)
        if plain:  # the data never cross the threshold
            above = plain[0] == ('K', 0.0)
            text = ('%s never reaches %s in your file, so should %s above %s get the %s%s?' if above else
                    '%s is above %s in every %s you sent, so should %s at or below %s still get the %s%s?') % (
                (X.label, tvs, X.label.lower(), tvs, lab.lower(), rule_bit(rules_ev, tv)) if above else
                (X.label, tvs, pw, X.label.lower(), tvs, lab.lower(), rule_bit(rules_ev, tv)))
            options = [('No, keep it as it is' if above else 'Yes, always') if op is None else
                       ('Only above %s (>)' % tvs if op == '>' else 'From exactly %s up (>=)' % tvs) for op in heads]
            return cut(text), options, probe
        hi = next((o for e, o in zip(opts, outs) if any(n[0] == 'IF' and n[1] == '>=' for n in nodes(e))), None)
        ratey = re.search(r'rate|%|percent', lab.lower()) or (isinstance(hi, float) and abs(hi) < 1)
        what = 'the %s %s' % (fmtnum(round(hi * 100, 4)) + '%', lab.lower()) if ratey and isinstance(hi, float) and hi else \
            'the %s' % lab.lower()
        text = 'Does a %s with exactly %s %s get %s%s?' % (pw, tvs, X.label.lower(), what, rule_bit(rules_ev, tv))
        options = ['Yes, exactly %s qualifies (>=)' % tvs if op == '>=' else 'No, only above %s (>)' % tvs
                   if op == '>' else 'Neither: another rule' for op in heads]
        return cut(text), options, probe
    probe = {'input': {'scenario': 'every input scaled by a random factor between 0.6 and 1.4 (probe %d)' % (d or {}).get('probe', 0),
                       'cell': cref((T.g.name, T.r, T.g.pcols[(d or {}).get('col', 0)]))}, 'outputs': outs}
    if unround(opts[0]) == unround(opts[1]):
        return cut('Should %s be rounded to the cent each %s?' % (lab.lower(), pw)), [
            'Yes, round to the cent' if e[0] == 'RND' else 'No, keep full precision' for e in opts], probe
    names = lambda e: {leaf_name(n, pw) for n in leaves(unround(e))}
    uniq = [sorted(names(e) - names(opts[1 if i == 0 else 0])) for i, e in enumerate(opts)]
    if all(uniq[:2]):
        text = 'Is %s based on %s, or on %s?' % (lab.lower(), ' and '.join(uniq[0]), ' and '.join(uniq[1]))
        return cut(text), ['Based on %s' % (' and '.join(u) or 'something else') for u in uniq], probe
    text = 'Two readings of %s fit every %s you sent but differ when the inputs change: which one should the model use?' % (
        lab.lower(), pw)
    return cut(text), [short(e, pw) for e in opts], probe


def run(a):
    evd = {}
    if a.evidence:
        with open(a.evidence) as fh:
            evd = json.load(fh) or {}
    case = a.case or evd.get('case_id') or 'C-0001'
    cnum = case.split('-', 1)[1] if case.upper().startswith('C-') else case
    answers = {}
    for item in [x for grp in (a.answer or []) for x in grp]:
        k, _, v = item.partition('=')
        answers[k.strip()] = int(v)
    book = Book(a.workbook)
    grids = [g for g in (layout(book, s) for s in book.sheets) if g]
    for g in grids:
        for r in g.rows:
            T = Row(g, r, book.cells[(g.name, r, g.lab)].strip())
            for i, c in enumerate(g.pcols):
                v, f = book.cells.get((g.name, r, c)), book.formula.get((g.name, r, c))
                if f is not None and '#REF!' in f.upper():
                    st, v = 'broken', None
                elif f is not None:
                    st, v = 'form', v if isinstance(v, float) else None
                    T.surv[i] = f
                elif isinstance(v, float):
                    st = 'num'
                elif isinstance(v, Err):
                    st, v = 'err', None
                else:
                    st, v = ('blank', None) if v is None else ('err' if garbled(v) else 'text', None)
                T.vals.append(v)
                T.state.append(st)
            ROWS[T.rid] = T
    rows = [ROWS[(g.name, r)] for g in grids for r in g.rows]
    inside = set()
    for g in grids:
        inside |= {(g.name, g.hr, c) for c in [g.lab] + g.pcols + g.tcols}
        inside |= {(g.name, r, c) for r in g.rows for c in g.pcols + g.tcols + list(range(1, g.lab))}
    order = {s: i for i, s in enumerate(book.sheets)}
    for key in sorted(book.cells, key=lambda k: (order[k[0]], k[1], k[2])):
        v = book.cells[key]
        if isinstance(v, float) and key not in inside and v != 0:
            SV[key], SL[key] = v, scalar_label(book, key)
    rules_ev = [x for x in evd.get('rules') or [] if isinstance(x, dict)]
    ZG[0] = any(r.get('zero_denominator') is not None for r in rules_ev) or any(re.search(r'zero denominator|denominator is (zero|0)|denominator of (zero|0)|divid\w* by (zero|0)|'
                          r'zero denominator|show 0%|show zero', t, re.I) for t in all_text(evd))
    scal_rec = {}
    for key in sorted(book.cells, key=lambda k: (order[k[0]], k[1], k[2])):  # damaged assumption cells
        v = book.cells[key]
        if key not in inside and (isinstance(v, Err) or garbled(v)) and key[2] > 1:
            lab = scalar_label(book, key)
            if lab != cref(key) and re.search(r'[A-Za-z]{3}', lab) and not re.search(r'[?#\ufffd]', lab):
                UNK[key], SL[key] = lab, lab
                for rule in rules_ev:  # stated outright in the evidence: 'Tier 1 rate = 0.05'
                    m = re.match(r'\s*(.+?)\s*(?:=|:)\s*\$?(-?[\d,]*\.?\d+)\s*(%?)\s*\.?\s*$', str(rule.get('text', '')))
                    if m and lkey(m.group(1)) == lkey(lab):
                        SV[key] = float(m.group(2).replace(',', '')) / (100.0 if m.group(3) else 1.0)
                        scal_rec[key] = ('rule', rule.get('fragment_id') or rule.get('source'))
                        break
    lits = []
    cmp_words = re.compile(r'over|above|below|under|at least|or more|more than|less than|fewer than|threshold|minimum|'
                           r'exceed|up to|from|between|tier|band|bracket', re.I)
    for rule in rules_ev:
        txt = str(rule.get('text', ''))
        if '|' in txt or len(rule.get('numbers') or []) > 4:
            continue  # a table of reported figures, not a rule
        if cmp_words.search(txt) or rule.get('operator_hint'):
            THRK.update(float(x) for x in rule.get('numbers') or [] if isinstance(x, (int, float)) and abs(x) >= 1)
        for x in rule.get('numbers') or []:
            if isinstance(x, (int, float)) and x and float(x) not in lits and not any(
                    abs(v - x) <= tol(x) for v in SV.values()) and not (float(x).is_integer() and abs(x) <= 12):
                lits.append(float(x))
    scs = [('S', k) for k in SV] + [('K', x) for x in lits]

    def commit(T):
        hit = SOLVED.get((T.rid, T.choice))
        if hit and hit[0] not in SV:
            SV[hit[0]] = hit[1]
            scal_rec[hit[0]] = ('solved', T.rid)
            scs.append(('S', hit[0]))
    consts = [x for x in (12.0, 4.0, 100.0, 1000.0) if x not in lits and x not in SV.values()]

    # 1. infer each row's formula from the surviving values
    for g in grids:
        usable = [(g.name, r) for r in g.rows if sum(1 for v in ROWS[(g.name, r)].vals if v is not None) >= 2
                  and any(v for v in ROWS[(g.name, r)].vals if v is not None)]
        for r in g.rows:
            T = ROWS[(g.name, r)]
            known = [v for v in T.vals if v is not None]
            if T.surv:
                e = surv_choice(T, book)
                if e is not None:
                    T.choice, T.cands = e, [e]
                    continue
            ops = [x for x in usable if x[1] < r]
            if len(known) >= 2 and any(known):
                T.cands = infer_row(T, ops, usable, scs, consts)
                if T.cands:
                    T.choice = T.cands[0]
                    commit(T)
                    if uses_lag(T.choice):
                        T.seed = find_seed(T, ops, scs)
            extra = one_sided(T, ops, scs) if len(known) >= 2 else []
            if extra:
                T.choice = T.choice or ('K', 0.0)
                T.cands = [T.choice] + [e for e in T.cands[1:] if e[0] != 'IF'][:3] + extra

    prox = make_proxies(grids)
    use = lambda rid: sum(1 for v in ROWS[rid].vals if v is not None) >= 2 and any(v for v in ROWS[rid].vals if v is not None)
    summ = re.compile(r'summ|dash|overview|report|output|kpi|board|consol', re.I)
    for g in sorted(grids, key=lambda g: (not summ.search(g.name), -sum(ROWS[(g.name, r)].choice is None for r in g.rows))):
        for r in g.rows:  # 1b. rows still unexplained: pulls from other sheets (no cycles)
            T = ROWS[(g.name, r)]
            if T.choice is not None or T.surv or not use(T.rid):
                continue
            below = [(g.name, rr) for rr in g.rows if rr > r and use((g.name, rr)) and T.rid not in reach((g.name, rr))]
            px = [x for x in prox.get(g.name, []) if use(x) and T.rid not in reach(ROWS[x].src)] + below
            ops = [(g.name, rr) for rr in g.rows if rr < r and use((g.name, rr))]
            T.cands = infer_row(T, ops, ops, scs, consts, gen=lambda: tierx(T, ops, px, scs)) if px else []
            if T.cands:
                T.choice = T.cands[0]
                if uses_lag(T.choice):
                    T.seed = find_seed(T, ops, scs)
    for T in rows:  # 1c. a pasted rate row feeding a formula, when the rate is really derived from that formula's row
        if T.choice is None or T.choice[0] == 'F':
            continue
        for n in leaves(T.choice):
            if n[0] != 'R' or n[2] or len(n[1]) != 2 or n[1][1] > T.r or ROWS[n[1]].choice is not None:
                continue
            Rw, g = ROWS[n[1]], T.g
            ops_t = [(g.name, rr) for rr in g.rows if rr < T.r and use((g.name, rr)) and Rw.rid not in reach((g.name, rr))]
            alt = infer_row(T, ops_t, ops_t, scs, consts)
            if not alt or any(Rw.rid in reach(x[1][:2]) for x in leaves(alt[0]) if x[0] == 'R'):
                continue
            ops_r = [(g.name, rr) for rr in g.rows if rr < Rw.r and use((g.name, rr))]
            rc = infer_row(Rw, ops_r, ops_r, scs, consts, gen=lambda: tierx(Rw, ops_r, [T.rid], scs))
            if rc:
                T.cands, T.choice = alt, alt[0]
                commit(T)
                Rw.cands, Rw.choice = rc, rc[0]
                break
    for T in rows:  # a number typed from the evidence that belongs in a damaged assumption cell: reference the cell
        if T.choice is None or T.choice[0] == 'F':
            continue
        for kn in [n for n in leaves(T.choice) if n[0] == 'K' and n[1] not in (0.0, 1.0, 2.0)]:
            for u in [u for u in UNK if u not in SV and words(UNK[u]) & (words(T.label) | {
                    w for n in leaves(T.choice) if n[0] == 'S' for w in words(SL.get(n[1], ''))})]:
                e2 = subst(T.choice, kn, ('S', u))
                SV[u] = kn[1]
                if checker(T, True)(e2) is not None:
                    T.choice, T.cands = e2, [e2] + [subst(x, kn, ('S', u)) for x in T.cands[1:]]
                    scal_rec[u] = ('rule', next((r.get('fragment_id') for r in rules_ev if kn[1] in [
                        float(x) for x in r.get('numbers') or [] if isinstance(x, (int, float))]), None))
                    scs.append(('S', u))
                    break
                del SV[u]
    rround = [r for r in rules_ev if re.search(r'\bround', str(r.get('text', '')), re.I) and
              re.search(r'\bcents?\b|penny|2 decimal|two decimal', str(r.get('text', '')), re.I)]
    for T in rows:  # the evidence says this line is rounded to the cent: ROUND(...,2), and no unrounded rival
        if T.choice is None or T.choice[0] in ('F', 'RND') or not rround:
            continue
        ws = set(re.findall(r'[a-z]+', T.label.lower())) - {'of', 'the', 'and', 'per', 'total', 'rate'}
        acro = ''.join(w[0] for w in re.findall(r'[A-Za-z]+', T.label)).lower()
        hinted = [r for r in rround if r.get('row_hint') and lkey(r['row_hint']) == lkey(T.label)]
        named = hinted or [r for r in rround if not r.get('row_hint') and any(
            ws & set(re.findall(r'[a-z]+', t.lower())) or len(acro) > 2 and re.search(r'\b%s\b' % acro, t.lower())
            for t in (str(r.get('text', '')), str(r.get('context') or '')))]
        frac = any(n[0] in ('S', 'K') and 0 < abs((SV.get(n[1]) if n[0] == 'S' else n[1]) or 0) < 1 for n in leaves(T.choice))
        known = [v for v in T.vals if v is not None]
        if named and (hinted or frac) and known and max(abs(v) for v in known) >= 1 and \
                all(abs(v * 100 - round(v * 100)) < 1e-6 for v in known):
            e2 = ('RND', T.choice, 2)
            if checker(T, True)(e2) is not None:
                META[(T.rid, e2)] = meta(T, T.choice)
                T.choice, T.round_by = e2, named[0].get('fragment_id') or named[0].get('source')
                T.cands = [e2] + [x for x in T.cands if x != e2 and unround(x) != unround(e2)]
    vals0 = dict(book.cells)
    vals0.update({k: SV[k] for k in UNK if k in SV})

    # 2. probe alternatives that fit equally well: same results everywhere, or a question for the client
    F = build_F(book, rows)
    rng = random.Random(7)
    getters = [make_getter(F, vals0, scenario(vals0, F, rng)) for _ in range(6)]
    for T in rows:
        if len(T.cands) < 2 or T.choice[0] == 'F':
            continue
        for alt in T.cands[1:8]:
            d = pair_diff(T, T.cands[0], alt, getters)
            (T.rivals if d else T.equiv).append((alt, d))
        T.rivals = [(x, d) for x, d in T.rivals if unround(x) != unround(T.choice)]
        lit = lambda e: any(n[0] == 'K' and n[1] not in (0.0, 1.0, 2.0) for n in leaves(e))
        if not lit(T.choice):  # a number typed from the evidence never beats a reference to an assumption cell
            T.equiv += [(x, {'kind': 'label', 'note': 'types a number from the evidence where an assumption cell fits; '
                             'the cell reference is kept'}) for x, _ in T.rivals if lit(x)]
            T.rivals = [(x, d) for x, d in T.rivals if not lit(x)]
        if T.rivals and all(any(n[0] == 'IF' for n in nodes(x)) for x in [T.choice] + [x for x, _ in T.rivals]):
            ops_ = {}
            for x in [T.choice] + [x for x, _ in T.rivals]:  # operators the evidence wording settles
                for n in nodes(x):
                    if n[0] == 'IF' and n[3][0] in ('S', 'K'):
                        tv = vev(n[3], 0, gv)
                        if tv is not None:
                            ops_[tv] = op_from_words(rules_ev, tv)
            keep = [x for x in [T.choice] + [x for x, _ in T.rivals] if all(
                ops_.get(vev(n[3], 0, gv)) in (None, n[1]) for n in nodes(x) if n[0] == 'IF' and n[3][0] in ('S', 'K'))]
            if keep and len(keep) < 1 + len(T.rivals):
                T.choice = keep[0]
                T.worded = True
                T.equiv += [(x, {'kind': 'label', 'note': 'the operator the evidence wording rules out'}) for x, _ in
                            T.rivals if x not in keep]
                T.rivals = [(x, d) for x, d in T.rivals if x in keep and x != T.choice]
        if support(T, T.choice) > 0:  # a coincidental fit whose operands share no words with the row asks nothing
            odd = [(x, d) for x, d in T.rivals if support(T, x) == 0]
            T.rivals = [(x, d) for x, d in T.rivals if support(T, x) > 0]
            T.equiv += [(x, {'kind': 'label', 'note': 'fits the surviving values by coincidence of constants but its '
                             'inputs have nothing to do with this row; set aside'}) for x, _ in odd]
        if T.rivals and all(strip_s(x) == strip_s(T.choice) for x, _ in T.rivals):
            opts = [T.choice] + [x for x, _ in T.rivals]
            sc = [label_score(T, x) for x in opts]
            if sc.count(max(sc)) == 1:
                T.choice = opts[sc.index(max(sc))]
                T.equiv += [(x, {'kind': 'label', 'note': 'uses another assumption cell with the same value; '
                                 'the one whose label matches the row was kept'}) for x in opts if x is not T.choice]
                T.rivals = []
    n_rule = [0]

    def new_rule():
        n_rule[0] += 1
        return 'R-%s-%02d' % (cnum, n_rule[0])
    for T in rows:
        if T.choice is not None and any(has_formula(T, T.choice, i) for i in range(len(T.vals))):
            T.rule = new_rule()
    waiting = []
    for T in rows:
        if not T.rivals:
            continue
        opts = [T.choice] + [x for x, _ in T.rivals][:3]
        hint = None
        for n in [n for e in opts for n in nodes(e) if n[0] == 'IF']:
            tv = vev(n[3], 0, gv)
            for rule in rules_ev:
                if rule.get('operator_hint') in ('>', '>=') and any(
                        isinstance(x, (int, float)) and abs(x - tv) <= tol(tv) for x in rule.get('numbers') or []):
                    hint = rule['operator_hint']
        if hint:
            opts.sort(key=lambda e: 0 if any(n[0] == 'IF' and n[1] == hint for n in nodes(e)) else 1)
        T.options = opts
        if T.rule in answers and 0 <= answers[T.rule] < len(opts):
            T.choice, T.answered = opts[answers[T.rule]], True
        else:
            T.choice, T.waiting = opts[0], True
            waiting.append(T)
        T.rivals = [(x, {'kind': 'rival'}) for x in opts if x != T.choice]

    # 3. final formulas, lost inputs (exact evidence, then solving from surviving results), totals columns
    F = build_F(book, rows)
    label, cites, gaps, filled, from_ev = {}, {}, [], {}, set()

    def gap(what, why, where):
        gid = 'G-%s-%02d' % (cnum, len(gaps) + 51)
        gaps.append({'gap_id': gid, 'what': what, 'why': why, 'where_to_look': where, 'status': 'open'})
        return gid
    ev_vals = ev_index(evd.get('values') or [], rows)
    ev_rep = ev_index(evd.get('reported') or [], rows)
    lost = []
    for T in rows:
        known = [v for v in T.vals if v is not None]
        for i, st in enumerate(T.state):
            key = (T.g.name, T.r, T.g.pcols[i])
            if key in F and st != 'form':
                continue
            if st in ('num', 'form'):
                label[key], cites[key] = REC, [cref(key)]
                if T.choice is not None and i in meta(T, T.choice)[1]:
                    cites[key].append(gap('%s for %s (%s) differs from the row\'s rule %s; kept as typed' % (
                        T.label, T.g.plabels[i], cref(key), T.rule), 'a typed override or a one-off adjustment: confirm '
                        'with the client', ['the client or the person who maintains the model', 'notes or comments next '
                                            'to the cell in older copies']))
            elif st in ('err', 'broken'):
                lost.append((T, i, key))
            elif st == 'blank':
                lagged = T.choice is not None and T.choice[0] != 'F' and i == 0 and uses_lag(T.choice)
                if (('R', T.rid, 1) in leaves(T.choice)) if lagged else covered(T, i) and (
                        T.choice is None or not has_formula(T, T.choice, i)):
                    lost.append((T, i, key))
    km = {}
    for it in evd.get('known_missing') or []:
        T = match_row(it.get('label', ''), rows)
        p = match_period(it.get('period', ''), T.g) if T else None
        if T and p and p[0] == 'p':
            km[(T.g.name, T.r, T.g.pcols[p[1]])] = it
    for T, i, key in lost:
        it = ev_vals.get(key)
        if key in km:
            continue
        if it:
            filled[key] = float(it['value'])
            from_ev.add(key)
            label[key], cites[key] = REC, [x for x in (it.get('fragment_id'), it.get('source')) if x]
    for u in [u for u in UNK if u in SV]:  # damaged assumption cells: stated in evidence, or solved from the data
        filled[u] = SV[u]
        how = scal_rec.get(u, ('solved', None))
        frag = how[1] if how[0] == 'rule' else next((r.get('fragment_id') for r in rules_ev if any(
            isinstance(x, (int, float)) and abs(x - SV[u]) <= tol(SV[u]) for x in r.get('numbers') or [])), None)
        label[u], cites[u] = (REC, [frag]) if frag else (TESTED, ['solved from the surviving values of %s' % (
            ROWS[how[1]].label if how[1] in ROWS else 'the model')])
    for u in [u for u in UNK if u not in SV]:
        label[u], cites[u] = UNRES, [gap('%s (%s): the assumption cell is damaged and nothing in the file or the evidence '
                                         'fixes its value' % (UNK[u], cref(u)), 'formulas that use it cannot be rebuilt',
                                         ['the assumptions or rate card the model was built from', 'the CFO or the person who maintains the model'])]
    base = dict(book.cells)
    base.update(filled)
    for _ in range(8):  # restored inputs reveal rows rounded to the cent: ROUND(...,2) on that row
        get, hit = make_getter(F, base, {}), None
        for k in F:
            y, T = book.cells.get(k), ROWS.get(k[:2])
            if k in book.formula or not isinstance(y, float) or T is None or T.choice is None or \
                    T.choice[0] in ('RND', 'F') or k[2] not in T.g.pcols:
                continue
            v = get(*k)
            if isinstance(v, float) and tol(y) < abs(v - y) <= 0.0051 and abs(y * 100 - round(y * 100)) < 1e-6:
                hit = T
                break
        if hit is None:
            break
        e2 = ('RND', hit.choice, 2)
        META[(hit.rid, e2)] = meta(hit, hit.choice)
        hit.choice = e2
        for i in range(len(hit.vals)):
            if (hit.g.name, hit.r, hit.g.pcols[i]) in F and has_formula(hit, e2, i):
                F[(hit.g.name, hit.r, hit.g.pcols[i])] = cell_formula(e2, i, hit.g, hit.r)
    for T, i, key in lost:
        if key in filled:
            continue
        if key in km:  # the client says this figure does not exist: blank, unresolved, cited
            it = km[key]
            label[key], cites[key] = UNRES, [x for x in (it.get('fragment_id'), gap(
                '%s for %s (%s): %s' % (T.label, T.g.plabels[i], cref(key), it.get('text') or 'the client says this figure does not exist'),
                'it is a raw input the client cannot supply, so it stays blank', ['the client, once the figure exists',
                                                                                  it.get('source') or 'the client email'])) if x]
            continue
        res = back_solve(key, T, F, base, book)
        if res:
            filled[key] = base[key] = res[0]
            nice = abs(res[0] * 100 - round(res[0] * 100)) < 1e-9
            label[key], cites[key] = TESTED if nice else UNTESTED, ['value solved from surviving ' + ', '.join(cref(k) for k in res[1])]
            continue
        per = T.g.plabels[i]
        deps = [ROWS[k[:2]].label for k in F if k[0] == key[0] and k[1] != key[1] and k[2] == key[2] and
                key in refs_of(parse(F[k], k[0]), set()) and k[:2] in ROWS]
        label[key], cites[key] = UNRES, [gap('%s for %s (%s): the input value was lost (%s) and no evidence gives it' % (
            T.label, per, cref(key), 'cell blank' if T.state[i] == 'blank' else 'cell shows #REF!'),
            'it is a raw input, so no formula can rebuild it' + (
                '; it feeds %s for %s' % (', '.join(sorted(set(deps))), per) if deps else ''),
            where_to_look(T.label, per))]
    tot_groups = {}
    for g in grids:
        get = make_getter(F, base, {})
        P = len(g.pcols)
        for tc in g.tcols:
            votes, todo = {}, []
            for r in g.rows:
                T, key = ROWS[(g.name, r)], (g.name, r, tc)
                y, f = book.cells.get(key), book.formula.get(key)
                if f is not None and '#REF!' not in f.upper():
                    label[key], cites[key] = REC, [cref(key)]
                    continue
                surv = isinstance(y, float) and f is None
                if not (surv or isinstance(y, Err) or f is not None or key in ev_rep):
                    continue
                vs = [(lambda v: v if isinstance(v, float) else None)(get(g.name, r, c)) for c in g.pcols]
                todo.append((T, key, y if surv else None, vs))
                for i in range(P):
                    acc = 0.0
                    for j in range(i, P):
                        if not surv or vs[j] is None:
                            break
                        acc += vs[j]
                        if j > i and abs(acc - y) <= tol(y):
                            votes[('HSUM', i, j)] = votes.get(('HSUM', i, j), 0) + 1
                    if surv and vs[i] is not None and abs(vs[i] - y) <= tol(y) and len(set(vs)) > 1:
                        votes[('PREF', i)] = votes.get(('PREF', i), 0) + 1
            spans = sorted(votes, key=lambda k: (-votes[k], k[0] != 'HSUM', -(k[-1] - k[1])))
            span = next((k[1:] for k in spans if k[0] == 'HSUM'), (0, P - 1))
            dense = 2 * len(todo) >= len(g.rows)
            have = {T.rid for T, key, y, vs in todo}
            for r in g.rows:  # blank totals cells in a column that clearly covers every row: the column's own pattern
                T, key = ROWS[(g.name, r)], (g.name, r, tc)
                if dense and T.rid not in have and key not in book.cells and key not in book.formula and (
                        T.choice is None or not uses_lag(T.choice) and T.choice[0] != 'F') and not re.search(
                        r'price|rate|%|percent|ratio|margin|growth|per |average|avg|index|headcount', T.label.lower()):
                    todo.append((T, key, None, None))
            ratio_rows = []
            for T, key, y, vs in todo:
                is_ratio = T.choice is not None and (T.choice[0] == '/' or T.choice[0] == 'RND' and T.choice[1][0] == '/') \
                    or (y is not None and T.choice is not None and T.choice[0] != 'F' and not uses_lag(T.choice) and
                        any(n[0] == 'IF' for n in nodes(T.choice)) and abs(y) < 1)
                if is_ratio:
                    ratio_rows.append((T, key, y))
                    continue
                if T.choice is not None and uses_lag(T.choice) and ('R', T.rid, 1) not in leaves(T.choice) and y is None:
                    continue  # a growth rate has no total
                if y is None:  # a broken or blank totals cell
                    chain = T.choice is not None and ('R', T.rid, 1) in leaves(T.choice)
                    pick = ('PREF', span[1]) if chain else ('HSUM',) + span
                else:
                    pick = None
                    for e in [('HSUM',) + span] + [k for k in spans if k[0] == 'PREF'] + [('PREF', span[0]), ('PREF', span[1])] + \
                            [k for k in spans if k[0] == 'HSUM'] + [('HAVG',) + span]:
                        if e[0] in ('HSUM', 'HAVG'):
                            part = vs[e[1]:e[2] + 1]
                            val = None if None in part else sum(part) / (len(part) if e[0] == 'HAVG' else 1)
                        else:
                            val = vs[e[1]]
                        if val is not None and abs(val - y) <= tol(y):
                            pick = e
                            break
                    if pick is None:
                        ratio_rows.append((T, key, y))
                        continue
                F[key] = ('%s%d' % (n2col(g.pcols[pick[1]]), T.r)) if pick[0] == 'PREF' else ren(pick, 0, g, T.r)
                tot_groups.setdefault((g.name, tc, pick), []).append(key)
            get = make_getter(F, base, {})
            tv = lambda rid: (lambda v: v if isinstance(v, float) else None)(get(rid[0], rid[1], tc))
            colof = lambda c, lag, tc=tc: tc
            for T, key, y in ratio_rows:  # rates recalculated from the totals, e.g. J7/J5
                own = [T.choice[1] if T.choice[0] == '/' else T.choice[1][1]] if T.choice is not None and (
                    T.choice[0] == '/' or T.choice[0] == 'RND' and T.choice[1][0] == '/') else []
                pairs = [(n[1], n[2]) for n in own if n[1][0] == 'R' and n[2][0] == 'R' and not n[1][2] and not n[2][2]]
                pairs += [(('R', A, 0), ('R', B, 0)) for A in [(g.name, rr) for rr in g.rows] for B in [(g.name, rr) for rr in g.rows]
                          if A != B and T.rid not in (A, B) and y is not None]
                pick = None
                for num_, den_ in pairs:
                    a_, b_ = tv(num_[1]), tv(den_[1])
                    if y is None and a_ is not None or a_ is not None and b_ and abs(a_ / b_ - y) <= max(tol(y), 1e-12):
                        pick = ('/', num_, den_)
                        break
                if pick is None:
                    if y is not None:
                        label[key], cites[key] = REC, [cref(key)]
                    continue
                F[key] = cell_formula(pick, 0, g, T.r, colof)
                tot_groups.setdefault((g.name, tc, pick), []).append(key)

    # 4. recalculate the whole rebuilt workbook; roll back anything that does not reproduce what survived
    def precedents(k, depth=4):
        out, todo = set(), [k]
        for _ in range(depth):
            nxt = []
            for x in todo:
                if x in F:
                    for y in refs_of(parse(F[x], x[0]), set()):
                        if y not in out:
                            out.add(y)
                            nxt.append(y)
            todo = nxt
        return out
    for _ in range(6):
        get = make_getter(F, base, {})
        changed = False
        miss = [k for k in F if k not in book.formula and isinstance(book.cells.get(k), float) and
                not close(get(*k), book.cells.get(k), 1e-9)]
        rnd = lambda k: isinstance(get(*k), float) and abs(get(*k) - book.cells[k]) <= 0.0051 and \
            abs(book.cells[k] * 100 - round(book.cells[k] * 100)) < 1e-6
        for k in sorted(miss, key=lambda k: not rnd(k)):  # cent-rounding repairs first, then blame
            y = book.cells.get(k)
            T, v = ROWS.get(k[:2]), get(*k)
            if T is not None and T.choice is not None and T.choice[0] not in ('RND', 'F') and isinstance(v, float) and \
                    abs(v - y) <= 0.0051 and abs(y * 100 - round(y * 100)) < 1e-6 and k[2] in T.g.pcols:
                e2 = ('RND', T.choice, 2)  # the restored inputs show the row is rounded to the cent
                META[(T.rid, e2)] = meta(T, T.choice)
                T.choice = e2
                for i in range(len(T.vals)):
                    if (T.g.name, T.r, T.g.pcols[i]) in F and has_formula(T, e2, i):
                        F[(T.g.name, T.r, T.g.pcols[i])] = cell_formula(e2, i, T.g, T.r)
                changed = True
                break
            culprits = [x for x in precedents(k) if x in from_ev]
            for x in culprits:  # an evidence value that breaks surviving results is undone
                filled.pop(x)
                from_ev.discard(x)
                base[x] = book.cells.get(x)
                T = ROWS[x[:2]]
                label[x], cites[x] = UNRES, [gap('%s %s: the evidence value conflicts with surviving %s, so it was not used' % (
                    T.label, cref(x), cref(k)), 'the export row may belong to a different line or period',
                    where_to_look(T.label, T.g.plabels[T.g.pcols.index(x[2])] if x[2] in T.g.pcols else ''))]
            if not culprits:  # the formula does not hold in this cell: keep the typed value and flag it
                del F[k]
                T = ROWS.get(k[:2])
                label[k], cites[k] = REC, [cref(k), gap('%s (%s) does not follow the rebuilt rule %s; kept as typed' % (
                    T.label if T else '', cref(k), T.rule if T else ''), 'a typed override or a different formula in this '
                    'cell: confirm with the client', ['the client or the person who maintains the model'])]
            changed = True
            break
        if not changed:
            break
    get = make_getter(F, base, {})
    newF = {k: f for k, f in F.items() if k not in book.formula or '#REF!' in book.formula[k].upper()}
    tot_rule = {}
    for (sh, tc, pick), keys in sorted(tot_groups.items(), key=lambda kv: (order[kv[0][0]], kv[0][1], kv[0][2])):
        keys = [k for k in keys if k in newF]
        if keys:
            rid_ = new_rule()
            for k in keys:
                tot_rule[k] = rid_
                cites[k] = [rid_]
    tot_groups = {k: [x for x in v if x in tot_rule] for k, v in tot_groups.items()}
    tot_groups = {k: v for k, v in tot_groups.items() if v}
    bad = []
    for k in newF:
        T = ROWS.get(k[:2])
        y, v = book.cells.get(k), get(*k)
        cites.setdefault(k, [T.rule] if T and T.rule else [])
        wt = T is not None and T.waiting and k[2] in T.g.pcols
        if isinstance(y, float) and k not in book.formula and close(v, y, 1e-9):
            label[k] = UNTESTED if wt else TESTED
        else:
            label[k] = UNTESTED
    for key, it in ev_rep.items():
        v, T = get(*key), ROWS.get(key[:2])
        if isinstance(v, float) and abs(v - float(it['value'])) <= ev_tol(float(it['value'])):
            if key in newF and label.get(key) == UNTESTED and not (T and T.waiting and key[2] in T.g.pcols):
                label[key] = TESTED
            cites.setdefault(key, []).append(it.get('fragment_id') or it.get('source'))
        elif key in label:
            if label[key] == TESTED:
                label[key] = UNTESTED
            cites.setdefault(key, []).append(gap('%s %s: the rebuilt model gives %s but %s reports %s' % (
                T.label if T else '', cref(key), fmtv(v, True), it.get('source', 'evidence'), it['value']),
                'a rebuilt formula or an input disagrees with a reported figure',
                ['the report itself (was it restated?)', 'the inputs feeding %s' % cref(key), 'an older copy of the model']))

    # 5. records
    rules, items = [], []
    used_frag = lambda vals: [r.get('fragment_id') for r in rules_ev if any(
        isinstance(x, (int, float)) and any(abs(x - v) <= tol(v) for v in vals) for x in r.get('numbers') or [])]
    for T in rows:
        keys = [(T.g.name, T.r, c) for c in T.g.pcols]
        mine = [k for k in keys if k in newF] + [k for k in newF if k[:2] == T.rid and k[2] in T.g.tcols and k not in tot_rule]
        if T.rule and mine:
            first = min(mine, key=lambda k: (k[2] not in T.g.pcols, k == keys[0] and T.seed is not None, k[2]))
            consts_used = [SV[n[1]] if n[0] == 'S' else n[1] for n in leaves(T.choice) if n[0] in ('S', 'K')] if T.choice[0] != 'F' else []
            frags = [f for f in used_frag(consts_used) if f] + [cites[k][-1] for k in mine if k in ev_rep and cites.get(k)]
            tested = [k for k in mine if label.get(k) == TESTED]
            status = UNTESTED if T.waiting else TESTED if tested else UNTESTED
            alts = T.rivals + T.equiv
            seed = ' First %s: =%s.' % (T.g.pw, newF[keys[0]]) if T.seed is not None and keys[0] in newF else ''
            rules.append({'rule_id': T.rule, 'description': '%s = %s.%s%s%s' % (
                T.label, desc(T.choice, T.g.pw), seed, ' Chosen by client answer.' if T.answered else '',
                ' Waiting on the client question.' if T.waiting else ''),
                'cells': ranges(mine), 'formula_pattern': '=' + newF[first], 'formula_r1c1': to_r1c1(newF[first], first[1], first[2]),
                'evidence': ranges([k for k in keys if T.state[keys.index(k)] == 'num' and label.get(k) == TESTED]) +
                [cref(n[1]) for n in leaves(T.choice) if n[0] == 'S'] * (T.choice[0] != 'F') + frags +
                (['client answer'] if T.answered else []),
                'alternatives': [{'formula_pattern': '=' + ren(x, first[2] in T.g.pcols and T.g.pcols.index(first[2]) or 1, T.g, T.r),
                                  'differs_when': differs_text(T, pair_diff(T, T.choice, x, getters) if d and d.get('kind') in ('threshold', 'scenario', 'rival') else d, money_like(T.label))}
                                 for x, d in alts if x != T.choice][:5],
                'status': status})
            items.append({'item': item_name(mine, T), 'label': status, 'cites': [T.rule] + frags})
        surv = [k for k in keys if label.get(k) == REC and k not in filled]
        if surv and not (T.rule and mine and len(surv) == len([k for k in keys if T.state[keys.index(k)] == 'form'])):
            if not T.rule or any(T.state[keys.index(k)] == 'form' for k in surv) or T.choice is None or T.seed is None:
                if T.choice is None or all(T.state[keys.index(k)] == 'form' for k in surv):
                    items.append({'item': item_name(surv, T), 'label': REC, 'cites': ranges(surv)})
        for k in keys:
            if k in label and (T.state[keys.index(k)] in ('blank', 'err', 'broken') or
                               any(str(c).startswith('G-') for c in cites.get(k, []))):
                items.append({'item': item_name([k], T), 'label': label[k], 'cites': [c for c in cites.get(k, []) if c]})
    for (sh, tc, pick), keys in sorted(tot_groups.items(), key=lambda kv: tot_rule[kv[1][0]]):
        rid_, g = tot_rule[keys[0]], next(g for g in grids if g.name == sh)
        st = TESTED if any(label.get(k) == TESTED for k in keys) else UNTESTED
        rules.append({'rule_id': rid_, 'description': ('%s column = %s of %s through %s on each row.' % (
            g.tlabels[tc], 'SUM' if pick[0] == 'HSUM' else 'AVERAGE', g.plabels[pick[1]], g.plabels[pick[2]])) if
            pick[0] in ('HSUM', 'HAVG') else '%s column = the %s value on each row (%s).' % (
            g.tlabels[tc], g.plabels[pick[1]], 'opening' if pick[1] == 0 else 'closing') if pick[0] == 'PREF' else
            '%s column = %s, recalculated from the totals.' % (g.tlabels[tc], desc(pick)),
            'cells': ranges(keys), 'formula_pattern': '=' + newF[keys[0]],
            'formula_r1c1': to_r1c1(newF[keys[0]], keys[0][1], keys[0][2]),
            'evidence': ranges([k for k in keys if label.get(k) == TESTED]) + [cites[k][-1] for k in keys if k in ev_rep],
            'alternatives': [], 'status': st})
        items.append({'item': '%s (%s column)' % (', '.join(ranges(keys)), g.tlabels[tc]), 'label': st, 'cites': [rid_]})
        for k in keys:
            if not isinstance(book.cells.get(k), float) or k in ev_rep:
                items.append({'item': item_name([k], ROWS[k[:2]]), 'label': label[k], 'cites': cites[k]})
    for k in bad:
        gaps.append({'gap_id': 'G-%s-%02d' % (cnum, len(gaps) + 51), 'what': 'rebuilt formula in %s does not reproduce its surviving value' % cref(k),
                     'why': 'internal check failed; the cell is labeled unresolved', 'where_to_look': ['rules.json entry for this row'], 'status': 'open'})
    used_s = sorted({n[1] for T in rows if T.choice and T.choice[0] != 'F' for n in leaves(T.choice) if n[0] == 'S'},
                    key=lambda k: (order[k[0]], k[1], k[2]))
    for k in sorted(set(used_s) | set(UNK), key=lambda k: (order[k[0]], k[1], k[2])):
        items.append({'item': '%s (%s)' % (cref(k), SL[k]), 'label': label.get(k, REC), 'cites': [c for c in cites.get(k, [cref(k)]) if c]})
    question = None
    for n, T in enumerate(waiting):
        d = pair_diff(T, T.options[0], T.options[1], getters)
        text, options, probe = make_question(T, d, rules_ev, T.options)
        if n == 0:
            question = {'rule_id': T.rule, 'question': text, 'options': options, 'probe': probe}
        else:
            gaps.append({'gap_id': 'G-%s-%02d' % (cnum, len(gaps) + 51), 'what': 'client choice for %s (%s)' % (T.label, T.rule),
                         'why': text, 'where_to_look': ['ask the client after %s is answered' % question['rule_id']] + options,
                         'status': 'open'})
    counts = {l: 0 for l in LABELS}
    for k, l in label.items():
        counts[l] += 1
    counts[REC] += sum(1 for k in SV if k not in label)
    summary = {'status': 'needs_client' if waiting else 'done', 'counts': counts, 'formulas_rebuilt': len(newF),
               'questions': len(waiting), 'case_id': case}
    cells = {}
    for k, f in newF.items():
        cells.setdefault(k[0], {})[(k[1], k[2])] = (f, get(*k))
    for k, v in filled.items():
        cells.setdefault(k[0], {})[(k[1], k[2])] = (None, v)
    out = a.out_dir
    first, rev = (grids[0].name if grids else ''), {r['rule_id']: r for r in rules}
    manifest = {'case_id': case, 'unresolved': sorted(cref(k) for k, l in label.items() if l == UNRES),
                'rules': {(str(T.r) if T.g.name == first else '%s!%d' % (T.g.name, T.r)): {
                    'rule_id': T.rule, 'evidence': rev[T.rule]['evidence']} for T in rows if T.rule in rev},
                'needs_signoff': [T.r if T.g.name == first else '%s!%d' % (T.g.name, T.r) for T in waiting]}
    with open(os.path.join(out, 'manifest.json'), 'w') as fh:
        json.dump(manifest, fh, indent=2)
    write_model(a.workbook, os.path.join(out, 'model.xlsx'), book, cells)
    for name, obj in (('rules.json', rules), ('report_items.json', items), ('gaps.json', gaps),
                      ('question.json', question), ('summary.json', summary)):
        with open(os.path.join(out, name), 'w') as fh:
            json.dump(obj, fh, indent=2, default=str)
    nt = sum(1 for k in newF if label[k] == TESTED)
    return 'rebuilt %d formulas (%d tested, %d untested); %d unresolved; %s' % (
        len(newF), nt, sum(1 for k in newF if label[k] == UNTESTED), counts[UNRES],
        '%d question%s for the client' % (len(waiting), '' if len(waiting) == 1 else 's') if waiting else 'no questions for the client')


def main(argv=None):
    ap = argparse.ArgumentParser(description='Rebuild lost formulas in a financial model (.xlsx).')
    ap.add_argument('--workbook', required=True)
    ap.add_argument('--evidence')
    ap.add_argument('--case')
    ap.add_argument('--answer', action='append', nargs='+', default=[], help='RULE_ID=OPTION_INDEX')
    ap.add_argument('--out-dir', required=True)
    a = ap.parse_args(argv)
    os.makedirs(a.out_dir, exist_ok=True)
    try:
        line = run(a)
    except Exception as exc:  # report the crash in summary.json so the agent can read it
        with open(os.path.join(a.out_dir, 'summary.json'), 'w') as fh:
            json.dump({'status': 'failed', 'counts': {l: 0 for l in LABELS}, 'formulas_rebuilt': 0, 'questions': 0,
                       'error': '%s: %s' % (type(exc).__name__, exc)}, fh, indent=2)
        print('failed: %s: %s' % (type(exc).__name__, exc))
        return 1
    print(line)
    return 0


if __name__ == '__main__':
    sys.exit(main())
