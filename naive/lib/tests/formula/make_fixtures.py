#!/usr/bin/env python3
"""Build dev fixtures for formula_infer.py: original models with real formulas, damaged copies (formulas pasted as
values, some cells blank or #REF!), and evidence.json files. Uses openpyxl + formulas (dev only).

  python3 make_fixtures.py [out_dir]     (default: ./fixtures next to this file)
"""
import json, os, re, sys
import openpyxl
import formulas

HERE = os.path.dirname(os.path.abspath(__file__))


def calc(path):
    """Compute every cell with the formulas package. Returns {(SHEET_UPPER, 'A1'): value}."""
    xl = formulas.ExcelModel().loads(path).finish()
    out = {}
    for k, v in xl.calculate().items():
        m = re.match(r"^'\[[^\]]+\](.+)'!([A-Z]+\d+)$", k)
        if m:
            val = v.value[0][0] if hasattr(v, 'value') else v
            out[(m.group(1).upper(), m.group(2))] = val
    return out


def plain(v):
    if isinstance(v, bool) or v is None or isinstance(v, str):
        return v
    try:
        return float(v)
    except (TypeError, ValueError):
        return str(v)


def damage(orig, dst, blanks=(), refs=()):
    """Paste every formula as its value, then blank some cells and put #REF! in others."""
    vals = calc(orig)
    wb = openpyxl.load_workbook(orig)
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for c in row:
                if isinstance(c.value, str) and c.value.startswith('='):
                    c.value = plain(vals[(ws.title.upper(), c.coordinate)])
    for sheet, ref in blanks:
        wb[sheet][ref].value = None
    for sheet, ref in refs:
        wb[sheet][ref].value = '#REF!'
    wb.save(dst)


def model_a(path, units=(1800, 1950, 2100, 1700, 2300, 2450, 2050, 2600)):
    """(a) quarterly revenue model: units x price, tiered discount (>=, threshold never hit exactly), COGS %, opex."""
    wb = openpyxl.Workbook()
    m = wb.active
    m.title = 'Model'
    a = wb.create_sheet('Assumptions')
    for i, (lab, v) in enumerate([('Assumption', 'Value'), ('Price per unit', 25), ('Discount threshold', 50000),
                                  ('Discount rate', 0.1), ('COGS % of net revenue', 0.4), ('Rent per quarter', 12000),
                                  ('Marketing % of net revenue', 0.08)], start=1):
        a.cell(i, 1, lab)
        a.cell(i, 2, v)
    m['A1'] = 'Quarterly revenue model'
    m['A3'] = 'Line item'
    cols = 'BCDEFGHI'
    for i, c in enumerate(cols):
        m[c + '3'] = 'Q%d' % (i + 1)
    m['J3'] = 'FY total'
    salaries = [20000, 20000, 22000, 22000, 24000, 24000, 26000, 26000]
    labels = {4: 'Units sold', 5: 'Price per unit', 6: 'Gross sales', 7: 'Discount', 8: 'Net revenue', 9: 'COGS',
              10: 'Gross margin', 11: 'Gross margin %', 13: 'Salaries', 14: 'Rent', 15: 'Marketing', 16: 'Total opex',
              17: 'Operating income', 18: 'Revenue growth %'}
    for r, lab in labels.items():
        m['A%d' % r] = lab
    for i, c in enumerate(cols):
        p = cols[i - 1] if i else None
        m[c + '4'] = units[i]
        m[c + '5'] = '=Assumptions!$B$2'
        m[c + '6'] = '=%s4*%s5' % (c, c)
        m[c + '7'] = '=IF(%s6>=Assumptions!$B$3,%s6*Assumptions!$B$4,0)' % (c, c)
        m[c + '8'] = '=%s6-%s7' % (c, c)
        m[c + '9'] = '=%s8*Assumptions!$B$5' % c
        m[c + '10'] = '=%s8-%s9' % (c, c)
        m[c + '11'] = '=%s10/%s8' % (c, c)
        m[c + '13'] = salaries[i]
        m[c + '14'] = '=Assumptions!$B$6'
        m[c + '15'] = '=%s8*Assumptions!$B$7' % c
        m[c + '16'] = '=SUM(%s13:%s15)' % (c, c)
        m[c + '17'] = '=%s10-%s16' % (c, c)
        if p:
            m[c + '18'] = '=%s8/%s8-1' % (c, p)
    for r in (4, 6, 7, 8, 9, 10, 13, 14, 15, 16, 17):
        m['J%d' % r] = '=SUM(B%d:I%d)' % (r, r)
    m['J11'] = '=J10/J8'
    wb.save(path)


