# Basketball Grader Wizard

> This project ingests weekly basketball results in xls format and coverts it into actionable recommendations for grading of basketball teams for boys and girls across multiple age levels it should be in a dashboard and have tables it should assess the data every week and provide recommendations for which teams show move up or go down a grade based on fairness this should be a profressional looking app and it is ok to to search the public internat for similar applications it should be feature rich

## Quick Start

1. **Open in VS Code** — The workspace is configured to use `.venv` automatically.

2. **Create or refresh the virtual environment**:
   ```powershell
   py -3.13 -m venv .venv
   # If Python 3.13 is not installed, use Python 3.12 instead.
   .venv\Scripts\python.exe -m pip install --upgrade pip
   .venv\Scripts\python.exe -m pip install -e ".[dev]"
   ```

   If you copied or moved this project from another folder or machine, recreate `.venv` before
   running the app. Windows virtual environments are not portable.

3. **Configure environment**:
   ```powershell
   copy .env.example .env
   # Edit .env with your credentials
   ```

4. **Run the app**:
   ```powershell
   .venv\Scripts\python.exe -m streamlit run src/app.py
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
│   └── styles.py     # Shared theme CSS
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

