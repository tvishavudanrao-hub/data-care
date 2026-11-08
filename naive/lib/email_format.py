#!/usr/bin/env python3
"""email_format.py: turn a Data Care email's content into a branded HTML email plus a
plain-text version, so every client email looks the same and reads well everywhere.

Standard library only (runs in any Naive sandbox). Input is a small JSON file:

    {
      "kind": "quote",                      # receipt | quote | question | update | delivery | closing
      "case_id": "C-0005",
      "recipient_name": "Marek",            # first name if known; empty -> "Hello,"
      "title": "Your quote for case C-0005",
      "paragraphs": ["We received your workbook ...", "..."],
      "table": [["Service", "Excel formula recovery"], ["Price", "$450 (not to exceed)"]],
      "bullets": ["Recovered: 27", "Reconstructed and tested: 81"],
      "callout": "Reply APPROVE to start. Nothing begins until you do.",
      "closing": "Kind regards,"
    }

    python3 email_format.py --file content.json      # prints {"html": "...", "text": "..."}

Pass "html" and "text" to agentmail.send_message / reply_to_message together.

Every value is HTML-escaped: client-supplied text (names, descriptions) can never inject
markup or links. No images or remote resources are loaded (nothing is tracked).
"""

import argparse
import html
import json
import re
import sys

BRAND = "Data Care"
TAGLINE = "We rebuild what you lost from what survives."
INBOX = "datacare-recover@agentmail.to"
LABELS_NOTE = ("Every item in our reports is labeled recovered, reconstructed and tested, "
               "reconstructed but untested, or unresolved. We never guess a value.")

INK = "#1f2933"
MUTED = "#616e7c"
ACCENT = "#0b6e4f"
RULE = "#e4e7eb"
PANEL = "#f5f7fa"
FONT = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif"

KIND_LABEL = {
    "receipt": "Case opened",
    "quote": "Quote",
    "question": "One question",
    "update": "Case update",
    "delivery": "Your recovery is ready",
    "closing": "Case closed",
}


def esc(value) -> str:
    return html.escape(str(value or ""), quote=True)


def clean_name(name: str) -> str:
    """A first name, or '' when we only have an address or a domain."""
    name = (name or "").strip()
    if not name or "@" in name or "." in name.split()[0] and " " not in name:
        return ""
    if re.fullmatch(r"[A-Za-z0-9.-]+\.[A-Za-z]{2,}", name):  # looks like a domain
        return ""
    return name.split()[0][:40]


def greeting(name: str) -> str:
    first = clean_name(name)
    return f"Dear {first}," if first else "Hello,"


def build(c: dict) -> dict:
    kind = c.get("kind", "update")
    case_id = c.get("case_id", "")
    title = c.get("title") or KIND_LABEL.get(kind, "Case update")
    paras = [p for p in c.get("paragraphs", []) if str(p).strip()]
    table = [r for r in c.get("table", []) if isinstance(r, (list, tuple)) and len(r) == 2]
    bullets = [b for b in c.get("bullets", []) if str(b).strip()]
    callout = c.get("callout", "")
    closing = c.get("closing") or "Kind regards,"
    hello = greeting(c.get("recipient_name", ""))

    # ---------- plain text ----------
    t = [hello, ""]
    for p in paras:
        t += [str(p), ""]
    if table:
        width = max(len(str(k)) for k, _ in table)
        t += [f"  {str(k).ljust(width)}  {v}" for k, v in table] + [""]
    if bullets:
        t += [f"  - {b}" for b in bullets] + [""]
    if callout:
        t += [str(callout), ""]
    t += [closing, f"The {BRAND} team", INBOX, ""]
    if case_id:
        t += [f"Case {case_id}"]
    t += [LABELS_NOTE]
    text = "\n".join(t).strip() + "\n"

    # ---------- HTML (table layout + inline styles: renders in Gmail, Outlook, Apple Mail) ----------
    p_style = f"margin:0 0 16px 0;font-size:15px;line-height:1.6;color:{INK};"
    body = [f'<p style="{p_style}">{esc(hello)}</p>']
    body += [f'<p style="{p_style}">{esc(p)}</p>' for p in paras]
    if table:
        rows = "".join(
            f'<tr><td style="padding:10px 14px;font-size:14px;color:{MUTED};border-bottom:1px solid {RULE};width:40%;">{esc(k)}</td>'
            f'<td style="padding:10px 14px;font-size:14px;color:{INK};font-weight:600;border-bottom:1px solid {RULE};">{esc(v)}</td></tr>'
            for k, v in table)
        body.append(f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
                    f'style="border-collapse:collapse;border:1px solid {RULE};border-radius:6px;margin:4px 0 20px 0;">{rows}</table>')
    if bullets:
        items = "".join(f'<li style="margin:0 0 6px 0;">{esc(b)}</li>' for b in bullets)
        body.append(f'<ul style="margin:0 0 20px 0;padding-left:20px;font-size:15px;line-height:1.6;color:{INK};">{items}</ul>')
    if callout:
        body.append(f'<div style="margin:4px 0 22px 0;padding:14px 16px;background:{PANEL};border-left:4px solid {ACCENT};'
                    f'font-size:15px;line-height:1.5;color:{INK};font-weight:600;">{esc(callout)}</div>')
    body.append(f'<p style="margin:8px 0 0 0;font-size:15px;line-height:1.6;color:{INK};">{esc(closing)}<br>'
                f'<strong>The {BRAND} team</strong><br>'
                f'<span style="color:{MUTED};font-size:13px;">{esc(INBOX)}</span></p>')

    case_line = f"Case {esc(case_id)} &middot; " if case_id else ""
    html_doc = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title></head>
<body style="margin:0;padding:0;background:{PANEL};">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{PANEL};padding:24px 12px;">
<tr><td align="center">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background:#ffffff;border:1px solid {RULE};border-radius:8px;font-family:{FONT};">
<tr><td style="padding:22px 32px;border-bottom:3px solid {ACCENT};">
<div style="font-size:20px;font-weight:700;color:{INK};letter-spacing:0.2px;">{BRAND}</div>
<div style="font-size:12px;color:{MUTED};margin-top:2px;">{esc(TAGLINE)}</div>
</td></tr>
<tr><td style="padding:28px 32px 8px 32px;">
<div style="font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:0.8px;color:{ACCENT};margin-bottom:6px;">{esc(KIND_LABEL.get(kind, "Case update"))}</div>
<h1 style="margin:0 0 20px 0;font-size:22px;line-height:1.3;color:{INK};font-weight:700;">{esc(title)}</h1>
{''.join(body)}
</td></tr>
<tr><td style="padding:20px 32px 24px 32px;border-top:1px solid {RULE};font-size:12px;line-height:1.5;color:{MUTED};">
{case_line}{esc(LABELS_NOTE)}
</td></tr>
</table>
</td></tr></table>
</body></html>"""
    return {"html": html_doc, "text": text}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--file", required=True, help="content JSON (see top of file)")
    ap.add_argument("--preview", help="also write the HTML to this file, for checking")
    a = ap.parse_args()
    with open(a.file, encoding="utf-8") as fh:
        content = json.load(fh)
    out = build(content)
    if a.preview:
        with open(a.preview, "w", encoding="utf-8") as fh:
            fh.write(out["html"])
    json.dump(out, sys.stdout)


if __name__ == "__main__":
    main()
