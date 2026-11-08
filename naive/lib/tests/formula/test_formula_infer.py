#!/usr/bin/env python3
"""Tests for formula_infer.py on the dev fixtures from make_fixtures.py (uses openpyxl + formulas).

  python3 test_formula_infer.py        (or: python3 -m unittest test_formula_infer)

For each damaged fixture: run the tool, then check (1) the rebuilt file opens in openpyxl, (2) recalculating it with
the formulas package reproduces every surviving value, (3) under 5 random input scenarios every computed cell matches
the original model (except cells waiting on the client question), (4) labels and ids follow CONTRACTS.md,
(5) only fixture (a) asks a question, (6) --answer resolves it.
"""
import json, os, random, re, subprocess, sys, tempfile, unittest, zipfile
import openpyxl
import formulas

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.abspath(os.path.join(HERE, '..', '..', 'formula_infer.py'))
sys.path.insert(0, HERE)
import make_fixtures  # noqa: E402

LABELS = {'recovered', 'reconstructed and tested', 'reconstructed but untested', 'unresolved'}
FIX, RUNS = None, {}


def setUpModule():
    global FIX
    FIX = make_fixtures.build(tempfile.mkdtemp(prefix='fi_fixtures_'))


def run_tool(case, *extra):
    key = (case,) + extra
    if key not in RUNS:
        out = tempfile.mkdtemp(prefix='fi_out_%s_' % case)
        d = os.path.join(FIX, case)
        p = subprocess.run([sys.executable, TOOL, '--workbook', os.path.join(d, 'model_damaged.xlsx'),
                            '--evidence', os.path.join(d, 'evidence.json'), '--out-dir', out] + list(extra),
                           capture_output=True, text=True, timeout=300)
        assert p.returncode == 0, p.stdout + p.stderr
        res = {'dir': out, 'stdout': p.stdout.strip()}
        for name in ('rules', 'report_items', 'gaps', 'question', 'summary'):
            with open(os.path.join(out, name + '.json')) as fh:
                res[name] = json.load(fh)
        RUNS[key] = res
    return RUNS[key]


def norm(v):
    if hasattr(v, 'value'):
        v = v.value[0][0]
    if isinstance(v, (bool, str)) or v is None:
        return v
    try:
        return float(v)
    except (TypeError, ValueError):
        return str(v)


class Recalc:
    """A workbook loaded into the formulas package, recalculated with optional input overrides."""

    def __init__(self, path):
        self.xl = formulas.ExcelModel().loads(path).finish()
        self.keys = {}
        for k in self.xl.calculate():
            m = re.match(r"^'\[[^\]]+\](.+)'!([A-Z]+\d+)$", k)
            if m:
                self.keys[(m.group(1).upper(), m.group(2))] = k

    def calc(self, inputs=None):
        ov = {self.keys[k]: v for k, v in (inputs or {}).items() if k in self.keys}
        sol = self.xl.calculate(inputs=ov) if ov else self.xl.calculate()
        out = {}
        for k, v in sol.items():
            m = re.match(r"^'\[[^\]]+\](.+)'!([A-Z]+\d+)$", k)
            if m:
                out[(m.group(1).upper(), m.group(2))] = norm(v)
        return out


def same(a, b):
    if isinstance(a, float) and isinstance(b, float):
        return abs(a - b) <= 1e-6 * max(1.0, abs(a), abs(b))
    return a == b or (a in (None, 0.0) and b in (None, 0.0))


def cells_of(rng):
    """'Model!C12:J12' -> [('MODEL', 'C12'), ...]"""
    sheet, ref = rng.rsplit('!', 1)
    sheet = sheet.strip("'").upper()
    a, _, b = ref.partition(':')
    b = b or a
    (c1, r1), (c2, r2) = [re.match(r'([A-Z]+)(\d+)', x).groups() for x in (a, b)]
    from openpyxl.utils import column_index_from_string as ci, get_column_letter as gl
    return [(sheet, '%s%d' % (gl(c), r)) for r in range(int(r1), int(r2) + 1) for c in range(ci(c1), ci(c2) + 1)]


def originals(case):
    """(formula cells, numeric input cells) of the original model, keyed (SHEET_UPPER, 'A1')."""
    wb = openpyxl.load_workbook(os.path.join(FIX, case, 'model_original.xlsx'))
    f, inp = set(), {}
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for c in row:
                if isinstance(c.value, str) and c.value.startswith('='):
                    f.add((ws.title.upper(), c.coordinate))
                elif isinstance(c.value, (int, float)) and not isinstance(c.value, bool):
                    inp[(ws.title.upper(), c.coordinate)] = float(c.value)
    return f, inp


