import ast
import os
import sys

stdlib = sys.stdlib_module_names if hasattr(sys, 'stdlib_module_names') else set() # python 3.10+
project_modules = {'attendance', 'portal', 'attendance_core', 'scripts'}

imports = set()

def get_imports(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read(), filename=filepath)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name.split('.')[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module.split('.')[0])
    except Exception as e:
        pass

for root, dirs, files in os.walk(r'd:\dev\attendance_core'):
    if 'venv' in root or '.git' in root or '__pycache__' in root:
        continue
    for file in files:
        if file.endswith('.py'):
            get_imports(os.path.join(root, file))

external_imports = {m for m in imports if m not in stdlib and m not in project_modules}
print("External modules found:")
for m in sorted(external_imports):
    print(m)
