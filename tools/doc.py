""" Just a simple script to generate documentation for the command types we make available"""
from __future__ import annotations
from common.models import Command
from common.constants import get_project_root
from pydantic import BaseModel, TypeAdapter

import json
import sys
import subprocess
import webbrowser
import argparse
from pathlib import Path
from typing import (
    Annotated,
    Union,
    get_args,
    get_origin)

# with this we don't have to manually import every single *Cmd type, we can just
# walk the Command type definition and retrieve the types that comprise it.
# Annotated[Union[...]], Field(discriminator="command")


def unwrap_union(tp):
    """Retrieve the actual *Cmd types, that comprise our Command union type"""
    while get_origin(tp) is Annotated:
        tp = get_args(tp)[0]
    if get_origin(tp) is Union:
        return get_args(tp)
    return (tp,)


def make_out_dir(arg_path: str) -> Path:
    p = Path(arg_path)
    if not p.is_absolute():
        p = get_project_root() / p
    p.mkdir(parents=True, exist_ok=True)
    return p.resolve()


def render(json_in: Path,
           html_out: Path) -> None:
    try:
        subprocess.run(["generate-schema-doc", str(json_in), str(html_out)], check=False)
    except Exception as exc:
        print(f"{exc}", file=sys.stderr)


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate Command schemas + docs")
    ap.add_argument("-s", "--out-schemas", default="docs/schemas",
                    help="Output dir for JSON Schemas")
    ap.add_argument("-H", "--out-html", default="docs/html",
                    help="Output dir for HTML docs")
    ap.add_argument("-o", "--open", action="store_true",
                    help="Open the generated HTML")
    args = ap.parse_args()

    out_schema_dir = make_out_dir(args.out_schemas)
    out_html_dir = make_out_dir(args.out_html)

    out_schema_dir.mkdir(parents=True, exist_ok=True)
    out_html_dir.mkdir(parents=True, exist_ok=True)

    union_schema = TypeAdapter(Command).json_schema()
    cmd_schema_path = out_schema_dir / "Command.schema.json"
    cmd_schema_path.write_text(json.dumps(union_schema, indent=2, ensure_ascii=False), encoding="utf-8")

    cmd_types = [t for t in unwrap_union(Command) if isinstance(t, type) and issubclass(t, BaseModel)]
    for cls in cmd_types:
        path = out_schema_dir / f"{cls.__name__}.schema.json"
        path.write_text(json.dumps(cls.model_json_schema(), indent=2, ensure_ascii=False), encoding="utf-8")

    command_html = out_html_dir / "Command.html"
    render(cmd_schema_path, command_html)
    for cls in cmd_types:
        render(out_schema_dir / f"{cls.__name__}.schema.json", out_html_dir / f"{cls.__name__}.html")

    print(f"Wrote JSON Schemas to: {out_schema_dir}")
    print(f"Wrote HTML docs to   : {out_html_dir}")

    if args.open and command_html.exists():
        print("Opening docs")
        try:
            webbrowser.open_new_tab(command_html.as_uri())
            print(f"Opened {command_html}")
        except Exception as e:
            print(f"Could not open browser automatically: {e}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
