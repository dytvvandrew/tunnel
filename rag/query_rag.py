from __future__ import annotations

import argparse
import json

from rag_core import retrieve_for_prompt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("question")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    payload = retrieve_for_prompt(args.question, top_k=args.top_k)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    print(payload.get("context") or "未检索到相关资料。")
    if payload.get("sources"):
        print("\n资料来源：")
        for source in payload["sources"]:
            print(f"- [{source['rank']}] {source['source']} score={source['score']}")


if __name__ == "__main__":
    main()

