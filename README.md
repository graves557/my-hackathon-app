# Bathroom Tracker

## Local development

1. Create and activate a Python virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Install dependencies:

```powershell
pip install -r requirements.txt
```

3. Run the app directly:

```powershell
python api/index.py
```

4. Open the API:

- `http://127.0.0.1:8000/api/status`
- `http://127.0.0.1:8000/`

## Vercel local development

If `vercel dev` fails with a Python runtime error, make sure the virtual environment is activated and the correct Python version is available.

```powershell
.\.venv\Scripts\Activate.ps1
vercel dev
```

If you are on Windows and `python3` is not available, use the standard `python` command or disable the Windows App Execution Alias for `python3`.
