"""BriefMinion command line interface.

Usage:
    briefminion brief "Cortensor Mainnet Full Alpha"
    briefminion brief "quantum computing" --max-sources 3 --yes
    briefminion ask "What did the brief say about latency?" --topic "quantum computing"

The model provider comes from your OpenMinion config (see README):
    openminion setup --provider cortensor-portal --model oss-20b --no-chat
or any other configured provider, selected with --agent / --model.
"""

from __future__ import annotations

import argparse
import sys

from openminion import ProviderError, TurnTimeoutError

from .agent import run_ask, run_brief


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="briefminion",
        description="Research-brief agent on the OpenMinion 0.1 Python SDK.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    brief = subparsers.add_parser("brief", help="Research a topic and save a brief.")
    brief.add_argument("topic", help="Topic to research")
    brief.add_argument("--agent", default=None, help="Configured OpenMinion agent id")
    brief.add_argument("--model", default=None, help="Model id override")
    brief.add_argument("--out-dir", default="briefs", help="Output directory")
    brief.add_argument("--max-sources", type=int, default=4)
    brief.add_argument(
        "--yes",
        action="store_true",
        help="Auto-approve the save step (no interactive prompt)",
    )

    ask = subparsers.add_parser("ask", help="Ask a follow-up about a saved brief.")
    ask.add_argument("question", help="Follow-up question")
    ask.add_argument("--topic", required=True, help="Topic of the brief to ask about")
    ask.add_argument("--agent", default=None, help="Configured OpenMinion agent id")
    ask.add_argument("--model", default=None, help="Model id override")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "brief":
            record = run_brief(
                topic=args.topic,
                agent_id=args.agent,
                model=args.model,
                out_dir=args.out_dir,
                max_sources=args.max_sources,
                auto_approve=args.yes,
            )
            print(f"Brief saved: {record['saved_path']}")
            print(f"Title: {record['brief_title']}")
            print(f"Articles: {record['articles_fetched']}")
            print(f"Time: {record['total_seconds']}s")
            if record["fallbacks"]:
                print(f"Fallbacks used: {', '.join(record['fallbacks'])}")
            print(f"Run log: {record['run_log_path']}")
            return 0
        answer = run_ask(
            question=args.question,
            topic=args.topic,
            agent_id=args.agent,
            model=args.model,
        )
        print(answer)
        return 0
    except ProviderError as exc:
        print(f"provider failed: {exc.code}: {exc.message}", file=sys.stderr)
        return 1
    except TurnTimeoutError as exc:
        print(f"turn timed out: {exc}", file=sys.stderr)
        return 1
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
