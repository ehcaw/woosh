from pathlib import Path
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import secrets
import json
from sqlalchemy import create_engine
from contextlib import contextmanager

class DatabaseConfig:
    CONFIG_FILE = 'db_config.encrypted'
    
    def __init__(self):
        self.key = self._get_or_create_key()
        self.fernet = Fernet(self.key)
        
    def _get_or_create_key(self):
        key_file = Path('.env.key')
        if key_file.exists():
            return key_file.read_bytes()
        else:
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=b'static_salt',
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(secrets.token_bytes(32)))
            key_file.write_bytes(key)
            return key
    
    def save_config(self, config):
        encrypted_data = self.fernet.encrypt(json.dumps(config).encode())
        with open(self.CONFIG_FILE, 'wb') as f:
            f.write(encrypted_data)
    
    def load_config(self):
        try:
            if not Path(self.CONFIG_FILE).exists():
                return None
            with open(self.CONFIG_FILE, 'rb') as f:
                encrypted_data = f.read()
            decrypted_data = self.fernet.decrypt(encrypted_data)
            return json.loads(decrypted_data)
        except Exception:
            return None

def get_db_url(config):
    """Get database URL from stored configuration"""
    if not config:
        raise Exception("Database not configured")
    return f"mysql+mysqlconnector://{config['DB_USER']}:{config['DB_PASSWORD']}@{config['DB_HOST']}:{config['DB_PORT']}/{config['DB_NAME']}"

@contextmanager
def get_db_connection(config):
    """Context manager for database connections"""
    if not config:
        raise Exception("Database not configured")
    
    engine = create_engine(get_db_url(config))
    try:
        connection = engine.connect()
        yield connection
    finally:
        connection.close()
        engine.dispose()