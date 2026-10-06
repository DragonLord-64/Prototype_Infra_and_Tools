#!/usr/bin/env python3
"""Generate local NetBox service secrets once; never overwrite existing env files."""
from pathlib import Path
import os
import secrets

root = Path(__file__).resolve().parent / 'env'
if root.exists() and any(root.iterdir()):
    raise SystemExit('Existing env files preserved. Use them to restart the deployment.')
root.mkdir(mode=0o700, exist_ok=True)
os.chmod(root, 0o700)
db, redis, cache, key, pepper = [secrets.token_hex(32) for _ in range(5)]
files = {
    'postgres.env': {'POSTGRES_DB': 'netbox', 'POSTGRES_USER': 'netbox', 'POSTGRES_PASSWORD': db},
    'redis.env': {'REDIS_PASSWORD': redis},
    'redis-cache.env': {'REDIS_PASSWORD': cache},
    'netbox.env': {
        'DB_HOST': 'postgres', 'DB_NAME': 'netbox', 'DB_USER': 'netbox', 'DB_PASSWORD': db,
        'REDIS_HOST': 'redis', 'REDIS_DATABASE': '0', 'REDIS_PASSWORD': redis,
        'REDIS_CACHE_HOST': 'redis-cache', 'REDIS_CACHE_DATABASE': '1', 'REDIS_CACHE_PASSWORD': cache,
        'SECRET_KEY': key, 'API_TOKEN_PEPPER_1': pepper, 'SKIP_SUPERUSER': 'true',
        'CORS_ORIGIN_ALLOW_ALL': 'False', 'MEDIA_ROOT': '/opt/netbox/netbox/media',
    },
}
for name, values in files.items():
    path = root / name
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, 'w') as stream:
        stream.write(''.join(f'{k}={v}\n' for k, v in values.items()))
print('Private service environment created. No secret values printed.')
