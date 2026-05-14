"""Shared HTML + render helpers for PDF templates."""
from __future__ import annotations

from PySide6.QtGui import QTextDocument
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtWidgets import QFileDialog, QWidget


CSS = """
<style>
  body { font-family: 'Inter', sans-serif; color: #1e1b15; font-size: 11pt; }
  h1 { font-family: 'Fraunces', serif; font-size: 24pt; margin: 0 0 4pt; color: #13110c; }
  h2 { font-family: 'Fraunces', serif; font-size: 16pt; margin: 16pt 0 6pt; color: #1e1b15; }
  .eyebrow { font-size: 9pt; color: #6f6757; letter-spacing: 1.5pt; text-transform: uppercase; }
  .wordmark { font-family: 'Fraunces', serif; font-size: 12pt; color: #4a4538; }
  .footer { font-size: 8pt; color: #a89e89; text-align: center; margin-top: 24pt; }
  .question { margin-bottom: 14pt; }
  .question .num { font-weight: 600; color: #4a4538; }
  table { border-collapse: collapse; width: 100%; }
  th, td { padding: 4pt 8pt; border-bottom: 1px solid #ebe3d5; text-align: left; }
  th { color: #6f6757; font-size: 9pt; font-weight: 500; }
  .answer-line { display: inline-block; border-bottom: 1px solid #4a4538; height: 18pt; min-width: 200pt; }
  .option-bullet { font-size: 14pt; vertical-align: middle; }
</style>
"""


def html_header(title: str) -> str:
    """Returns the opening <html><head>...</head><body><wordmark><h1>title</h1>."""
    return (
        f"<html><head><meta charset='utf-8'/>{CSS}</head><body>"
        f"<div class='wordmark'>Learning Buddy</div>"
        f"<h1>{title}</h1>"
    )


def html_footer() -> str:
    return "<div class='footer'>designed by Matthias</div></body></html>"


def render_to_pdf(html: str, output_path: str) -> None:
    """Render an HTML string to a PDF at output_path."""
    document = QTextDocument()
    document.setHtml(html)
    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    printer.setOutputFileName(output_path)
    document.print_(printer)


def render_to_bytes(html: str) -> bytes:
    """Render an HTML string to PDF bytes (in-memory via temp file)."""
    import os as _os
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        render_to_pdf(html, tmp_path)
        with open(tmp_path, "rb") as f:
            return f.read()
    finally:
        _os.unlink(tmp_path)


def save_pdf_with_dialog(
    parent: QWidget, html: str, default_filename: str,
) -> bool:
    """Open a save dialog and render the PDF on confirm. Returns True on success."""
    path, _ = QFileDialog.getSaveFileName(
        parent, "PDF speichern", default_filename, "PDF (*.pdf)",
    )
    if not path:
        return False
    if not path.lower().endswith(".pdf"):
        path += ".pdf"
    render_to_pdf(html, path)
    return True
