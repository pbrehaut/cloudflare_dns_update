from collections import defaultdict
from datetime import datetime
import requests
import json
import os

REVERT = False
TEST = False
API_KEY = ''
IP_MAP_FILE = ''

TIMESTAMP = datetime.now().strftime("%d-%b-%y_%H-%M-%S")

# Create directory for logs
os.mkdir(TIMESTAMP)

b = requests.session()
b.headers['Authorization'] = API_KEY

with open(IP_MAP_FILE, encoding='utf-8') as F:
    ip_map = set([tuple(x.strip().split()) for x in F.readlines()])
old_new_map_for = {x: y for x, y in sorted(ip_map, key=lambda x: [int(z) for z in x[0].split('.')])}
old_new_map_rev = {y: x for x, y in sorted(ip_map, key=lambda x: [int(z) for z in x[0].split('.')])}

old_new_map_test = {
    '10.0.0.13': '10.0.0.15',
    '10.0.0.9': '10.0.0.10'
}

if REVERT:
    old_new_map = old_new_map_rev
elif TEST:
    old_new_map = old_new_map_test
else:
    old_new_map = old_new_map_for


def update_host(b, zone, r_id, r_ip, payload):
    with open(os.path.join(TIMESTAMP, 'Update.log'), 'a', encoding='utf-8') as F:
        payload_dict = json.loads(payload)
        line_sep = '-' * 80
        F.write(f'{line_sep}\n{payload_dict["name"]} from {r_ip} to {payload_dict["content"]}......Updating\n')
        x = b.put(f"https://api.cloudflare.com/client/v4/zones/{zone}/dns_records/{r_id}",
                  data=payload,
                  verify=False).json()
        try:
            assert x['success'] is True
            x = x['result']
            assert x['content'] == payload_dict['content']
            assert x['name'] == payload_dict['name']
            assert x['proxied'] == payload_dict['proxied']
            F.write(f'{payload_dict["name"]} from {r_ip} to {payload_dict["content"]}......Success\n{line_sep}\n\n')
        except:
            F.write(f'{payload_dict["name"]} from {r_ip} to {payload_dict["content"]}......Failed\n{line_sep}\n\n')
            F.write(json.dumps(x, indent=3))
            raise


def get_payload(new_ip, host, proxy: bool):
    payload = json.dumps({"content": new_ip,
                          "type": "A",
                          "name": host,
                          'proxied': proxy})
    return payload


store_zones = defaultdict(list)

# Get first page of zone
page1 = b.get("https://api.cloudflare.com/client/v4/zones", verify=False).json()
page_count = page1['result_info']['total_pages']

pages = page1['result']
for page in range(2, page_count + 1):
    pages.extend(b.get(f"https://api.cloudflare.com/client/v4/zones?page={page}", verify=False).json()['result'])

zone_id_names = [(x['id'], x['name']) for x in pages]
for zone_id, zone_name in zone_id_names:
    print(zone_name)
    x = b.get(f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records", verify=False).json()
    records = x['result']

    # go through each record
    for record in records:
        r_id = record['id']
        r_ip = record['content']
        r_proxy = record['proxied']
        r_name = record['name']

        store_zones[zone_name].append(record)

        # Check if there is an IP mapping
        if r_ip in old_new_map:
            payload = get_payload(old_new_map[r_ip], r_name, r_proxy)
            print(payload)
            update_host(b, zone_id, r_id, r_ip, payload)

    # Write out pre change zone data to file - one text and json file per zone
    with open(os.path.join(TIMESTAMP, zone_name + '.txt'), 'w', encoding='utf-8') as F:
        F.write(json.dumps(store_zones[zone_name], indent=3))
    with open(os.path.join(TIMESTAMP, zone_name + '.json'), 'w', encoding='utf-8') as F:
        json.dump(store_zones[zone_name], F)

# Write out the whole backup in one json file
with open(os.path.join(TIMESTAMP, 'Full Backup.json'), 'w', encoding='utf-8') as F:
    json.dump(store_zones, F)
