import os, django, uuid
os.environ.setdefault('DJANGO_SETTINGS_MODULE','odozi.settings')
django.setup()
from django.core.cache import cache
from django.test import Client

# Prepare ticket
client = Client()
client.defaults['wsgi.url_scheme'] = 'http'

ticket_id = str(uuid.uuid4())
redis_ticket_key = f'ws_transit_ticket:{ticket_id}'
cache_key = f'redis_auth_{redis_ticket_key}'
payload = {
    'jwt_access_token': b'dummyjwt',
    'github_access_token': b'dummygithub',
    'browser_family': 'test-browser',
    'expires_at': 'never'
}
cache.set(cache_key, payload, timeout=60)
print('Set cache key', cache_key)

# Attach cookie to client
client.cookies['ticket_id'] = ticket_id

print('\n=== First ws-ticket POST ===')
r = client.post('/account/api/auth/ws-ticket/')
print(r.status_code, r.content)

print('\n=== Second ws-ticket POST (should be 409) ===')
r = client.post('/account/api/auth/ws-ticket/')
print(r.status_code, r.content)

print('\n=== First dashboard POST ===')
r = client.post('/dashboard/')
print(r.status_code, r.content[:200])

print('\n=== Second dashboard POST (should be 403 or 409) ===')
r = client.post('/dashboard/')
print(r.status_code, r.content[:200])
