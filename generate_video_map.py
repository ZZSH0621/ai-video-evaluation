#!/usr/bin/env python3
"""
generate_video_map.py
Scan 96/ directory and output VIDEO_MAP JS constant + oss_key_map.json.

Usage:
  # 旧模式 (OSS 直连 URL, 保持兼容):
  python generate_video_map.py --output video_map.js

  # 新模式 (Worker 代理 URL):
  python generate_video_map.py \
      --output video_map.js \
      --worker-base https://oss-video-proxy.zzsh0621.workers.dev \
      --oss-key-map worker/oss_key_map.json

  # 仅打印到 stdout (旧行为):
  python generate_video_map.py
"""

import os
import re
import json
import sys
import secrets
import urllib.parse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VIDEO_DIR = os.path.join(BASE_DIR, "96")

# Model folder name -> HTML model name
MODEL_NORMALIZE = {
    "谷歌veo": "Gemini Veo",
    "即梦": "即梦",
    "可灵": "可灵",
    "ViduQ3": "ViduQ3",
}

# Scenario folder name -> HTML scenario name
SCENARIO_NORMALIZE = {
    "AI短剧": "AI漫剧",
    "直播": "直播带货",
    "音乐": "音乐",
    "广告": "广告",
    "特效": "特效",
    "体育运动": "体育运动",
}

# Type substrings extracted from filename -> (normalized type, position in CASE_DETAILS)
TYPE_MAP = {
    # 音乐: mv(0,1), 现场(2,3)
    "mv": ("mv", 0),
    "现场": ("现场", 1),
    # 广告: 汽车广告(0,1), 饮品广告(2,3)
    "汽车": ("汽车广告", 0),
    "饮品": ("饮品广告", 1),
    "红牛": ("饮品广告", 1),
    # AI漫剧: 3D漫剧(0,1), 真人短剧(2,3)
    "3D": ("3D漫剧", 0),
    "真人": ("真人短剧", 1),
    # 直播带货: 3c数码带货(0,1), 美妆带货(2,3)
    "数码": ("3c数码带货", 0),
    "美妆": ("美妆带货", 1),
    # 特效: 现实场景元素特效(0,1), 电影特效(2,3)
    "现实场景元素": ("现实场景元素特效", 0),
    "电影": ("电影特效", 1),
    # 体育运动: 举重(0,1), 篮球(2,3)
    "举重": ("举重", 0),
    "篮球": ("篮球", 1),
}

DIFF_MAP = {
    "简单": ("简单", 0),
    "困难": ("进阶", 1),
}


def parse_filename(filename, scenario_folder):
    """Parse a video filename to extract type and difficulty.
    Returns (type_str, diff_str, case_index) or None on failure.
    """
    name = filename
    if name.lower().endswith(".mp4"):
        name = name[:-4]

    scenario_clean = scenario_folder

    # Remove the scenario prefix from the filename
    pattern = re.escape(scenario_clean) + r"-*"
    remainder = re.sub(r"^" + pattern, "", name)

    if remainder == name:
        if name.startswith(scenario_clean):
            remainder = name[len(scenario_clean):]

    if not remainder:
        return None

    remainder = remainder.strip()
    remainder = re.sub(r"^[\s\-]+", "", remainder)
    remainder = re.sub(r"[\s\-]+$", "", remainder)

    if not remainder:
        return None

    diff_str = None
    type_str = None

    for diff_text in ["困难", "简单"]:
        if remainder.endswith(diff_text):
            diff_str = diff_text
            type_str = remainder[:-len(diff_text)]
            break

    if not diff_str:
        return None

    type_str = type_str.rstrip(" -_")
    if not type_str:
        return None

    type_str = re.sub(r"-+", "-", type_str).strip("-")

    if type_str not in TYPE_MAP:
        print(f"// WARNING: Unknown type '{type_str}' in {filename}", file=sys.stderr)
        return None

    norm_type, type_pos = TYPE_MAP[type_str]
    norm_diff, diff_pos = DIFF_MAP[diff_str]

    case_idx = type_pos * 2 + diff_pos
    return (norm_type, norm_diff, case_idx)


