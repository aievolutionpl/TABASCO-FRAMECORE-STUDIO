"""Native window entry point, with an explicit headless mode for package acceptance."""
import argparse
import logging
import sys
from pathlib import Path
from framecore.desktop_runtime import APP_NAME, configure, data_directory


def main():
    configure()
    parser = argparse.ArgumentParser(description=APP_NAME)
    parser.add_argument('--root', type=Path)
    parser.add_argument('--headless', action='store_true', help='Test the packaged server without opening a window')
    parser.add_argument('--ready-file', type=Path, help='Write the local URL for automated package acceptance')
    args = parser.parse_args()
    directory = data_directory()
    directory.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=directory / 'desktop.log', level=logging.INFO,
                        format='%(asctime)s %(levelname)s %(message)s', encoding='utf-8')
    if sys.stdout is None: sys.stdout = open(directory / 'desktop-output.log', 'a', encoding='utf-8', buffering=1)
    if sys.stderr is None: sys.stderr = sys.stdout
    from framecore.store import Store
    from framecore.server import start_background
    server, thread = start_background(Store(args.root or directory / 'projects'))
    url = f'http://127.0.0.1:{server.server_port}/'
    if args.ready_file:
        import json
        args.ready_file.write_text(json.dumps({'url':url}),encoding='utf-8')
    try:
        if args.headless:
            print(url, flush=True)
            thread.join()
        else:
            import webview
            webview.create_window(APP_NAME, url, width=1440, height=940,
                                  min_size=(800, 600), background_color='#17191b')
            webview.start(gui='edgechromium' if sys.platform == 'win32' else 'cocoa' if sys.platform == 'darwin' else None)
    except KeyboardInterrupt:
        pass
    except Exception:
        logging.exception('Nie udało się uruchomić okna studia')
        raise
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


if __name__ == '__main__':
    main()
