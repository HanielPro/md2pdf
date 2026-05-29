# md2pdf

Tool to convert Markdown files to PDF using Python.

## Requirements

- Python 3.7+
- Install dependencies:

```bash
python -m venv .venv 
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Usage

### GUI mode

Run without arguments to open the graphical interface:

```bash
python src/main.py
```

### CLI mode

Convert a file (output name inferred from input):

```bash
python src/main.py data/report.md
```

Specify output file explicitly:

```bash
python src/main.py data/report.md output.pdf
```

Include a custom CSS file:

```bash
python src/main.py data/report.md --css mystyle.css
```

Quiet mode:

```bash
python src/main.py data/report.md -q
```

## Building the executable

Requires [PyInstaller](https://pyinstaller.org):

```bash
pip install pyinstaller
```

Then build a single `.exe`:

```bash
pyinstaller --onefile --windowed --name espasmo --collect-all xhtml2pdf --collect-all reportlab src/main.py
```

The executable will be at `dist/espasmo.exe`.

| Flag | Description |
|---|---|
| `--onefile` | Bundles everything into a single `.exe` |
| `--windowed` | Suppresses the console window when using the GUI |
| `--collect-all xhtml2pdf` | Includes internal fonts and CSS from xhtml2pdf |
| `--collect-all reportlab` | Includes ReportLab font data required by xhtml2pdf |

### Running the executable

```bash
dist\md2pdf.exe                  # opens the GUI
dist\md2pdf.exe data\report.md   # CLI mode
```

## Notes

- Relative image paths in the Markdown are resolved relative to the Markdown file location.
- Images are auto-scaled to fit A4 width (655 px at 96 dpi).
- If PDF fonts or styling look off, try a custom CSS with web-safe or embedded fonts.
