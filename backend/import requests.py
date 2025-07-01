import requests

response = requests.get(
    'http://localhost:8000/init/12822',
    params={'stream': 'true', 'include_summary': 'true'},
    headers={
        'X-Tenant-ID': 'wedosoft',
        'X-Platform': 'freshdesk',
        'X-Domain': 'wedosoft',
        'X-API-Key' : 'Ug9H1cKCZZtZ4haamBy'
    },
    stream=True
)

for line in response.iter_lines():
    if line:
        print(f"스트리밍 청크: {line.decode()}")