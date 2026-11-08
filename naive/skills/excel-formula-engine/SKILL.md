# Excel formula engine (formula_infer.py)

Use this for every case of kind "excel": a workbook whose formulas were pasted over as plain values, often with a few blank or #REF! cells. It is tool 4 of the reconstruction-toolkit skill; follow that skill's Excel steps.

## Run it
- Naive library folders are flat: a folder name can't contain "/". Each case uses one folder per stage, named <case_id>-<stage>: C-0001-incoming, C-0001-quarantine, C-0001-working, C-0001-evidence, C-0001-rebuilt, C-0001-report. Older notes that say cases/C-0001/working/ mean the folder C-0001-working. In hand-off JSON a file is "<folder>/<file name>". If your publish_file cannot set a folder, start the file name with the folder name and two underscores: C-0001-rebuilt__model.xlsx.
1. Get the tool from the file library: use find_files to find formula_infer.py in the folder tools (take the newest), then fetch_file it into your sandbox as formula_infer.py. Never retype it: it is long and one wrong character breaks it. If find_files or fetch_file is missing, or the file is not there, reply with status "failed" and the note "formula tool missing".
2. Run:
   `python3 formula_infer.py --workbook model.xlsx --evidence evidence.json --case <case_id> --out-dir rebuilt/`
   Leave out --evidence if Context found none. It needs only standard Python 3, no packages, no network.
3. Read rebuilt/summary.json.
   - "needs_client": rebuilt/question.json holds one question. Put it in your reply to the Recovery Manager word for word, with status needs_client. When the answer comes back, rerun with `--answer <rule_id>=<option index>` (the index is into question.json's options).
   - "done": publish the outputs.
   - "failed": reply failed and paste the last lines of the error in the note.
4. Outputs in rebuilt/: model.xlsx (formulas restored; it recalculates when opened), rules.json, report_items.json, gaps.json, question.json, summary.json, manifest.json (the list Validation's checker reads: unresolved cells, rule per row, rows waiting on the client). Publish them to the folder <case_id>-rebuilt.

## What it does, so you can explain it to the client
- It finds the rows whose values follow one formula across every period (sums, differences, products, ratios, growth, tiered discounts with IF, references to an assumptions sheet) and keeps only formulas that reproduce every surviving value.
- It fills blank or broken cells from the row's formula, or, for raw inputs, from the evidence Context found.
- When two readings both fit the data but would disagree on some input, it never picks one: it writes the question.
- Every item gets one of four labels: recovered, reconstructed and tested, reconstructed but untested, unresolved.
- It never runs the client's file. It reads it as data.
- Its source is also in the team repo at naive/lib/formula_infer.py.