class FormulaInferTests(unittest.TestCase):
    CASES = ('a', 'b', 'c', 'd', 'g')

    def waiting_cells(self, res):
        q = res['question']
        if not q:
            return set()
        rule = next(r for r in res['rules'] if r['rule_id'] == q['rule_id'])
        return {c for rng in rule['cells'] for c in cells_of(rng)}

    def test_1_opens_and_recalc_flags(self):
        for case in self.CASES:
            with self.subTest(case=case):
                res = run_tool(case)
                path = os.path.join(res['dir'], 'model.xlsx')
                wb = openpyxl.load_workbook(path)
                self.assertEqual(wb.sheetnames, openpyxl.load_workbook(os.path.join(FIX, case, 'model_damaged.xlsx')).sheetnames)
                with zipfile.ZipFile(path) as z:
                    self.assertIn('fullCalcOnLoad="1"', z.read('xl/workbook.xml').decode())
                    self.assertNotIn('xl/calcChain.xml', z.namelist())
                nform = sum(1 for ws in wb.worksheets for row in ws.iter_rows() for c in row
                            if isinstance(c.value, str) and c.value.startswith('='))
                self.assertEqual(nform, res['summary']['formulas_rebuilt'])

    def test_2_reproduces_surviving_values(self):
        for case in self.CASES:
            with self.subTest(case=case):
                res = run_tool(case)
                got = Recalc(os.path.join(res['dir'], 'model.xlsx')).calc()
                wb = openpyxl.load_workbook(os.path.join(FIX, case, 'model_damaged.xlsx'))
                n = 0
                for ws in wb.worksheets:
                    for row in ws.iter_rows():
                        for c in row:
                            if isinstance(c.value, (int, float)) and not isinstance(c.value, bool):
                                k = (ws.title.upper(), c.coordinate)
                                self.assertTrue(same(float(c.value), got.get(k)), '%s: %s vs %s' % (k, c.value, got.get(k)))
                                n += 1
                self.assertGreater(n, 40)

    def test_3_random_scenarios_match_original(self):
        for case in self.CASES:
            with self.subTest(case=case):
                res = run_tool(case)
                skip = self.waiting_cells(res)
                fcells, inputs = originals(case)
                orig = Recalc(os.path.join(FIX, case, 'model_original.xlsx'))
                new = Recalc(os.path.join(res['dir'], 'model.xlsx'))
                rng = random.Random(1234)
                checked = 0
                for _ in range(5):
                    sc = {k: round(v * rng.uniform(0.7, 1.3), 2) for k, v in inputs.items()}
                    a, b = orig.calc(sc), new.calc(sc)
                    for k in sorted(fcells - skip):
                        self.assertTrue(same(a.get(k), b.get(k)), '%s %s: original %s, rebuilt %s' % (case, k, a.get(k), b.get(k)))
                        checked += 1
                self.assertGreater(checked, 5 * 30)

    def test_4_labels_follow_contract(self):
        for case in self.CASES:
            with self.subTest(case=case):
                res = run_tool(case)
                cnum = '%04d' % ('abcdefg'.index(case) + 1)
                s = res['summary']
                self.assertIn(s['status'], ('done', 'needs_client', 'failed'))
                self.assertEqual(set(s['counts']), LABELS)
                self.assertIsInstance(s['formulas_rebuilt'], int)
                self.assertIsInstance(s['questions'], int)
                for r in res['rules']:
                    self.assertRegex(r['rule_id'], r'^R-%s-\d{2}$' % cnum)
                    self.assertIn(r['status'], LABELS - {'recovered'})
                    self.assertTrue(r['cells'] and r['description'] and ('formula_pattern' in r or 'formula_r1c1' in r))
                    for alt in r['alternatives']:
                        self.assertEqual(set(alt), {'formula_pattern', 'differs_when'})
                for it in res['report_items']:
                    self.assertEqual(set(it), {'item', 'label', 'cites'})
                    self.assertIn(it['label'], LABELS)
                    self.assertTrue(it['cites'], it)
                for g in res['gaps']:
                    self.assertRegex(g['gap_id'], r'^G-%s-\d{2}$' % cnum)
                    self.assertEqual(g['status'], 'open')
                    self.assertTrue(g['where_to_look'] and g['what'] and g['why'])
                by_item = {}
                for it in res['report_items']:
                    by_item.setdefault(it['item'].split(' ')[0], it)
                if case == 'a':
                    self.assertEqual(by_item['Model!E4']['label'], 'recovered')
                    self.assertIn('F-0001-012', by_item['Model!E4']['cites'])
                    self.assertEqual(by_item['Model!D8']['label'], 'reconstructed and tested')
                    self.assertIn('F-0001-005', by_item['Model!D8']['cites'])
                    self.assertEqual(by_item['Model!G15']['label'], 'reconstructed but untested')
                    self.assertEqual(by_item['Model!F16']['label'], 'reconstructed but untested')
                    disc = next(r for r in res['rules'] if 'Discount' in r['description'])
                    self.assertEqual(disc['status'], 'reconstructed but untested')
                    self.assertTrue(disc['alternatives'])
                if case == 'b':
                    self.assertEqual(by_item['SaaS!G17']['label'], 'unresolved')
                    self.assertTrue(any('SaaS!G17' in g['what'] for g in res['gaps']))
                    self.assertEqual(by_item['SaaS!B10']['label'], 'reconstructed and tested')  # solved exactly from survivors
                    self.assertEqual(by_item['SaaS!E13']['label'], 'reconstructed and tested')
                    self.assertIn('F-0002-003', by_item['SaaS!E13']['cites'])
                    self.assertEqual(s['counts']['unresolved'], 1)
                if case == 'g':
                    self.assertEqual(by_item['Model!G10']['label'], 'recovered')  # typed override kept and flagged
                    self.assertTrue(any('Model!G10' in g['what'] for g in res['gaps']))
                    pats = ' '.join(r['formula_pattern'] for r in res['rules'])
                    for frag in ('MIN(', 'MAX(', 'Model!B6', 'Rates!C2', ',IF(', '$B$9+'):
                        self.assertIn(frag, pats)
                if case == 'c':
                    self.assertEqual(by_item['P&L!J7']['label'], 'reconstructed but untested')
                    self.assertEqual(s['counts']['unresolved'], 0)

    def test_5_question_only_for_a(self):
        for case in self.CASES:
            with self.subTest(case=case):
                res = run_tool(case)
                if case == 'a':
                    q = res['question']
                    self.assertEqual(res['summary']['status'], 'needs_client')
                    self.assertEqual(res['summary']['questions'], 1)
                    self.assertEqual(set(q), {'rule_id', 'question', 'options', 'probe'})
                    self.assertIn('50,000.00', q['question'])
                    self.assertIn('Orders over $50,000', q['question'])
                    self.assertLessEqual(len(q['question']), 200)
                    self.assertEqual(q['question'].count('?'), 1)
                    self.assertTrue(q['question'].endswith('?') and '. ' not in q['question'])
                    self.assertEqual(len(q['options']), 2)
                    self.assertEqual(sorted(q['probe']['outputs']), [0.0, 5000.0])
                    self.assertIn('1 question for the client', res['stdout'])
                else:
                    self.assertIsNone(res['question'])
                    self.assertEqual(res['summary']['status'], 'done')
                    self.assertEqual(res['summary']['questions'], 0)

    def test_7_one_sided_threshold_asks(self):
        for case in ('e', 'f'):  # the data never cross the threshold: ask about the other side, never pick silently
            with self.subTest(case=case):
                res = run_tool(case)
                q = res['question']
                self.assertEqual(res['summary']['status'], 'needs_client')
                self.assertIn('50,000.00', q['question'])
                self.assertLessEqual(len(q['question']), 200)
                self.assertTrue(any('>' in r['formula_pattern'] or 'IF(' in a['formula_pattern']
                                    for r in res['rules'] if r['rule_id'] == q['rule_id'] for a in r['alternatives']))
                skip = self.waiting_cells(res)
                fcells, inputs = originals(case)
                a = Recalc(os.path.join(FIX, case, 'model_original.xlsx')).calc()
                b = Recalc(os.path.join(res['dir'], 'model.xlsx')).calc()
                for k in fcells - skip:
                    if k[1][0] != 'J' and k not in {('MODEL', c + '8') for c in 'BCDEFGHI'}:
                        self.assertTrue(same(a.get(k), b.get(k)), k)

    def test_6_answer_resolves_question(self):
        q = run_tool('a')['question']
        idx = next(i for i, o in enumerate(q['options']) if '>=' in o)  # the original model uses >=
        res = run_tool('a', '--answer', '%s=%d' % (q['rule_id'], idx))
        self.assertIsNone(res['question'])
        self.assertEqual(res['summary']['status'], 'done')
        rule = next(r for r in res['rules'] if r['rule_id'] == q['rule_id'])
        self.assertEqual(rule['status'], 'reconstructed and tested')
        self.assertIn('client answer', rule['evidence'])
        self.assertIn('>=', rule['formula_pattern'])
        # gross sales exactly at the threshold: the answered model must match the original, the unanswered default not
        fcells, inputs = originals('a')
        sc = dict(inputs)
        sc[('MODEL', 'B4')] = 2000.0  # 2000 units x $25 = $50,000.00 exactly
        orig = Recalc(os.path.join(FIX, 'a', 'model_original.xlsx')).calc(sc)
        answered = Recalc(os.path.join(res['dir'], 'model.xlsx')).calc(sc)
        default = Recalc(os.path.join(run_tool('a')['dir'], 'model.xlsx')).calc(sc)
        for k in fcells:
            self.assertTrue(same(orig.get(k), answered.get(k)), '%s: %s vs %s' % (k, orig.get(k), answered.get(k)))
        self.assertFalse(same(orig[('MODEL', 'B7')], default[('MODEL', 'B7')]))


if __name__ == '__main__':
    unittest.main(verbosity=2)
