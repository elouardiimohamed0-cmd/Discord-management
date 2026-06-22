#!/usr/bin/env python3
import os
import py_compile
import sys
​
BAD_CHARS = {
"u200b": "U+200B ZERO WIDTH SPACE",
"u200c": "U+200C ZERO WIDTH NON-JOINER",
"u200d": "U+200D ZERO WIDTH JOINER",
"ufeff": "U+FEFF BOM / ZERO WIDTH NO-BREAK SPACE",
}
SKIP_DIRS = {
".git",
"pycache",
".venv",
"venv",
"env",
".env",
}
def iter_python_files(root="."):
for current_root, dirs, files in os.walk(root):
dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
for filename in files:
if filename.endswith(".py"):
yield os.path.join(current_root, filename)
def check_bad_chars(path):
errors = []
with open(path, "r", encoding="utf-8", errors="replace") as f:
for line_no, line in enumerate(f, 1):
for char, label in BAD_CHARS.items():
if char in line:
errors.append(f"{path}:{line_no}: invalid invisible character {label}")
return errors
def check_compile(path):
try:
py_compile.compile(path, doraise=True)
return []
except py_compile.PyCompileError as e:
return [f"{path}: compile failedn{e.msg}"]
def main():
all_errors = []
files = list(iter_python_files("."))
if not files:
print("No Python files found.")
return 1
print(f"Checking {len(files)} Python files...")
for path in files:
all_errors.extend(check_bad_chars(path))
all_errors.extend(check_compile(path))
if all_errors:
print("nFAILED:n")
for err in all_errors:
print(err)
print("-" * 80)
return 1
print("OK: no invisible characters and all Python files compile.")
return 0
if name == "main":
raise SystemExit(main())
