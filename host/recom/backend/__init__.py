import os
import glob
import importlib.util
import inspect

from recom.backend.backend import RecomBackend

# Get the current directory
current_dir = os.path.dirname(__file__)

# Find all Python files in the directory except for __init__.py
py_files = [f for f in glob.glob(os.path.join(current_dir, "*.py")) if not f.endswith('__init__.py')]

backends = []

# Loop through each Python file
for py_file in py_files:
    # Get the module name
    module_name = os.path.splitext(os.path.basename(py_file))[0]

    # Import the module dynamically
    spec = importlib.util.spec_from_file_location(module_name, py_file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    # Find subclasses of RecomBackend and add them to a list
    for name, obj in inspect.getmembers(module):
        if inspect.isclass(obj) and issubclass(obj, RecomBackend) and obj != RecomBackend:
            backends.append(obj)
