
import argparse
import json
from .adapter import prompt, run_tool

def main():
    parser = argparse.ArgumentParser(description="WWML YouTube editorial adapter")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("prompt")
    p.add_argument("skill")
    p.add_argument("--brief", default="")
    p = sub.add_parser("tool")
    p.add_argument("name")
    p.add_argument("args", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.command == "prompt":
        print(prompt(args.skill, args.brief))
    else:
        print(json.dumps(run_tool(args.name, args.args), indent=2))

if __name__ == "__main__":
    main()
