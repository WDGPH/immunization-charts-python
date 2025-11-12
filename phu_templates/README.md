# PHU Templates Directory

This directory contains Public Health Unit (PHU) specific template customizations.

## Usage

Each PHU should create a subdirectory here with their organization-specific templates:

```
phu_templates/
├── my_phu/
│   ├── en_template.py              (required for English output)
│   ├── fr_template.py              (required for French output)
│   ├── conf.typ                    (required)
│   └── assets/                     (optional - only if templates reference assets)
│       ├── logo.png                (optional)
│       └── signature.png           (optional)
```

## Running with PHU Templates

To use a PHU-specific template, specify the template name with `--template`:

```bash
# Generate English notices
uv run viper students.xlsx en --template my_phu

# Generate French notices
uv run viper students.xlsx fr --template my_phu
```

This will load templates from `phu_templates/my_phu/`.

## Template File Requirements

### Core Requirements (Always Required)

- `conf.typ` - Typst configuration and utility functions

### Language-Specific Requirements (Based on Output Language)

- `en_template.py` - Required only if generating English notices (`--language en`)
  - Must define `render_notice()` function
  - Consulted only when `--language en` is specified
  
- `fr_template.py` - Required only if generating French notices (`--language fr`)
  - Must define `render_notice()` function
  - Consulted only when `--language fr` is specified

**Note:** A PHU may provide templates for only one language. If a user requests a language your template does not support, the pipeline will fail with a clear error message. If you only support one language, only include that template file (e.g., only `en_template.py`).

### Asset Requirements (Based on Template Implementation)

Assets in the `assets/` directory are **optional** and depend entirely on your template implementation:

- `assets/logo.png` - Only required if your `en_template.py` or `fr_template.py` references a logo
- `assets/signature.png` - Only required if your `en_template.py` or `fr_template.py` references a signature
- Other files - Any additional assets (e.g., `assets/header.png`, `assets/seal.pdf`) may be included and referenced in your templates

**Note:** If your template references an asset (e.g., `include "assets/logo.png"` in Typst), that asset **must** exist. The pipeline will fail with a clear error if a referenced asset is missing.

## Creating a PHU Template

If your PHU supports both English and French:

```bash
cp -r templates/ phu_templates/my_phu/
```

Then customize:
- Replace `assets/logo.png` with your PHU logo
- Replace `assets/signature.png` with your signature
- Modify `en_template.py` and `fr_template.py` as needed
- Adjust `conf.typ` for organization-specific styling

### Testing Your Template

```bash
# Test English generation
uv run viper students.xlsx en --template my_phu

# Test French generation (if you provided fr_template.py)
uv run viper students.xlsx fr --template my_phu
```

If a language template is missing:
```
FileNotFoundError: Template module not found: /path/to/phu_templates/my_phu/fr_template.py
Expected fr_template.py in /path/to/phu_templates/my_phu
```

If an asset referenced by your template is missing:
```
FileNotFoundError: Logo not found: /path/to/phu_templates/my_phu/assets/logo.png
```

## Git Considerations

**Important:** PHU-specific templates are excluded from version control via `.gitignore`.

- Templates in this directory will NOT be committed to the main repository
- Each PHU should maintain their templates in their own fork or separate repository
- The `README.md` file and `.gitkeep` are the only tracked files in this directory