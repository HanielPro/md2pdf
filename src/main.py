"""
Markdown to PDF converter.

Provides both a command-line interface and a :mod:`tkinter` GUI.
Run without arguments to open the GUI; pass a file path for CLI mode.
"""

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Optional

import markdown
from xhtml2pdf import pisa

try:
    from PIL import Image as _PILImage
    _HAS_PIL = True
except ImportError:
    _HAS_PIL = False

# A4 (8.27in) minus 2×0.7in margins = 6.87in × 96dpi ≈ 659px
_MAX_IMG_PX = 655

DEFAULT_CSS: str = """
<style>
body { font-family: DejaVu Sans, Arial, sans-serif; margin: 0.7in; line-height: 1.25; }
p { margin: 0 0 0.35em 0; }
h1, h2, h3, h4, h5, h6 { margin: 0 0 0.25em 0; }
ul, ol { margin: 0 0 0.5em 1.2em; padding: 0; }
li { margin: 0.12em 0; }
table { border-collapse: collapse; width: 100%; }
table, th, td { border: 1px solid #ccc; padding: 6px; }
pre, code { background: #f6f8fa; padding: 6px; font-family: monospace; font-size: 0.9em; white-space: pre-wrap; }
.figure { page-break-inside: avoid; break-inside: avoid; text-align: center; margin: 0.4em 0; }
img { page-break-inside: avoid; }
div, section { margin: 0; padding: 0; }
</style>
"""


def _open_file(path: Path) -> None:
    """Open *path* with the system default application.

    Uses :func:`os.startfile` on Windows, ``open`` on macOS, and
    ``xdg-open`` on Linux.

    :param path: File to open.
    :type path: ~pathlib.Path
    """
    import subprocess

    if sys.platform == "win32":
        os.startfile(str(path))
    elif sys.platform == "darwin":
        subprocess.run(["open", str(path)], check=False)
    else:
        subprocess.run(["xdg-open", str(path)], check=False)


def _make_figure(img_tag: str, base_dir: Path) -> str:
    """Wrap an ``<img>`` tag in a centred figure ``<div>`` with explicit pixel dimensions.

    :func:`xhtml2pdf` ignores ``max-width`` and mishandles percentage widths, so
    Pillow is used to read the natural image size and emit an inline
    ``style="width:Xpx;height:Ypx;"`` capped at :data:`_MAX_IMG_PX`.  When
    Pillow is unavailable or the source is a URL / data URI the tag is wrapped
    as-is.

    :param img_tag: Raw ``<img …>`` HTML string produced by the Markdown renderer.
    :type img_tag: str
    :param base_dir: Directory of the source Markdown file, used to resolve
        relative image paths.
    :type base_dir: ~pathlib.Path
    :returns: An HTML ``<div class="figure">`` element containing the
        (possibly resized) image tag.
    :rtype: str
    """
    if _HAS_PIL:
        src_match = re.search(r'\bsrc=["\']([^"\']+)["\']', img_tag, re.IGNORECASE)
        if src_match:
            src = src_match.group(1)
            if not src.startswith(('data:', 'http:', 'https:')):
                img_path = Path(src) if Path(src).is_absolute() else base_dir / src
                try:
                    with _PILImage.open(img_path) as pil_img:
                        orig_w, orig_h = pil_img.size
                        if orig_w > _MAX_IMG_PX:
                            w = _MAX_IMG_PX
                            h = int(orig_h * _MAX_IMG_PX / orig_w)
                        else:
                            w, h = orig_w, orig_h
                        img_tag = re.sub(
                            r'\s*(?:style=["\'][^"\']*["\'])?\s*/?>$',
                            f' style="width:{w}px;height:{h}px;" />',
                            img_tag.rstrip(),
                        )
                except Exception:
                    pass
    return f'<div class="figure">{img_tag}</div>'


