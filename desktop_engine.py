"""Console worker for rendering and stdio MCP, shipped alongside the native app."""
import argparse
import sys
from pathlib import Path
from framecore.desktop_runtime import configure, data_directory


def main():
    configure()
    # PyInstaller's bootloader can ignore PYTHONUTF8 on Windows. MCP is UTF-8
    # regardless of console code page, including redirected pipes from agents.
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='strict')
    if len(sys.argv) > 1 and sys.argv[1] == '--render-worker':
        log_path = Path(sys.argv[2])
        sys.argv = [sys.argv[0], *sys.argv[3:]]
        with log_path.open('a', encoding='utf-8', buffering=1) as log:
            sys.stdout = sys.stderr = log
            from vstudio.renderers.html_to_video import main as render
            return render()
    parser = argparse.ArgumentParser(description='FrameCore desktop engine')
    parser.add_argument('--mcp', action='store_true', required=True)
    parser.add_argument('--root', type=Path, default=data_directory() / 'projects')
    args = parser.parse_args()
    from framecore.store import Store
    from framecore.api import API
    from framecore.render import RenderJobs
    from framecore.mcp import FrameCoreMCP
    store = Store(args.root)
    FrameCoreMCP(API(store, RenderJobs(store))).serve()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