def model_b(path):
    """(b) monthly SaaS: assumptions at the top of the same sheet, lagged references, ROUND(...,0), cumulative."""
    wb = openpyxl.Workbook()
    s = wb.active
    s.title = 'SaaS'
    s['A1'] = 'SaaS metrics model'
    for r, (lab, v) in enumerate([('ARPU (monthly)', 49), ('Monthly churn rate', 0.03), ('Starting customers', 400),
                                  ('New customer growth', 0.05)], start=3):
        s.cell(r, 1, lab)
        s.cell(r, 2, v)
    s['A8'] = 'Metric'
    months = 'Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec'.split()
    cols = [openpyxl.utils.get_column_letter(i) for i in range(2, 14)]
    for c, mo in zip(cols, months):
        s[c + '8'] = '%s 2025' % mo
    labels = {9: 'Customers (start of month)', 10: 'New customers', 11: 'Churned customers', 12: 'Customers (end of month)',
              13: 'MRR', 14: 'Cumulative revenue', 15: 'Churn % (actual)', 16: 'MRR growth %', 17: 'Marketing spend',
              18: 'CAC'}
    for r, lab in labels.items():
        s['A%d' % r] = lab
    spend = [5000, 5200, 5400, 5100, 5600, 5900, 6100, 6000, 6300, 6500, 6200, 6800]
    for i, c in enumerate(cols):
        p = cols[i - 1] if i else None
        s[c + '9'] = '=%s12' % p if p else '=$B$5'
        s[c + '10'] = '=ROUND(%s10*(1+$B$6),0)' % p if p else 60
        s[c + '11'] = '=ROUND(%s9*$B$4,0)' % c
        s[c + '12'] = '=%s9+%s10-%s11' % (c, c, c)
        s[c + '13'] = '=%s12*$B$3' % c
        s[c + '14'] = '=%s14+%s13' % (p, c) if p else '=%s13' % c
        s[c + '15'] = '=%s11/%s9' % (c, c)
        if p:
            s[c + '16'] = '=%s13/%s13-1' % (c, p)
        s[c + '17'] = spend[i]
        s[c + '18'] = '=%s17/%s10' % (c, c)
    wb.save(path)