def md_to_pdf(
    md_path: "str | Path",
    pdf_path: "Optional[str | Path]" = None,
    css_content: Optional[str] = None,
    quiet: bool = False,
) -> bool:
    """Convert a Markdown file to PDF.

    :param md_path: Path to the source ``.md`` file.
    :type md_path: str or ~pathlib.Path
    :param pdf_path: Destination path for the generated PDF.  Defaults to the
        same directory and stem as *md_path* with a ``.pdf`` extension.
    :type pdf_path: str or ~pathlib.Path, optional
    :param css_content: Raw ``<style>…</style>`` block injected into the HTML
        ``<head>``.  Defaults to :data:`DEFAULT_CSS` when ``None``.
    :type css_content: str, optional
    :param quiet: Suppress all console output when ``True``.
    :type quiet: bool
    :returns: ``True`` on success, ``False`` when ``xhtml2pdf`` reports errors.
    :rtype: bool
    :raises FileNotFoundError: If *md_path* does not exist.
    """
    md_path = Path(md_path)
    if not md_path.exists():
        raise FileNotFoundError(f"Markdown file not found: {md_path}")

    pdf_path = (
        Path(pdf_path).resolve() if pdf_path is not None
        else md_path.with_suffix('.pdf').resolve()
    )

    text = md_path.read_text(encoding='utf-8')
    html_body = markdown.markdown(
        text, extensions=["fenced_code", "tables", "toc", "attr_list"]
    )

    base_dir = md_path.parent

    def _wrap_figure(m: re.Match) -> str:
        return _make_figure(m.group(1), base_dir)

    # Wrap <p><img></p> -> figure div
    html_body = re.sub(
        r"<p>\s*(<img [^>]+/?>)\s*</p>", _wrap_figure, html_body, flags=re.IGNORECASE
    )
    # Wrap remaining bare <img> not already inside a figure div (15-char fixed lookbehind)
    html_body = re.sub(
        r'(?<!class="figure">)(<img [^>]+/?>)', _wrap_figure, html_body, flags=re.IGNORECASE
    )

    css = css_content if css_content is not None else DEFAULT_CSS
    html = f'<html><head><meta charset="utf-8">{css}</head><body>{html_body}</body></html>'

    old_cwd = Path.cwd()
    try:
        os.chdir(md_path.parent)
        with open(str(pdf_path), "wb") as pdf_file:
            pisa_status = pisa.CreatePDF(html, dest=pdf_file)
        if pisa_status.err:
            if not quiet:
                print("Conversion completed with errors.")
            return False
        if not quiet:
            print(f"PDF created: {pdf_path}")
        return True
    finally:
        os.chdir(old_cwd)


