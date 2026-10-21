"""Command line entry point.

  python -m isu_agent.cli generate                 # build the mock IS-U database
  python -m isu_agent.cli accounts                 # list demo accounts and their questions
  python -m isu_agent.cli ask 100000000013 "Why is the latest bill so high?"
  python -m isu_agent.cli eval                     # accuracy against ground truth
"""
from __future__ import annotations

import argparse
import json

from . import config


def main():
    p = argparse.ArgumentParser(prog="isu-agent")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("generate")
    sub.add_parser("accounts")
    a = sub.add_parser("ask")
    a.add_argument("vkont")
    a.add_argument("question", nargs="?", default="Why is the latest bill unusual?")
    a.add_argument("--belnr")
    a.add_argument("--show-tools", action="store_true")
    e = sub.add_parser("eval")
    e.add_argument("--llm", action="store_true", help="Evaluate the LLM agent instead of the rule engine")
    x = sub.add_parser("export-abap", help="Generate an ABAP class that loads the mock data on BTP")
    x.add_argument("--accounts", type=int, default=16)
    args = p.parse_args()

    if args.cmd == "generate":
        from .mockdata import generate
        print(generate())
    elif args.cmd == "accounts":
        for g in json.loads(config.GROUND_TRUTH_PATH.read_text()):
            print(f'{g["vkont"]}  {g["name"]:<22} {g["scenario"]:<18} bill {g["focus_belnr"]}  "{g["question"]}"')
    elif args.cmd == "ask":
        from .agent import BillAgent
        from .repository import get_repository
        res = BillAgent(get_repository()).ask(args.question, args.vkont, args.belnr)
        print(res.answer)
        if res.proposed_cases:
            print("\n[Proposed clarification case - awaiting approval]")
            for c in res.proposed_cases:
                print(f'  {c["category"]}: {c["summary"]}')
        if args.show_tools:
            print(f"\n[mode: {res.mode}]")
            for c in res.tool_calls:
                print("  tool:", c["tool"], c["input"])
    elif args.cmd == "eval":
        from .evaluate import run_eval
        run_eval(use_llm=args.llm)
    elif args.cmd == "export-abap":
        from .export_abap import export
        print(export(args.accounts))


if __name__ == "__main__":
    main()
