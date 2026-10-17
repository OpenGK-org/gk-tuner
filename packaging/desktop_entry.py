"""Windowed Windows entry point, also used by the packaged smoke check."""
import sys
import traceback

from gktuner.runtime import prepare_desktop_runtime, data_root


def main():
    prepare_desktop_runtime()
    if '--smoke-test' in sys.argv:
        from gktuner.release_check import run
        return run(sys.argv[sys.argv.index('--smoke-test') + 1])
    if '--gkflasher-cli' in sys.argv:
        import runpy
        from gktuner.runtime import default_backend
        entry = default_backend('GKFlasher') / 'gkflasher.py'
        sys.path.insert(0, str(entry.parent))
        sys.argv = [str(entry), *sys.argv[sys.argv.index('--gkflasher-cli') + 1:]]
        runpy.run_path(str(entry), run_name='__main__')
        return 0
    from PyQt5 import QtWidgets as W

    def failed(kind, value, trace):
        details = ''.join(traceback.format_exception(kind, value, trace))
        print(details, file=sys.stderr, flush=True)
        if W.QApplication.instance():
            W.QMessageBox.critical(None, 'GK Tuner', f'{value}\n\nDetails were saved to {data_root() / "runtime.log"}.')

    sys.excepthook = failed
    from gktuner.app import main as app_main
    return app_main()


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise
