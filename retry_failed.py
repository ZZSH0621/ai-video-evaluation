"""Retry failed compressions with safe temp filenames."""
import subprocess, os, glob, tempfile, shutil

video_dir = r'F:\AI\新的网站\96'
videos = glob.glob(os.path.join(video_dir, '**', '*.mp4'), recursive=True)
tmpdir = tempfile.mkdtemp()
fixed = 0

for i, v in enumerate(videos):
    size_mb = os.path.getsize(v) / 1e6
    # Already compressed files are < 5MB (CRF30 720p), skip them
    # Original failed ones still > 2MB typically
    # Actually let's just check: if file > 3MB, likely not compressed yet
    if size_mb < 3.0:
        continue

    tmp_in = os.path.join(tmpdir, f'in_{i}.mp4')
    tmp_out = os.path.join(tmpdir, f'out_{i}.mp4')
    try:
        shutil.copy2(v, tmp_in)
        cmd = [
            'ffmpeg', '-y', '-i', tmp_in,
            '-vf', "scale='min(1280,iw)':'min(720,ih)':force_original_aspect_ratio=decrease",
            '-c:v', 'libx264', '-crf', '30', '-preset', 'fast',
            '-c:a', 'aac', '-b:a', '64k', '-ac', '1',
            '-movflags', '+faststart', tmp_out
        ]
        r = subprocess.run(cmd, capture_output=True)
        if r.returncode == 0 and os.path.exists(tmp_out):
            new_mb = os.path.getsize(tmp_out) / 1e6
            os.replace(tmp_out, v)
            pct = round((size_mb - new_mb) / size_mb * 100, 1)
            print(f'[{fixed+1}] {pct}%  {round(size_mb,1)}MB -> {round(new_mb,1)}MB  {os.path.basename(v)}')
            fixed += 1
        else:
            print(f'SKIP: {os.path.basename(v)}')
    except Exception as e:
        print(f'ERR: {os.path.basename(v)} - {e}')
    finally:
        for f in [tmp_in, tmp_out]:
            if os.path.exists(f):
                os.remove(f)

shutil.rmtree(tmpdir, ignore_errors=True)
print(f'\nFixed: {fixed} files')
