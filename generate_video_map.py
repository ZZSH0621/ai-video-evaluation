#!/usr/bin/env python3
"""
generate_video_map.py
Scan 96/ directory and output VIDEO_MAP JS constant.
Handles all naming anomalies: extra spaces, double dashes, missing dashes,
alternate type names (红牛/饮品, AI短剧/AI漫剧, etc).

Usage: python generate_video_map.py > video_map.js
       Then paste output into HTML <script> after MODEL_DIM_SCORES.
"""

import os
import re
import json
import urllib.parse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VIDEO_DIR = os.path.join(BASE_DIR, "96")

# Model folder name → HTML model name
MODEL_NORMALIZE = {
    "谷歌veo": "Gemini Veo",
    "即梦": "即梦",
    "可灵": "可灵",
    "ViduQ3": "ViduQ3",
}

# Scenario folder name → HTML scenario name
SCENARIO_NORMALIZE = {
    "AI短剧": "AI漫剧",
    "直播": "直播带货",
    "音乐": "音乐",
    "广告": "广告",
    "特效": "特效",
    "体育运动": "体育运动",
}

# Type substrings extracted from filename → (normalized type, position in CASE_DETAILS)
# Position 0 = first type pair (cases 0,1), Position 1 = second type pair (cases 2,3)
TYPE_MAP = {
    # 音乐: mv(0,1), 现场(2,3)
    "mv": ("mv", 0),
    "现场": ("现场", 1),
    # 广告: 汽车广告(0,1), 饮品广告(2,3) - some models use 红牛 instead of 饮品
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

# Difficulty mapping: folder uses 困难, HTML uses 进阶
DIFF_MAP = {
    "简单": ("简单", 0),
    "困难": ("进阶", 1),
}


def parse_filename(filename, scenario_folder):
    """
    Parse a video filename to extract type and difficulty.
    Returns (type_str, diff_str, case_index) or None on failure.
    """
    # Remove extension
    name = filename
    if name.lower().endswith(".mp4"):
        name = name[:-4]

    # Remove scenario prefix (the folder name)
    # The filename starts with the scenario name, possibly with extra dashes
    # Examples: "音乐-mv-简单", "AI短剧-3D-困难", "特效--电影-困难"
    scenario_clean = scenario_folder

    # Remove the scenario prefix from the filename
    # Handle cases where scenario is followed by dashes
    pattern = re.escape(scenario_clean) + r"-*"
    remainder = re.sub(r"^" + pattern, "", name)

    # Also handle when scenario is followed directly by content (no dash)
    # e.g., "音乐mv简单" → try removing just the scenario string
    if remainder == name:
        if name.startswith(scenario_clean):
            remainder = name[len(scenario_clean):]

    if not remainder:
        return None

    # Clean up: strip spaces, normalize multiple dashes to single dash
    remainder = remainder.strip()
    # Remove leading dashes and spaces
    remainder = re.sub(r"^[\s\-]+", "", remainder)
    # Remove trailing dashes and spaces
    remainder = re.sub(r"[\s\-]+$", "", remainder)

    if not remainder:
        return None

    # Now parse type and difficulty
    # Case 1: "type-diff" (normal, e.g., "mv-简单", "汽车-困难")
    # Case 2: "typediff" (no dash, e.g., "mv简单", "mv困难")
    # Case 3: "type-diff" where type has internal dashes (e.g., "现实场景元素-简单")

    # Try to find difficulty at the end
    diff_str = None
    type_str = None

    for diff_text in ["困难", "简单"]:
        if remainder.endswith(diff_text):
            diff_str = diff_text
            type_str = remainder[:-len(diff_text)]
            break

    if not diff_str:
        return None

    # Clean type: strip trailing dashes/spaces
    type_str = type_str.rstrip(" -_")
    if not type_str:
        return None

    # Normalize type: handle extra dashes in middle of type
    # e.g., "现实场景元素" might have extra dashes
    type_str = re.sub(r"-+", "-", type_str).strip("-")

    # Map type to normalized type and position
    if type_str not in TYPE_MAP:
        print(f"// WARNING: Unknown type '{type_str}' in {filename}", file=__import__('sys').stderr)
        return None

    norm_type, type_pos = TYPE_MAP[type_str]
    norm_diff, diff_pos = DIFF_MAP[diff_str]

    # Case index = type_pos * 2 + diff_pos
    case_idx = type_pos * 2 + diff_pos

    return (norm_type, norm_diff, case_idx)


def scan_videos():
    """Scan VIDEO_DIR and build VIDEO_MAP dict."""
    video_map = {}
    file_count = 0
    error_count = 0

    for model_folder in sorted(os.listdir(VIDEO_DIR)):
        model_path = os.path.join(VIDEO_DIR, model_folder)
        if not os.path.isdir(model_path):
            continue

        model_name = MODEL_NORMALIZE.get(model_folder)
        if not model_name:
            print(f"// WARNING: Unknown model folder '{model_folder}'", file=__import__('sys').stderr)
            continue

        if model_name not in video_map:
            video_map[model_name] = {}

        for scenario_folder in sorted(os.listdir(model_path)):
            scenario_path = os.path.join(model_path, scenario_folder)
            if not os.path.isdir(scenario_path):
                continue

            scenario_name = SCENARIO_NORMALIZE.get(scenario_folder)
            if not scenario_name:
                print(f"// WARNING: Unknown scenario folder '{scenario_folder}'", file=__import__('sys').stderr)
                continue

            if scenario_name not in video_map[model_name]:
                video_map[model_name][scenario_name] = [None, None, None, None]

            mp4_files = sorted([f for f in os.listdir(scenario_path) if f.lower().endswith(".mp4")])

            for mp4_file in mp4_files:
                result = parse_filename(mp4_file, scenario_folder)
                if result is None:
                    print(f"// WARNING: Could not parse '{model_folder}/{scenario_folder}/{mp4_file}'", file=__import__('sys').stderr)
                    error_count += 1
                    continue

                norm_type, norm_diff, case_idx = result

                if case_idx < 0 or case_idx > 3:
                    print(f"// WARNING: Invalid case index {case_idx} for '{model_folder}/{scenario_folder}/{mp4_file}'", file=__import__('sys').stderr)
                    error_count += 1
                    continue

                # Build absolute file:// URL (encode spaces/special chars)
                abs_path = os.path.abspath(os.path.join(scenario_path, mp4_file))
                # Use urllib to properly encode the path
                file_url = "file:///" + urllib.parse.quote(abs_path.replace("\\", "/"), safe="/:")

                video_map[model_name][scenario_name][case_idx] = file_url
                file_count += 1

    return video_map, file_count, error_count


def main():
    import sys
    video_map, file_count, error_count = scan_videos()

    # Custom JSON output with indentation
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

    lines = []
    lines.append("// Auto-generated by generate_video_map.py")
    lines.append(f"// Found {file_count} video files (errors: {error_count})")
    lines.append("const VIDEO_MAP = " + json_str(video_map) + ";")
    output = "\n".join(lines) + "\n"

    # Write to file if --output specified, else stdout
    if "--output" in sys.argv:
        idx = sys.argv.index("--output")
        if idx + 1 < len(sys.argv):
            out_path = sys.argv[idx + 1]
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(output)
            print(f"Written {file_count} entries to {out_path}")
    else:
        sys.stdout.buffer.write(output.encode("utf-8"))

    if error_count > 0:
        print(f"\n// ⚠ {error_count} files could not be parsed!", file=sys.stderr)


if __name__ == "__main__":
    main()
