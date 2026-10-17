"""`h2t-drawio`: the drawio skill's two functions as a command.

The plugin scripts have no command line; the skill imports `generate_diagram` and
`export_diagram` into a `uv run --with drawpyo python` session. This is the same two calls
with their arguments as flags. `generate` needs the `drawio` extra (drawpyo), imported only
when a diagram is built — `--help` and `export` work on a base install.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path


def _load_graph(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in {".yaml", ".yml"}:
        import yaml

        return yaml.safe_load(text) or {}
    return json.loads(text)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="h2t-drawio", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate", help="write a .drawio file from a graph (JSON or YAML)")
    gen.add_argument("graph", type=Path, help="graph file: nodes, edges, optional containers")
    gen.add_argument("output", help="the .drawio file to write")
    gen.add_argument("--shapes", help="project .drawio-shapes.toml override")
    gen.add_argument("--config", help="project .drawio-skill.yaml override")
    gen.add_argument("--reset", action="store_true",
                     help="overwrite instead of keeping user-moved positions and nodes")

    exp = sub.add_parser("export", help="export a .drawio file through the draw.io Desktop CLI")
    exp.add_argument("drawio", help="the .drawio file")
    exp.add_argument("--format", dest="fmt", default="png", choices=["png", "svg", "pdf"])
    exp.add_argument("--output", help="output path (default: next to the input)")
    exp.add_argument("--config", help="project .drawio-skill.yaml override")
    exp.add_argument("--page", type=int, dest="page_index", help="page index to export")
    exp.add_argument("--all-pages", action="store_true", help="all pages (pdf)")

    shapes = sub.add_parser("shapes", help="list the node types generate knows: the shipped "
                            "library with a project override merged on top")
    shapes.add_argument("--shapes", help="project .drawio-shapes.toml override")
    shapes.add_argument("--json", action="store_true")
    return parser


def _shape_types(shapes_path: str | None) -> dict[str, str]:
    from h2t_ops.tools.drawio.generate import _load_shapes

    library = _load_shapes(shapes_path)
    return {name: library[name].get("baseStyle", "") for name in sorted(library)
            if not name.startswith("_") and name not in ("title", "version")
            and isinstance(library[name], dict)}


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):  # a cp1252 console cannot take every style (#428)
        sys.stdout.reconfigure(encoding="utf-8")
    args = _parser().parse_args(argv)
    if args.command == "shapes":
        types = _shape_types(args.shapes)
        if args.json:
            print(json.dumps(types, ensure_ascii=False))
        else:
            for name, style in types.items():
                print(f"  {name}: {style}")
        return 0
    if args.command == "generate":
        if importlib.util.find_spec("drawpyo") is None:  # the remedy beats an ImportError
            from h2t_ops.setup import hints
            print("h2t-drawio generate needs drawpyo, the drawio extra of h2t-ops. Add it: "
                  f"{hints.add_extra('drawio')}", file=sys.stderr)
            return 3
        from h2t_ops.tools.drawio.generate import generate_diagram

        path = generate_diagram(_load_graph(args.graph), args.output,
                                preserve_user_edits=not args.reset,
                                shapes_path=args.shapes, config_path=args.config)
    else:
        from h2t_ops.tools.drawio.export import export_diagram

        path = export_diagram(args.drawio, fmt=args.fmt, output_path=args.output,
                              config_path=args.config, page_index=args.page_index,
                              all_pages=args.all_pages)
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