def model_c(path):
    """(c) threshold hit exactly (no question), two-rate tier, ROUND(...,2), FY sub-totals, quoted sheet names."""
    wb = openpyxl.Workbook()
    m = wb.active
    m.title = 'P&L'
    rc = wb.create_sheet('Rate Card')
    for i, (lab, v) in enumerate([('Rate', 'Value'), ('Price per unit', 25), ('Discount threshold', 50000),
                                  ('Discount rate above threshold', 0.1), ('Discount rate at or below threshold', 0.02),
                                  ('COGS rate', 0.3725), ('Fixed costs per quarter', 9000)], start=1):
        rc.cell(i, 1, lab)
        rc.cell(i, 2, v)
    m['A2'] = 'Line item'
    cols = 'BCDEFGHI'
    for i, c in enumerate(cols):
        m[c + '2'] = 'Q%d %d' % (i % 4 + 1, 2025 + i // 4)
    m['J2'], m['K2'] = 'FY 2025', 'FY 2026'
    labels = {3: 'Units sold', 4: 'Price per unit', 5: 'Gross sales', 6: 'Discount', 7: 'Net revenue', 8: 'COGS',
              9: 'Gross profit', 10: 'Operating cash'}
    for r, lab in labels.items():
        m['A%d' % r] = lab
    units = [1800, 2000, 2150, 1900, 2000, 2400, 2250, 2600]
    for i, c in enumerate(cols):
        m[c + '3'] = units[i]
        m[c + '4'] = "='Rate Card'!$B$2"
        m[c + '5'] = '=%s3*%s4' % (c, c)
        m[c + '6'] = "=IF(%s5>'Rate Card'!$B$3,%s5*'Rate Card'!$B$4,%s5*'Rate Card'!$B$5)" % (c, c, c)
        m[c + '7'] = '=%s5-%s6' % (c, c)
        m[c + '8'] = "=ROUND(%s7*'Rate Card'!$B$6,2)" % c
        m[c + '9'] = '=%s7-%s8' % (c, c)
        m[c + '10'] = "=%s9-'Rate Card'!$B$7" % c
    for r in (3, 5, 6, 7, 8, 9, 10):
        m['J%d' % r] = '=SUM(B%d:E%d)' % (r, r)
        m['K%d' % r] = '=SUM(F%d:I%d)' % (r, r)
    wb.save(path)


def model_d(path):
    """(d) layout variants: row numbers in column A, labels in B, '2025 Q1' headers, a Total column, assumptions to the
    right of the grid, tax only on profit (IF around 0 with loss quarters), revenue per head, cumulative net income."""
    wb = openpyxl.Workbook()
    m = wb.active
    m.title = 'Forecast'
    m['B1'] = 'Five-year forecast (extract)'
    m['B2'] = 'Line'
    cols = 'CDEFGHIJ'
    for i, c in enumerate(cols):
        m[c + '2'] = '%d Q%d' % (2025 + i // 4, i % 4 + 1)
    m['K2'] = 'Total'
    m['M2'], m['N2'] = 'Assumption', 'Value'
    m['M3'], m['N3'] = 'Tax rate', 0.25
    m['M4'], m['N4'] = 'COGS % of revenue', 0.35
    labels = ['Revenue', 'COGS', 'Gross profit', 'Operating expenses', 'EBIT', 'Tax', 'Net income', 'Headcount',
              'Revenue per head', 'Cumulative net income']
    for i, lab in enumerate(labels):
        m['A%d' % (i + 3)] = i + 1
        m['B%d' % (i + 3)] = lab
    revenue = [120000, 95000, 143000, 88000, 160500, 171000, 99000, 185250]
    opex = [70000, 72000, 74000, 76000, 78000, 80000, 82000, 84000]
    heads = [11, 12, 12, 13, 14, 14, 15, 16]
    for i, c in enumerate(cols):
        p = cols[i - 1] if i else None
        m[c + '3'] = revenue[i]
        m[c + '4'] = '=%s3*$N$4' % c
        m[c + '5'] = '=%s3-%s4' % (c, c)
        m[c + '6'] = opex[i]
        m[c + '7'] = '=%s5-%s6' % (c, c)
        m[c + '8'] = '=IF(%s7>0,%s7*$N$3,0)' % (c, c)
        m[c + '9'] = '=%s7-%s8' % (c, c)
        m[c + '10'] = heads[i]
        m[c + '11'] = '=%s3/%s10' % (c, c)
        m[c + '12'] = '=%s12+%s9' % (p, c) if p else '=%s9' % c
    for r in (3, 4, 5, 6, 7, 8, 9):
        m['K%d' % r] = '=SUM(C%d:J%d)' % (r, r)
    wb.save(path)


def model_g(path):
    """(g) Summary sheet pulling from Model, per-period FX rates on another sheet, two-tier discount decided by the
    data, capped commission (MIN), tax ROUND(MAX(0,x)*rate,2), benefits = salaries x % + fixed, units actual then
    forecast, and one typed override in Rent."""
    wb = openpyxl.Workbook()
    sm = wb.active
    sm.title = 'Summary'
    m, rt, a = wb.create_sheet('Model'), wb.create_sheet('Rates'), wb.create_sheet('Assumptions')
    rows = [('Assumption', 'Value'), ('Price per unit', 40), ('Tier 1 threshold', 50000), ('Tier 2 threshold', 100000),
            ('Tier 1 discount rate', 0.05), ('Tier 2 discount rate', 0.12), ('Commission rate', 0.06),
            ('Commission cap', 4000), ('Benefits % of salaries', 0.2), ('Benefits fixed per quarter', 1500),
            ('Tax rate', 0.25), ('Unit growth (forecast)', 0.08), ('Rent per quarter', 9000)]
    for i, (lab, v) in enumerate(rows, start=1):
        a.cell(i, 1, lab)
        a.cell(i, 2, v)
    cols = 'BCDEFGHI'
    A = lambda r: 'Assumptions!$B$%d' % r
    m['A1'] = 'Line item'
    for i, c in enumerate(cols):
        m[c + '1'] = 'Q%d' % (i + 1)
    labels = ['Units sold', 'Price per unit', 'Gross sales', 'Discount', 'Net revenue', 'Commission', 'Salaries',
              'Benefits', 'Rent', 'Total costs', 'EBIT', 'Tax', 'Net income', 'Net revenue (EUR)']
    for i, lab in enumerate(labels, start=2):
        m['A%d' % i] = lab
    units, sal = [1100, 1250, 2500, 1900], [30000, 30000, 32000, 32000, 34000, 34000, 36000, 36000]
    rt['A1'], rt['B1'], rt['A2'], rt['B2'] = 'Rate', 'Unit', 'EUR per USD', 'EUR'
    fx = [0.92, 0.93, 0.91, 0.9, 0.94, 0.95, 0.93, 0.92]
    for i, c in enumerate(cols):
        p, rc = (cols[i - 1] if i else None), 'CDEFGHIJ'[i]
        rt[rc + '1'], rt[rc + '2'] = 'Q%d' % (i + 1), fx[i]
        m[c + '2'] = units[i] if i < 4 else '=%s2*(1+%s)' % (p, A(12))
        m[c + '3'] = '=' + A(2)
        m[c + '4'] = '=%s2*%s3' % (c, c)
        m[c + '5'] = '=IF(%s4>%s,%s4*%s,IF(%s4>=%s,%s4*%s,0))' % (c, A(4), c, A(6), c, A(3), c, A(5))
        m[c + '6'] = '=%s4-%s5' % (c, c)
        m[c + '7'] = '=MIN(%s6*%s,%s)' % (c, A(7), A(8))
        m[c + '8'] = sal[i]
        m[c + '9'] = '=%s8*%s+%s' % (c, A(9), A(10))
        m[c + '10'] = 12000 if c == 'G' else '=' + A(13)
        m[c + '11'] = '=SUM(%s7:%s10)' % (c, c)
        m[c + '12'] = '=%s6-%s11' % (c, c)
        m[c + '13'] = '=ROUND(MAX(0,%s12)*%s,2)' % (c, A(11))
        m[c + '14'] = '=%s12-%s13' % (c, c)
        m[c + '15'] = '=%s6*Rates!%s2' % (c, rc)
    sm['A1'] = 'Summary'
    sm['A3'] = 'Metric'
    for i, c in enumerate(cols):
        sm[c + '3'] = 'Q%d' % (i + 1)
        sm[c + '4'] = '=Model!%s6' % c
        sm[c + '5'] = '=Model!%s12' % c
        sm[c + '6'] = '=Model!%s14' % c
        sm[c + '7'] = '=%s6/%s4' % (c, c)
    for r, lab in ((4, 'Net revenue'), (5, 'EBIT'), (6, 'Net income'), (7, 'Net margin %')):
        sm['A%d' % r] = lab
    wb.save(path)


CASES = {
    'a': dict(build=model_a, blanks=[('Model', 'E4'), ('Model', 'D8'), ('Model', 'G15')], refs=[('Model', 'F16')],
              evidence={'case_id': 'C-0001',
                        'values': [{'label': 'Units sold', 'period': 'Q4', 'value': 1700.0, 'source': 'sales_export.csv#row5',
                                    'fragment_id': 'F-0001-012'}],
                        'reported': [{'label': 'Net Revenue', 'period': 'Q3', 'value': 47250.0,
                                      'source': 'board_report_q3.csv#row3', 'fragment_id': 'F-0001-005'}],
                        'rules': [{'text': 'Orders over $50,000 get 10% off.', 'numbers': [50000.0, 0.10],
                                   'operator_hint': '>', 'source': 'cfo_email.eml#line12', 'fragment_id': 'F-0001-020'}]}),
    'b': dict(build=model_b, blanks=[('SaaS', 'B10'), ('SaaS', 'H10'), ('SaaS', 'G18')], refs=[('SaaS', 'E13'), ('SaaS', 'G17')],
              evidence={'case_id': 'C-0002', 'values': [],
                        'reported': [{'label': 'mrr', 'period': '2025 Apr', 'value': 29498.0,
                                      'source': 'investor_update_apr.pdf#p2', 'fragment_id': 'F-0002-003'}],
                        'rules': []}),
    'c': dict(build=model_c, blanks=[('P&L', 'D8'), ('P&L', 'F3')], refs=[('P&L', 'J7')],
              evidence={'case_id': 'C-0003', 'values': [], 'reported': [], 'rules': []}),
    'd': dict(build=model_d, blanks=[('Forecast', 'F8'), ('Forecast', 'H12')], refs=[('Forecast', 'D3')],
              evidence={'case_id': 'C-0004', 'values': [], 'reported': [], 'rules': []}),
    'g': dict(build=model_g, blanks=[('Model', 'D7'), ('Summary', 'E5')], refs=[('Model', 'I15')],
              evidence={'case_id': 'C-0007', 'values': [], 'reported': [], 'rules': []}),
    # one-sided thresholds: every quarter above it (e), or none reaching it (f) -> a question about the other side
    'e': dict(build=lambda p: model_a(p, units=(2100, 2200, 2300, 2150, 2400, 2500, 2250, 2600)), blanks=[], refs=[],
              evidence={'case_id': 'C-0005', 'values': [], 'reported': [], 'rules': []}),
    'f': dict(build=lambda p: model_a(p, units=(1500, 1600, 1700, 1650, 1800, 1900, 1750, 1950)), blanks=[], refs=[],
              evidence={'case_id': 'C-0006', 'values': [], 'reported': [], 'rules': []}),
}


def build(out):
    os.makedirs(out, exist_ok=True)
    for name, spec in CASES.items():
        d = os.path.join(out, name)
        os.makedirs(d, exist_ok=True)
        orig, dmg = os.path.join(d, 'model_original.xlsx'), os.path.join(d, 'model_damaged.xlsx')
        spec['build'](orig)
        damage(orig, dmg, spec['blanks'], spec['refs'])
        with open(os.path.join(d, 'evidence.json'), 'w') as fh:
            json.dump(spec['evidence'], fh, indent=2)
    return out


if __name__ == '__main__':
    print(build(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'fixtures')))
