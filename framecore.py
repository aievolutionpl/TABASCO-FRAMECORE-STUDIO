#!/usr/bin/env python3
"""TABASCO FRAMECORE STUDIO entry point."""
import argparse
import json
from framecore.store import Store


def main():
    parser = argparse.ArgumentParser(description="TABASCO FRAMECORE STUDIO")
    parser.add_argument("command", choices=["editor", "mcp", "projects", "sample"], nargs="?", default="editor")
    parser.add_argument("--port", type=int, default=8877)
    parser.add_argument("--root", help="Katalog projektów (taki sam dla edytora i MCP)")
    examples = parser.add_mutually_exclusive_group()
    examples.add_argument("--creator-pack", action="store_true", help="Utwórz przykład z lokalną biblioteką materiałów (sample)")
    examples.add_argument("--production", action="store_true", help="Utwórz edytowalny przykład pipeline’u produkcyjnego (sample)")
    examples.add_argument("--campaign", action="store_true", help="Utwórz reklamę 30 s: sześć scen po 5 sekund")
    args = parser.parse_args()
    store = Store(args.root) if args.root else Store()
    if args.command == "mcp":
        from framecore.api import API
        from framecore.render import RenderJobs
        from framecore.mcp import FrameCoreMCP
        FrameCoreMCP(API(store, RenderJobs(store))).serve()
    elif args.command == "projects":
        print(json.dumps(store.list(), indent=2, ensure_ascii=False))
    elif args.command == "sample":
        from framecore.sample import create_sample, create_creator_pack
        if args.campaign:
            from framecore.campaign import create_campaign
            state = create_campaign(store)
        else:
            state = create_creator_pack(store,"production-pipeline") if args.production else create_creator_pack(store) if args.creator_pack else create_sample(store)
        print(json.dumps({"project_id":state["project"]["id"], "name":state["project"]["metadata"]["name"]},ensure_ascii=False))
    else:
        from framecore.server import Server
        srv = Server(store, args.port)
        print(f"TABASCO FRAMECORE STUDIO: http://127.0.0.1:{srv.server_port}", flush=True)
        try: srv.serve_forever()
        except KeyboardInterrupt: pass
        finally: srv.server_close()


if __name__ == "__main__": main()
