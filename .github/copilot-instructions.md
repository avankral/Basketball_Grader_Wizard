# Copilot Instructions — Basketball Grader Wizard

## Project Purpose

This project ingests weekly basketball results in xls format and coverts it into actionable recommendations for grading of basketball teams for boys and girls across multiple age levels it should be in a dashboard and have tables it should assess the data every week and provide recommendations for which teams show move up or go down a grade based on fairness this should be a profressional looking app and it is ok to to search the public internat for similar applications it should be feature rich

## Technologies

- **Streamlit** web application framework
- **Parquet** data format for efficient storage

## Code Style

- Type hints on **all** public function signatures
- Google-style docstrings for all public functions and classes
- `pathlib.Path` over `os.path` for all file operations
- Context managers (`with` statements) for I/O
- f-strings for string formatting; no `.format()` or `%`
- Maximum line length: 100 characters
- Specific exception types — never bare `except:`
- Defensive: validate inputs, handle missing keys gracefully

## Security

- **Never** hardcode credentials or API keys
- All secrets via `.env` + `python-dotenv`
- Log errors without exposing sensitive information
- Validate and sanitise all user inputs

## Data I/O

- **Parquet over CSV** — use `pyarrow` engine for all read/write
- Column dtypes should match schema definitions
- Never use `infer_datetime_format`; specify formats explicitly

## UI Styling (Streamlit)

Shared blue theme — inject via `st.markdown(unsafe_allow_html=True)`:

| Colour         | Hex       | Usage                  |
| -------------- | --------- | ---------------------- |
| Primary Blue   | `#00095B` | Headers, buttons       |
| Accent Blue    | `#1C69D4` | Subheaders, hover      |
| Light Blue     | `#E8F1FC` | Info boxes, table rows |
| Light Gray     | `#F5F5F5` | Sidebar background     |
| Success        | `#198754` | Success alerts         |
| Warning        | `#FFC107` | Warning alerts         |
| Error          | `#DC3545` | Error states           |

### Caching Strategy

- `@st.cache_data` — serialisable values (DataFrames, strings). Use `ttl=3600` for remote data.
- `@st.cache_resource` — singletons (OpenAI client, DB connections).
- `st.session_state` — per-user workflow state.

## File Organisation

```
config/       — Settings and configuration
src/          — Application source code
tests/        — Unit and integration tests
data/         — Local data files (gitignored)
assets/       — Static assets (logos, icons)
```
