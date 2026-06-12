"""Regenerate all OSS signed URLs - regex based replacement."""
import oss2, re, os, glob
from urllib.parse import unquote

access_key_id = os.environ.get('OSS_ACCESS_KEY_ID', '')
access_key_secret = os.environ.get('OSS_ACCESS_KEY_SECRET', '')
bucket_name = os.environ.get('OSS_BUCKET', '96vedio')
endpoint = os.environ.get('OSS_ENDPOINT', 'oss-cn-beijing.aliyuncs.com')

if not access_key_id or not access_key_secret:
    print('Error: Set OSS_ACCESS_KEY_ID and OSS_ACCESS_KEY_SECRET environment variables')
    exit(1)

auth = oss2.Auth(access_key_id, access_key_secret)
bucket = oss2.Bucket(auth, endpoint, bucket_name)

# Pattern to find OSS signed URLs in files
oss_url_pattern = re.compile(r'"(https?://96vedio\.oss-cn-beijing\.aliyuncs\.com/[^"]+\?[^"]+)"')

def extract_key_from_url(url):
    """Extract OSS object key from a signed URL."""
    # URL format: http(s)://bucket.endpoint/ENCODED_PATH?params...
    path_part = url.split('.com/')[1].split('?')[0]
    # URL decode the path
    return unquote(path_part)

def process_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    urls = oss_url_pattern.findall(content)
    print(f'{os.path.basename(filepath)}: found {len(urls)} signed URLs')

    replaced = 0
    for old_url in urls:
        try:
            key = extract_key_from_url(old_url)
            # Generate new signed URL (HTTPS, slash_safe)
            new_url = bucket.sign_url('GET', key, 31536000, slash_safe=True).replace('http://', 'https://')
            if new_url != old_url:
                content = content.replace(f'"{old_url}"', f'"{new_url}"')
                replaced += 1
        except Exception as e:
            print(f'  Error processing: {old_url[:80]}... - {e}')

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f'  Replaced: {replaced}/{len(urls)}')
    return replaced

# Process both files
r1 = process_file(r'F:\AI\新的网站\video_map.js')
r2 = process_file(r'F:\AI\新的网站\index.html')
print(f'\nTotal replaced: {r1} (JS) + {r2} (HTML) = {r1+r2}')
