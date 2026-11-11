"""Reuse the operator's private-directory/atomic-write storage boundary."""
import json
from cryptography.fernet import Fernet, InvalidToken
from agent.credentials import AccessError, Store


class PocStore(Store):
    def __init__(self, data_dir, key_dir):
        super().__init__(data_dir, key_dir)
        self.record_path = self.data_dir / 'private-api.fernet'
        self.key_path = self.key_dir / 'private-api.key'

    def load(self):
        if not self.record_path.exists():
            return None
        try:
            record = json.loads(Fernet(self.read_private(self.key_path, 128)).decrypt(
                self.read_private(self.record_path, 4 * 1024 * 1024)))
            if not isinstance(record, dict) or record.get('schema') != 'instagrapi-poc-v1':
                raise ValueError()
            return record
        except (InvalidToken, ValueError, TypeError, OSError):
            raise AccessError('Encrypted PoC storage could not be read. Existing files were preserved.') from None

    def save(self, record):
        if len(json.dumps(record).encode()) > 2 * 1024 * 1024:
            raise AccessError('PoC storage limit reached. Reduce the number of fetched posts.')
        super().save(record)
