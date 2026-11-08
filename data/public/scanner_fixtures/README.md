# Scanner fixture (harmless)

`EICAR_TEST_MARKER_harmless.txt` holds the standard EICAR antivirus test
string. It is inert text that antivirus tools detect on purpose. It is not
malware. The Salvage agent's static scanner should flag and quarantine it.
**Never execute it.**

The file is not committed, because antivirus on teammates' machines would
quarantine it on checkout. `python -m data.generate` writes it locally
(Verify owner), or build it from the two halves in `data/generate.py`
(`EICAR_PARTS`). Its sha256 is listed in `data/public/MANIFEST.json`.
