# Setup guide (Windows + VS Code + Git)

## 1. Install prerequisites
- Python 3.11+ (tick "Add python.exe to PATH"): https://www.python.org/downloads/
- Git: https://git-scm.com/downloads
- VS Code with the **Python** extension: https://code.visualstudio.com/

## 2. Open the project
Unzip, then in a terminal:
```powershell
cd path\to\SmartDashcams-main
code .
```

## 3. Create the environment (VS Code terminal: Ctrl + `)
```powershell
copy .env.example .env
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```
If activation is blocked: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.
macOS/Linux: `source .venv/bin/activate`.

Pick the interpreter: Ctrl+Shift+P -> "Python: Select Interpreter" -> `.venv`.

## 4. Run
```powershell
uvicorn app.main:app --reload
```
Open http://localhost:8000 and log in with `admin` / `ChangeMe123!`
(or press F5 in VS Code to run with the debugger).

## 5. Test
```powershell
pytest -q
```

## 6. Make it your own Git repo
```powershell
git init -b main
git add .
git commit -m "Initial commit: SmartDashcams"
```
Then create an empty repo on GitHub (no README) and connect it:
```powershell
git remote add origin https://github.com/<your-username>/SmartDashcams.git
git push -u origin main
```
`.env` and `*.db` are already git-ignored, so secrets and the local database are not committed.
