"""Compress all 96/ videos to 720p CRF 30 for web streaming."""
import subprocess, os, glob

video_dir = r'F:\AI\新的网站\96'
videos = glob.glob(os.path.join(video_dir, '**', '*.mp4'), recursive=True)
total = len(videos)
orig_total = 0
new_total = 0
failed = []

for i, v in enumerate(videos):
    orig_size = os.path.getsize(v)
    orig_total += orig_size
    tmp = v + '.tmp.mp4'
    cmd = [
        'ffmpeg', '-y', '-i', v,
        '-vf', "scale='min(1280,iw)':'min(720,ih)':force_original_aspect_ratio=decrease",
        '-c:v', 'libx264', '-crf', '30', '-preset', 'fast',
        '-c:a', 'aac', '-b:a', '64k', '-ac', '1',
        '-movflags', '+faststart', tmp
    ]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode == 0 and os.path.exists(tmp):
        new_size = os.path.getsize(tmp)
        os.replace(tmp, v)
        new_total += new_size
        pct = round((orig_size - new_size) / orig_size * 100, 1)
        print(f'[{i+1}/{total}] {pct}%  {round(orig_size/1e6,1)}MB -> {round(new_size/1e6,1)}MB')
    else:
        failed.append(v)
        print(f'[{i+1}/{total}] FAILED: {os.path.basename(v)}')
        if os.path.exists(tmp):
            os.remove(tmp)

orig_mb = round(orig_total/1e6, 1)
new_mb = round(new_total/1e6, 1)
saved_pct = round((orig_total-new_total)/orig_total*100, 1) if orig_total > 0 else 0
print(f'\nDone! {orig_mb}MB -> {new_mb}MB  ({saved_pct}% saved)')
if failed:
    print(f'Failed: {len(failed)} files')
