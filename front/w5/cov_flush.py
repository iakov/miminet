"""W5 fork-experiment helper: persist coverage data from forked children.

coverage.py only writes its data on process exit (atexit) or on SIGTERM when
``[run] sigterm = true`` is set in the config file. Celery prefork children
exit via os._exit, so neither hook fires there and their task-execution data
would be lost. This module, imported through w5_cov.pth from the app venv,
registers an at-fork child hook that starts a daemon thread which periodically
calls coverage.save(). Gated on the W5_COV_FLUSH env var so an instrumented
boot of the image is opt-in.
"""

import os


def _install() -> None:
    if not os.getenv("W5_COV_FLUSH"):
        return
    try:
        import threading
        import time

        from coverage.control import process_startup

        def _spawn_child_saver() -> None:
            cov = getattr(process_startup, "coverage", None)
            if cov is None:
                return

            def _loop() -> None:
                while True:
                    time.sleep(10)
                    try:
                        cov.save()
                    except Exception:
                        pass

            threading.Thread(target=_loop, daemon=True).start()

        os.register_at_fork(after_in_child=_spawn_child_saver)
    except Exception:
        pass


_install()
