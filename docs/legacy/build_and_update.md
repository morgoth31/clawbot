# Build and Update Guide

## Getting Started

The project comes with a helper script that installs the necessary dependencies and starts a local web server to preview documentation changes live.

```bash
chmod +x generate_docs.sh
./generate_docs.sh
```

## Adding New Code Documentation

If you create a new Python module in `ros2_llm_bridge/ros2_llm_bridge/`, you must explicitly add it to the `docs/api.md` file to instruct MkDocs to extract its docstrings.

Simply append a block like this to `docs/api.md`:

```markdown
## My New Module (`my_new_module.py`)

::: ros2_llm_bridge.my_new_module
    options:
      show_root_heading: true
      show_source: true
```

## Writing Docstrings

This project uses the **Google Docstring Style**. This style is required for `mkdocstrings` to parse your arguments, return types, and exceptions accurately.

### Example

```python
def example_function(param_one: int, param_two: str) -> bool:
    """This is a summary of the function.

    This function does XYZ based on the parameters provided.

    Args:
        param_one: The first parameter describing an integer ID.
        param_two: A descriptive string setting the mode.

    Returns:
        True if successful, False otherwise.

    Raises:
        ValueError: If `param_one` is less than 0.
    """
    pass
```

## Building a Static Site

If you wish to export the documentation to HTML (for example, to serve on GitHub Pages), run:

```bash
mkdocs build --strict
```

The static files will be placed into the `site/` directory by default.
