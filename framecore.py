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
    examples.add_argument("--showreel", action="store_true", help="Utwórz showreel Ruchu 2.0 (16:9, 24 s)")
    examples.add_argument("--reel", action="store_true", help="Utwórz rolkę Ruchu 2.0 (9:16, 12 s)")
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
        if args.showreel or args.reel:
            from framecore.showcase import create_reel, create_showreel
            state = create_showreel(store) if args.showreel else create_reel(store)
        elif args.campaign:
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
