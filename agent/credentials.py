"""Private encrypted operator storage, shared by Instagram runtimes."""
import contextlib
import fcntl
import json
import os
from pathlib import Path
import stat
import tempfile
import urllib.request
from cryptography.fernet import Fernet


class AccessError(Exception):
    """Safe operator error; never include credentials or provider responses."""


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Store:
    def __init__(self, data_dir, key_dir, forbidden_root=None):
        self.data_dir = Path(data_dir).expanduser().absolute()
        self.key_dir = Path(key_dir).expanduser().absolute()
        root = Path(forbidden_root or Path(__file__).resolve().parents[1]).resolve()
        for path in (self.data_dir, self.key_dir):
            resolved = path.resolve()
            if resolved == root or root in resolved.parents:
                raise AccessError('Credential storage must be outside the repository and website source mount.')
            if resolved == Path('/') or '..' in path.parts:
                raise AccessError('Choose private credential directories.')
            for part in (path, *path.parents):
                if part.is_symlink():
                    raise AccessError('Credential paths must not contain symlinks.')
        if self.data_dir.resolve() == self.key_dir.resolve() or self.data_dir.resolve() in self.key_dir.resolve().parents or self.key_dir.resolve() in self.data_dir.resolve().parents:
            raise AccessError('Use separate directories for encrypted tokens and their key.')
        self.record_path = self.data_dir / 'instagram.fernet'
        self.key_path = self.key_dir / 'instagram.key'

    @staticmethod
    def private_dir(path):
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
        info = path.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
            raise AccessError('Credential directory must be owned by you with mode 0700.')

    @staticmethod
    def read_private(path, limit):
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, 'rb') as handle:
            info = os.fstat(handle.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1:
                raise AccessError('Credential files must be privately owned, mode 0600, and not linked.')
            value = handle.read(limit + 1)
            if len(value) > limit:
                raise AccessError('Credential file exceeded the safety limit.')
            return value

    @contextlib.contextmanager
    def locked(self):
        self.private_dir(self.data_dir)
        self.private_dir(self.key_dir)
        fd = os.open(self.data_dir / 'operator.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'a') as handle:
            info = os.fstat(handle.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1:
                raise AccessError('Unsafe operator lock file.')
            fcntl.flock(handle, fcntl.LOCK_EX)
            yield

    def save(self, record):
        if not self.key_path.exists():
            if self.record_path.exists():
                raise AccessError('Encryption key missing. Do not overwrite existing credentials.')
            fd = os.open(self.key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, 'wb') as handle:
                handle.write(Fernet.generate_key())
                handle.flush()
                os.fsync(handle.fileno())
        encrypted = Fernet(self.read_private(self.key_path, 128)).encrypt(json.dumps(record).encode())
        fd, name = tempfile.mkstemp(prefix='.instagram-', dir=self.data_dir)
        try:
            with os.fdopen(fd, 'wb') as handle:
                handle.write(encrypted)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(name, self.record_path)
            directory = os.open(self.data_dir, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            if os.path.exists(name):
                os.unlink(name)
