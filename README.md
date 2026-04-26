# Basketball Grader Wizard

> This project ingests weekly basketball results in xls format and coverts it into actionable recommendations for grading of basketball teams for boys and girls across multiple age levels it should be in a dashboard and have tables it should assess the data every week and provide recommendations for which teams show move up or go down a grade based on fairness this should be a profressional looking app and it is ok to to search the public internat for similar applications it should be feature rich

## Quick Start

1. **Open in VS Code** — The `.venv` activates automatically.

2. **Install dependencies** (first time only):
   ```powershell
   python -m venv .venv
   .venv\Scripts\Activate.ps1
   pip install -e ".[dev]"
   ```

3. **Configure environment**:
   ```powershell
   copy .env.example .env
   # Edit .env with your credentials
   ```

4. **Run the app**:
   ```powershell
   streamlit run src/app.py
   ```

## Project Structure

```
Basketball Grader Wizard/
├── .vscode/          # VS Code settings (auto-venv)
├── .github/          # Copilot instructions
├── config/           # Settings module
│   ├── __init__.py
│   └── settings.py
├── src/              # Application source
│   ├── app.py        # Main Streamlit app
│   └── styles.py     # Ford Blue theme CSS
├── tests/            # Pytest tests
├── data/             # Local data (gitignored)
├── assets/           # Logos, icons
├── .env.example      # Template for secrets
├── pyproject.toml    # Project metadata
└── README.md
```

## Development

Run tests:
```powershell
pytest
```

Format code:
```powershell
ruff check --fix .
ruff format .
```

## Author

avankral
