"""会话状态、文件锁与原子持久化。"""
import json
import os
from pathlib import Path
import tempfile


def new_session():
    return {"turns": [], "summary": "", "todos": [], "trace": []}



class SessionStore:
    """One file and advisory OS lock per user/session, covering the full transaction."""
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def transact(self, user, session_id, operation):
        import hashlib
        import contextlib
        key = hashlib.sha256(json.dumps([user, session_id]).encode()).hexdigest()
        path = self.directory / (key + ".json")
        with open(self.directory / (key + ".lock"), "a+b") as lock:
            lock.seek(0)
            if not lock.read(1):
                lock.write(b"0")
                lock.flush()
            lock.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            try:
                state = json.loads(path.read_text(encoding="utf-8")) if path.exists() else new_session()
                result = operation(state)
                fd, temporary = tempfile.mkstemp(dir=self.directory, suffix=".tmp")
                try:
                    with os.fdopen(fd, "w", encoding="utf-8") as output:
                        json.dump(state, output, ensure_ascii=False)
                        output.flush()
                        os.fsync(output.fileno())
                    os.replace(temporary, path)
                finally:
                    with contextlib.suppress(FileNotFoundError):
                        os.unlink(temporary)
                return result, state
            finally:
                lock.seek(0)
                if os.name == "nt":
                    msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(lock, fcntl.LOCK_UN)

