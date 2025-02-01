# Makefile for packaging and publishing a Python package

# Mark targets as phony so that they run even if files with these names exist.
.PHONY: package publish clean

# The 'package' target builds both a source distribution and a wheel.
package: clean
	@echo "Building the package..."
	python -m build

# The 'publish' target depends on 'package' so it always builds the package first.
publish: package
	@echo "Publishing to PyPi..."
	twine upload dist/*

# The 'clean' target removes previous build artifacts.
clean:
	@echo "Cleaning previous builds..."
	rm -rf build dist *.egg-info