def scan_videos():
    """Scan VIDEO_DIR and build VIDEO_MAP dict + oss_key_map + token_map dicts."""
    video_map = {}
    oss_key_map = {}   # "model/scenario/index" -> "96/model_folder/scenario_folder/file.mp4"
    token_map = {}     # random_token -> oss_path (when --use-tokens)
    file_count = 0
    error_count = 0

    for model_folder in sorted(os.listdir(VIDEO_DIR)):
        model_path = os.path.join(VIDEO_DIR, model_folder)
        if not os.path.isdir(model_path):
            continue

        model_name = MODEL_NORMALIZE.get(model_folder)
        if not model_name:
            print(f"// WARNING: Unknown model folder '{model_folder}'", file=sys.stderr)
            continue

        if model_name not in video_map:
            video_map[model_name] = {}

        for scenario_folder in sorted(os.listdir(model_path)):
            scenario_path = os.path.join(model_path, scenario_folder)
            if not os.path.isdir(scenario_path):
                continue

            scenario_name = SCENARIO_NORMALIZE.get(scenario_folder)
            if not scenario_name:
                print(f"// WARNING: Unknown scenario folder '{scenario_folder}'", file=sys.stderr)
                continue

            if scenario_name not in video_map[model_name]:
                video_map[model_name][scenario_name] = [None, None, None, None]

            mp4_files = sorted([f for f in os.listdir(scenario_path) if f.lower().endswith(".mp4")])

            for mp4_file in mp4_files:
                result = parse_filename(mp4_file, scenario_folder)
                if result is None:
                    print(f"// WARNING: Could not parse '{model_folder}/{scenario_folder}/{mp4_file}'", file=sys.stderr)
                    error_count += 1
                    continue

                norm_type, norm_diff, case_idx = result

                if case_idx < 0 or case_idx > 3:
                    print(f"// WARNING: Invalid case index {case_idx} for '{model_folder}/{scenario_folder}/{mp4_file}'", file=sys.stderr)
                    error_count += 1
                    continue

                # OSS object path (relative from bucket root)
                oss_path = f"96/{model_folder}/{scenario_folder}/{mp4_file}"
                oss_path = oss_path.replace("\\", "/")

                # Build oss_key_map entry
                key = f"{model_name}/{scenario_name}/{case_idx}"
                oss_key_map[key] = oss_path

                # Build token_map entry (random 16-char hex token)
                token = secrets.token_hex(8)  # 16 hex chars
                # Avoid collisions (extremely unlikely, but check anyway)
                while token in token_map:
                    token = secrets.token_hex(8)
                token_map[token] = oss_path

                # For video_map, we store the path; URL generation happens in main()
                video_map[model_name][scenario_name][case_idx] = oss_path
                file_count += 1

    return video_map, oss_key_map, token_map, file_count, error_count


def json_str(obj, indent=0):
    """Pretty-print JSON with 2-space indent, JS-compatible."""
    sp = "  " * indent
    sp1 = "  " * (indent + 1)

    if isinstance(obj, dict):
        if not obj:
            return "{}"
        items = []
        for k, v in obj.items():
            items.append(f'{sp1}"{k}": {json_str(v, indent + 1)}')
        return "{\n" + ",\n".join(items) + "\n" + sp + "}"
    elif isinstance(obj, list):
        if not obj:
            return "[]"
        items = []
        for v in obj:
            items.append(f'{sp1}{json_str(v, indent + 1)}')
        return "[\n" + ",\n".join(items) + "\n" + sp + "]"
    elif obj is None:
        return "null"
    elif isinstance(obj, str):
        return json.dumps(obj, ensure_ascii=False)
    elif isinstance(obj, bool):
        return "true" if obj else "false"
    else:
        return str(obj)


