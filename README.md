# Mini SQL Compiler — SQLite edition

This improved version uses a real, persistent SQLite database instead of hardcoded student rows.

## Run on Windows
1. Stop any older version in VS Code with Ctrl+C.
2. Extract this ZIP to a new folder.
3. Double-click `run_windows.bat`, or run `python app.py` in the folder.
4. Open http://127.0.0.1:8000.
5. Add a student using the **Student Database (SQLite)** panel.
6. Run `SELECT name, marks FROM students;` in the SQL editor. The new name will appear.

## What is stored
The app creates `compiler_demo.db` in the project folder on first run. It seeds three sample students only when the students table is empty. Newly added records persist after restarting the app.

## Supported compiler subset
SELECT queries against `students` and `enrollments`, with supported JOIN, WHERE, GROUP BY, and ORDER BY forms. The parser and semantic checks are educational and intentionally limited. The query editor only permits SELECT queries. Add student records through the form.

## Pipeline
Lexer → Parser → Semantic Analyzer → Query Translator → Optimizer → Executor.

The executor runs the validated query against SQLite. The optimizer is a simplified teaching demonstration, not a full cost-based optimizer.

## Sample query buttons
- Sample buttons fill the SQL editor only; they do not run the query automatically.
- Each click on **Simple SELECT** cycles through four different SELECT examples.
- **Test Error** fills `SELECT name FROM missing_students;`, which demonstrates an unknown-table semantic error.
- Click **Compile & Execute** when you are ready to run the loaded query.

## Expanded demonstration controls
- **Simple SELECT** cycles through four valid SQL examples.
- **Filter + Sort**, **JOIN Demo**, and **GROUP BY Demo** load other supported examples.
- **Next Error Example** cycles through unknown table, unknown column, syntax, lexer, and invalid JOIN table examples.
- Error responses now mark the failed pipeline stage as FAIL and later stages as SKIPPED.
- Lexer now correctly ignores whitespace between SQL tokens.
