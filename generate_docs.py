import os
import glob
import yaml
from pathlib import Path

def generate_docs():
    base_dir = Path("/home/jetson/clawbot")
    docs_dir = base_dir / "docs"
    api_docs_dir = docs_dir / "api"
    api_docs_dir.mkdir(parents=True, exist_ok=True)
    
    # Exclude directories
    exclude_dirs = {'.venv', 'venv', 'env', 'site', 'docs', '.git', '__pycache__', 'build', 'install', 'log'}
    
    python_files = []
    
    for root, dirs, files in os.walk(base_dir):
        # Filter excluded directories
        dirs[:] = [d for d in dirs if d not in exclude_dirs and not d.startswith('.')]
        
        for file in files:
            if file.endswith(".py"):
                file_path = Path(root) / file
                # Skip __init__.py files
                if file == "__init__.py":
                    continue
                # Get module path relative to base_dir
                rel_path = file_path.relative_to(base_dir)
                module_path = str(rel_path.with_suffix('')).replace(os.path.sep, '.')
                python_files.append((file_path, module_path, rel_path))
                
    api_nav = []
    
    for file_path, module_path, rel_path in sorted(python_files, key=lambda x: x[1]):
        md_file_name = f"{module_path}.md"
        md_file_path = api_docs_dir / md_file_name
        
        # Write markdown file for mkdocstrings
        content = f"# {module_path}\n\n::: {module_path}\n    options:\n      show_root_heading: true\n      show_source: true\n"
        with open(md_file_path, "w") as f:
            f.write(content)
            
        api_nav.append({str(rel_path): f"api/{md_file_name}"})
        
    # Update mkdocs.yml
    mkdocs_file = base_dir / "mkdocs.yml"
    with open(mkdocs_file, "r") as f:
        mkdocs_config = yaml.safe_load(f)
        
    # Ensure paths point to "."
    plugins = mkdocs_config.get("plugins", [])
    for plugin in plugins:
        if isinstance(plugin, dict) and "mkdocstrings" in plugin:
            try:
                plugin["mkdocstrings"]["handlers"]["python"]["paths"] = ["."]
            except KeyError:
                pass
                
    # Update nav
    nav = mkdocs_config.get("nav", [])
    
    # Filter out existing API references to replace them
    new_nav = []
    for item in nav:
        if isinstance(item, dict) and "API Reference" in item:
            continue
        new_nav.append(item)
        
    new_nav.insert(1, {"API Reference": api_nav})
    mkdocs_config["nav"] = new_nav
    
    # Write updated mkdocs.yml
    with open(mkdocs_file, "w") as f:
        yaml.dump(mkdocs_config, f, sort_keys=False, default_flow_style=False)
        
    print(f"Generated docs for {len(python_files)} python files.")

if __name__ == "__main__":
    generate_docs()
