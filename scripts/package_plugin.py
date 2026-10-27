"""Build a self-contained .mfp without runtime files or credentials."""

import json
from pathlib import Path
import zipfile


def main() -> None:
    """Archive plugin sources, vendored engine and license for MoFox loading."""
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    output = root / "releases" / f"{manifest['name']}-{manifest['version']}.mfp"
    output.parent.mkdir(exist_ok=True)
    excluded = {"releases", "__pycache__", ".pytest_cache", "node_modules", ".git"}
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(root.rglob("*")):
            relative = path.relative_to(root)
            if (
                path.is_file()
                and not excluded.intersection(relative.parts)
                and path.suffix not in {".pyc", ".pyo"}
            ):
                archive.write(path, relative.as_posix())
    print(output)


if __name__ == "__main__":
    main()