class ConverterApp:
    """Tkinter GUI application for Markdown-to-PDF conversion.

    Presents a form with:

    * **Row 0** — file-picker for the source ``.md`` file.
    * **Row 1** — text entry for the output PDF name.
    * **Row 2** — folder-picker for the output directory.
    * **Row 3** — *Convert* button.
    * **Row 4** — status label (grey / green / orange / red).

    On success the generated PDF is opened automatically with the system
    default viewer via :func:`_open_file`.

    Usage::

        ConverterApp().run()
    """

    _PAD = {"padx": 10, "pady": 6}

    def __init__(self) -> None:
        """Initialise the root window and build all widgets."""
        import tkinter as tk

        self._tk = tk
        self.root = tk.Tk()
        self.root.title("Markdown to PDF")
        self.root.resizable(False, False)

        self.input_var = tk.StringVar()
        self.output_var = tk.StringVar()
        self.folder_var = tk.StringVar()
        self.status_var = tk.StringVar()

        self._build_ui()

    def _build_ui(self) -> None:
        """Create and grid all widgets onto :attr:`root`."""
        tk = self._tk
        pad = self._PAD

        tk.Label(self.root, text="Markdown file:").grid(row=0, column=0, sticky="w", **pad)
        tk.Entry(self.root, textvariable=self.input_var, width=45).grid(row=0, column=1, **pad)
        tk.Button(self.root, text="Browse…", command=self._browse_input).grid(
            row=0, column=2, **pad
        )

        tk.Label(self.root, text="Output PDF name:").grid(row=1, column=0, sticky="w", **pad)
        tk.Entry(self.root, textvariable=self.output_var, width=45).grid(row=1, column=1, **pad)
        tk.Label(self.root, text="(no extension needed)").grid(
            row=1, column=2, sticky="w", padx=4
        )

        tk.Label(self.root, text="Save to folder:").grid(row=2, column=0, sticky="w", **pad)
        tk.Entry(self.root, textvariable=self.folder_var, width=45).grid(row=2, column=1, **pad)
        tk.Button(self.root, text="Browse…", command=self._browse_folder).grid(
            row=2, column=2, **pad
        )

        tk.Button(self.root, text="Convert to PDF", command=self._convert, width=20).grid(
            row=3, column=0, columnspan=3, pady=(4, 8)
        )

        self._status_label = tk.Label(
            self.root, textvariable=self.status_var, fg="gray", wraplength=400
        )
        self._status_label.grid(row=4, column=0, columnspan=3, **pad)

    def _browse_input(self) -> None:
        """Open a file-picker dialog and populate :attr:`input_var`.

        Also pre-fills :attr:`output_var` with the selected file's stem and
        :attr:`folder_var` with the file's parent directory when those fields
        are still empty.
        """
        from tkinter import filedialog

        path = filedialog.askopenfilename(
            title="Select Markdown file",
            filetypes=[("Markdown files", "*.md *.markdown"), ("All files", "*.*")],
        )
        if path:
            self.input_var.set(path)
            if not self.output_var.get():
                self.output_var.set(Path(path).stem)
            if not self.folder_var.get():
                self.folder_var.set(str(Path(path).parent))

    def _browse_folder(self) -> None:
        """Open a directory-picker dialog and populate :attr:`folder_var`.

        The dialog opens in the current :attr:`folder_var` value, falling back
        to the source file's directory or the current working directory.
        """
        from tkinter import filedialog

        initial = (
            self.folder_var.get()
            or (str(Path(self.input_var.get()).parent) if self.input_var.get() else ".")
        )
        folder = filedialog.askdirectory(title="Select output folder", initialdir=initial)
        if folder:
            self.folder_var.set(folder)

    def _convert(self) -> None:
        """Validate form fields, call :func:`md_to_pdf`, and open the result.

        The PDF is saved to :attr:`folder_var` (falling back to the source
        file's directory when the field is empty).  On success the file is
        opened with the system default PDF viewer via :func:`_open_file`.

        Updates :attr:`_status_label` with the result colour and message:

        * **green** — conversion succeeded.
        * **orange** — ``xhtml2pdf`` finished with non-fatal errors.
        * **red** — an exception was raised.
        """
        from tkinter import messagebox

        md_path_str = self.input_var.get().strip()
        out_name = self.output_var.get().strip()

        if not md_path_str:
            messagebox.showerror("Missing input", "Please select a Markdown file.")
            return
        if not out_name:
            messagebox.showerror("Missing name", "Please enter a name for the output PDF.")
            return

        md_path = Path(md_path_str)
        folder_str = self.folder_var.get().strip()
        out_dir = Path(folder_str) if folder_str else md_path.parent

        if not out_name.lower().endswith(".pdf"):
            out_name += ".pdf"
        pdf_path = out_dir / out_name

        self._status_label.config(fg="gray")
        self.status_var.set("Converting…")
        self.root.update_idletasks()

        try:
            success = md_to_pdf(md_path, pdf_path, quiet=True)
            if success:
                self._status_label.config(fg="green")
                self.status_var.set(f"Done: {pdf_path}")
                _open_file(pdf_path)
            else:
                self._status_label.config(fg="orange")
                self.status_var.set("Conversion completed with errors.")
        except Exception as exc:
            self._status_label.config(fg="red")
            self.status_var.set(f"Error: {exc}")

    def run(self) -> None:
        """Enter the Tkinter main event loop."""
        self.root.mainloop()


def gui() -> None:
    """Instantiate and run :class:`ConverterApp`.

    :returns: None
    """
    ConverterApp().run()


def main(argv: Optional[list] = None) -> int:
    """Entry point for both GUI and CLI modes.

    Launches the GUI when invoked without arguments; otherwise parses the
    command line with :mod:`argparse`.

    :param argv: Argument list to parse.  Defaults to :data:`sys.argv` when
        ``None``.
    :type argv: list, optional
    :returns: Exit code — ``0`` on success, ``1`` on conversion error,
        ``2`` for a missing CSS file, ``3`` for any other exception.
    :rtype: int
    """
    if argv is None and len(sys.argv) == 1:
        gui()
        return 0

    parser = argparse.ArgumentParser(description="Convert Markdown file to PDF")
    parser.add_argument('input', help='Input markdown file')
    parser.add_argument('output', nargs='?', help='Output PDF file (optional)')
    parser.add_argument('--css', '-c', help='Path to a CSS file to include in the PDF')
    parser.add_argument('--quiet', '-q', action='store_true', help='Silence output')

    args = parser.parse_args(argv)

    css_content = None
    if args.css:
        css_file = Path(args.css)
        if not css_file.exists():
            print(f"CSS file not found: {css_file}")
            return 2
        css_content = css_file.read_text(encoding='utf-8')

    try:
        success = md_to_pdf(args.input, args.output, css_content=css_content, quiet=args.quiet)
        return 0 if success else 1
    except Exception as e:
        print(f"Error: {e}")
        return 3


if __name__ == '__main__':
    sys.exit(main())
