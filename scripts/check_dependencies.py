from __future__ import annotations

import importlib.util
import sys


REQUIRED_IMPORTS = {
    "deepagents": "deepagents",
    "langchain_core": "langchain-core",
    "langchain_mcp_adapters": "langchain-mcp-adapters",
    "langchain_openai": "langchain-openai",
    "mcp": "mcp",
    "requests": "requests",
}


def main() -> None:
    missing = []
    print(f"Python: {sys.executable}")
    for module_name, package_name in REQUIRED_IMPORTS.items():
        found = importlib.util.find_spec(module_name) is not None
        print(f"{module_name}: {'ok' if found else 'missing'}")
        if not found:
            missing.append(package_name)

    if missing:
        print("\nMissing packages:")
        for package_name in missing:
            print(f"- {package_name}")
        print("\nInstall with:")
        print("python -m pip install -r requirements.txt")
        raise SystemExit(1)

    print("\nAll required agent dependencies are installed.")


if __name__ == "__main__":
    main()
