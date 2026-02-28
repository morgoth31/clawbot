#!/bin/bash
# Install dependencies
pip install mkdocs-material "mkdocstrings[python]"

# Build and serve docs locally
mkdocs serve -a 0.0.0.0:8000