def main():
    # Parse arguments
    worker_base = None
    oss_key_map_path = None
    token_map_path = None
    output_path = None
    use_tokens = False

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--worker-base" and i + 1 < len(args):
            worker_base = args[i + 1].rstrip("/")
            i += 2
        elif args[i] == "--oss-key-map" and i + 1 < len(args):
            oss_key_map_path = args[i + 1]
            i += 2
        elif args[i] == "--token-map" and i + 1 < len(args):
            token_map_path = args[i + 1]
            i += 2
        elif args[i] == "--use-tokens":
            use_tokens = True
            i += 1
        elif args[i] == "--output" and i + 1 < len(args):
            output_path = args[i + 1]
            i += 2
        else:
            i += 1

    # Scan videos
    video_map, oss_key_map, token_map, file_count, error_count = scan_videos()

    # ---- Build VIDEO_MAP JS ----
    if worker_base and use_tokens:
        # Token mode: {worker_base}/v/{random_16_char_hex_token}
        # Build reverse lookup: oss_path -> token
        oss_to_token = {v: k for k, v in token_map.items()}
        video_map_js = {}
        for model_name, scenarios in video_map.items():
            video_map_js[model_name] = {}
            for scenario_name, cases in scenarios.items():
                video_map_js[model_name][scenario_name] = []
                for idx, oss_path in enumerate(cases):
                    if oss_path:
                        token = oss_to_token[oss_path]
                        video_map_js[model_name][scenario_name].append(
                            f"{worker_base}/v/{token}"
                        )
                    else:
                        video_map_js[model_name][scenario_name].append(None)

        comment = "// Auto-generated by generate_video_map.py (token proxy mode)"
    elif worker_base:
        # Readable path mode: {worker_base}/v/{model}/{scenario}/{index}
        video_map_js = {}
        for model_name, scenarios in video_map.items():
            video_map_js[model_name] = {}
            for scenario_name, cases in scenarios.items():
                video_map_js[model_name][scenario_name] = []
                for idx, oss_path in enumerate(cases):
                    if oss_path:
                        video_map_js[model_name][scenario_name].append(
                            f"{worker_base}/v/{model_name}/{scenario_name}/{idx}"
                        )
                    else:
                        video_map_js[model_name][scenario_name].append(None)

        comment = "// Auto-generated by generate_video_map.py (Worker proxy mode)"
    else:
        # Legacy mode: OSS direct paths (relative)
        video_map_js = {}
        for model_name, scenarios in video_map.items():
            video_map_js[model_name] = {}
            for scenario_name, cases in scenarios.items():
                video_map_js[model_name][scenario_name] = []
                for oss_path in cases:
                    if oss_path:
                        video_map_js[model_name][scenario_name].append(
                            urllib.parse.quote(oss_path, safe="/")
                        )
                    else:
                        video_map_js[model_name][scenario_name].append(None)

        comment = "// Auto-generated by generate_video_map.py (legacy direct-path mode)"

    lines = []
    lines.append(comment)
    lines.append(f"// Found {file_count} video files (errors: {error_count})")
    if worker_base:
        lines.append(f"// Worker base: {worker_base}")
        if use_tokens:
            lines.append(f"// Token mode: {len(token_map)} random tokens")
    lines.append("const VIDEO_MAP = " + json_str(video_map_js) + ";")
    output = "\n".join(lines) + "\n"

    # Write video_map.js
    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Written {file_count} entries to {output_path}")
    else:
        sys.stdout.buffer.write(output.encode("utf-8"))

    # ---- Write oss_key_map.json ----
    if oss_key_map_path:
        with open(oss_key_map_path, "w", encoding="utf-8") as f:
            json.dump(oss_key_map, f, ensure_ascii=False, indent=2)
        print(f"Written {len(oss_key_map)} entries to {oss_key_map_path}")

    # ---- Write token_map.json ----
    if token_map_path:
        with open(token_map_path, "w", encoding="utf-8") as f:
            json.dump(token_map, f, ensure_ascii=False, indent=2)
        print(f"Written {len(token_map)} entries to {token_map_path}")

    if error_count > 0:
        print(f"\n// ⚠ {error_count} files could not be parsed!", file=sys.stderr)


if __name__ == "__main__":
    main()
