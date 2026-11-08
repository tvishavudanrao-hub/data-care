import json
import os
import tempfile
import unittest
import zipfile

import forensics_scan as fs

SHEET = '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>%s</sheetData></worksheet>'


def make_xlsx(path, cells):
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("xl/workbook.xml", "<workbook/>")
        z.writestr("xl/worksheets/sheet1.xml", SHEET % ('<row r="1">%s</row>' % cells))


class ForensicsScanTests(unittest.TestCase):
    def run_scan(self, files):
        d = tempfile.mkdtemp()
        i, o = os.path.join(d, "in"), os.path.join(d, "out")
        os.makedirs(i)
        for n, b in files.items():
            if callable(b):
                b(os.path.join(i, n))
            else:
                with open(os.path.join(i, n), "wb") as fh:
                    fh.write(b)
        return fs.scan("C-0001", i, o), o

    def test_values_without_formulas_flagged_missing(self):
        r, _ = self.run_scan({"m.xlsx": lambda p: make_xlsx(p, '<c r="A1"><v>5</v></c><c r="B1"><v>7</v></c>')})
        f = r["files"][0]
        self.assertEqual(f["status"], "damaged")
        self.assertTrue(any(x["class"] == "missing" for x in f["findings"]))

    def test_error_cell_flagged_and_formulas_not_missing(self):
        r, _ = self.run_scan({"m.xlsx": lambda p: make_xlsx(
            p, '<c r="A1"><f>1+1</f><v>2</v></c><c r="B1" t="e"><v>#REF!</v></c>')})
        cls = [x["class"] for x in r["files"][0]["findings"]]
        self.assertIn("corrupted", cls)
        self.assertNotIn("missing", cls)

    def test_marker_quarantined_not_in_working(self):
        r, o = self.run_scan({"n.txt": b"hello " + fs.EICAR_MARK})
        self.assertEqual(r["files"][0]["status"], "quarantined")
        self.assertTrue(os.path.exists(os.path.join(o, "quarantine", "n.txt")))
        self.assertFalse(os.path.exists(os.path.join(o, "working", "n.txt")))

    def test_secret_value_never_stored(self):
        r, o = self.run_scan({"c.txt": b"x\npassword = hunter2hunter2\n"})
        self.assertIn("line 2", json.dumps(r))
        with open(os.path.join(o, "damage_report.json")) as fh:
            self.assertNotIn("hunter2", fh.read())

    def test_unreadable_and_ragged_rows(self):
        r, _ = self.run_scan({"a.csv": b"a,b\n1,2\n3,\xff\xfe\n5,6,7\n"})
        locs = [x["where"] for x in r["files"][0]["findings"]]
        self.assertIn("line 3", locs)
        self.assertIn("line 4", locs)

    def test_ids_use_forensics_block_and_file_names(self):
        r, o = self.run_scan({"m.xlsx": lambda p: make_xlsx(p, '<c r="A1"><v>5</v></c>')})
        with open(os.path.join(o, "forensics_fragments.json")) as fh:
            self.assertTrue(json.load(fh)[0]["fragment_id"].startswith("F-0001-9"))
        with open(os.path.join(o, "forensics_gaps.json")) as fh:
            self.assertEqual(json.load(fh)[0]["gap_id"], "G-0001-91")
        self.assertFalse(os.path.exists(os.path.join(o, "fragments.json")))

    def test_macro_project_flagged(self):
        def mk(p):
            make_xlsx(p, '<c r="A1"><f>1</f><v>1</v></c>')
            with zipfile.ZipFile(p, "a") as z:
                z.writestr("xl/vbaProject.bin", b"x")
        r, _ = self.run_scan({"m.xlsx": mk})
        self.assertTrue(any("macro" in x["detail"] for x in r["files"][0]["findings"]))

    def test_symlink_not_followed(self):
        d = tempfile.mkdtemp()
        i = os.path.join(d, "in")
        os.makedirs(i)
        try:
            os.symlink(os.path.join(d, "target"), os.path.join(i, "link.txt"))
        except (OSError, NotImplementedError):
            self.skipTest("symlinks not available")
        r = fs.scan("C-0001", i, os.path.join(d, "out"))
        self.assertEqual(r["files"][0]["status"], "skipped")

    def test_scanned_pdf_needs_visual_reading(self):
        scanned = b"%PDF-1.4\n1 0 obj<</Type /Page>>endobj\n2 0 obj<</Subtype /Image /Width 10>>endobj\n%%EOF"
        r, o = self.run_scan({"invoice.pdf": scanned})
        f = r["files"][0]
        self.assertEqual(f["status"], "needs-visual-reading")
        self.assertIn("scanned PDF", f["findings"][0]["detail"])
        with open(os.path.join(o, "forensics_gaps.json")) as fh:
            self.assertIn("image-capable", json.load(fh)[0]["where_to_look"][0])
        self.assertIn("invoice.pdf", r["possible_source_files"])

    def test_text_pdf_is_clean(self):
        text = b"%PDF-1.4\n1 0 obj<</Type /Page>>endobj\n2 0 obj<</Length 30>>stream\nBT /F1 12 Tf (Invoice 42) Tj ET\nendstream\nendobj\n%%EOF"
        r, _ = self.run_scan({"invoice.pdf": text})
        self.assertEqual(r["files"][0]["status"], "clean")

    def test_compressed_text_stream_counts_as_text(self):
        import zlib
        stream = zlib.compress(b"BT /F1 12 Tf (Lot 77) Tj ET")
        pdf = b"%PDF-1.4\n1 0 obj<</Type /Page>>endobj\n2 0 obj<</Length 10>>stream\n" + stream + b"\nendstream\nendobj\n%%EOF"
        r, _ = self.run_scan({"a.pdf": pdf})
        self.assertEqual(r["files"][0]["status"], "clean")

    def test_image_flagged_for_visual_reading(self):
        r, _ = self.run_scan({"receipt.png": b"\x89PNG\r\n\x1a\n" + b"\x00" * 20})
        self.assertEqual(r["files"][0]["detected_type"], "image")
        self.assertEqual(r["files"][0]["status"], "needs-visual-reading")

    def test_extension_mismatch(self):
        r, _ = self.run_scan({"fake.xlsx": b"just text"})
        self.assertTrue(any(x["class"] == "inconsistent" for x in r["files"][0]["findings"]))


if __name__ == "__main__":
    unittest.main()
