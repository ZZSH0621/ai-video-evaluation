#!/usr/bin/env python3
"""
从现有 video_map.js 中提取 OSS 对象路径，生成 oss_key_map.json。
这是过渡脚本 —— 之后 generate_video_map.py --oss-key-map 会直接生成。

Usage:
    python extract_oss_key_map.py video_map.js worker/oss_key_map.json
"""
import re
import json
import base64
import sys
from urllib.parse import unquote, urlparse


def extract_oss_path_from_url(url):
    """从 OSS 签名 URL 中提取对象路径。
    URL 格式: https://bucket.endpoint/ENCODED_PATH?params...
    返回: 解码后的路径 (如 "96/ViduQ3/AI短剧/AI短剧-3D-简单.mp4")
    """
    parsed = urlparse(url)
    path = unquote(parsed.path)
    # Remove leading slash
    if path.startswith('/'):
        path = path[1:]
    return path


def main():
    if len(sys.argv) < 2:
        js_path = r'F:\AI\新的网站\video_map.js'
    else:
        js_path = sys.argv[1]

    if len(sys.argv) < 3:
        out_path = r'F:\AI\新的网站\worker\oss_key_map.json'
    else:
        out_path = sys.argv[2]

    with open(js_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 提取 VIDEO_MAP 结构
    # 找到 atob("...") 并解码
    atob_pattern = re.compile(r'atob\("([^"]+)"\)')

    all_urls = []
    for m in atob_pattern.finditer(content):
        try:
            decoded = base64.b64decode(m.group(1)).decode('utf-8')
            all_urls.append(decoded)
        except Exception as e:
            print(f"Decode error: {e}", file=sys.stderr)

    print(f"Found {len(all_urls)} atob()-encoded URLs", file=sys.stderr)

    # 解析 JSON 结构来获取 model/scenario/index 映射
    # 提取 VIDEO_MAP 的 JSON 部分
    json_match = re.search(r'const VIDEO_MAP = ({[\s\S]*?});', content)
    if not json_match:
        print("ERROR: Could not find VIDEO_MAP in file", file=sys.stderr)
        sys.exit(1)

    json_str = json_match.group(1)

    # 将 atob("...") 替换为临时占位符以便 JSON 解析
    url_index = [0]
    def replace_atob(m):
        idx = url_index[0]
        url_index[0] += 1
        return json.dumps(f"__URL_{idx}__")

    clean_json = atob_pattern.sub(replace_atob, json_str)

    try:
        video_map = json.loads(clean_json)
    except json.JSONDecodeError as e:
        print(f"JSON parse error: {e}", file=sys.stderr)
        sys.exit(1)

    # 构建 oss_key_map
    oss_key_map = {}
    url_idx = 0

    for model_name, scenarios in video_map.items():
        for scenario_name, cases in scenarios.items():
            for i, case in enumerate(cases):
                if case and case.startswith('__URL_'):
                    url = all_urls[url_idx]
                    url_idx += 1
                    oss_path = extract_oss_path_from_url(url)
                    key = f"{model_name}/{scenario_name}/{i}"
                    oss_key_map[key] = oss_path
                    print(f"  {key} -> {oss_path}", file=sys.stderr)
                elif case:
                    # Direct path (non-encoded)
                    key = f"{model_name}/{scenario_name}/{i}"
                    oss_key_map[key] = case
                    print(f"  {key} -> {case} (direct)", file=sys.stderr)

    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(oss_key_map, f, ensure_ascii=False, indent=2)

    print(f"\nWritten {len(oss_key_map)} entries to {out_path}")


if __name__ == "__main__":
    main()
