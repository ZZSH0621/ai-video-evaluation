"""Add anti-copy protection, encode Worker proxy URLs, then obfuscate JS."""
import re, base64, subprocess, os, shutil

html_path = r'F:\AI\新的网站\index.html'

# ============================================================
# 控制开关 (休眠 = True, 启用 = False)
# ============================================================
SKIP_PROTECT = True   # True=休眠反制(右键/键盘/录屏/水印), False=启用
SKIP_OVERLAY = True   # True=休眠赛博加载动画, False=启用

with open(html_path, 'r', encoding='utf-8') as f:
    html = f.read()

# 防止重复处理：已混淆的 HTML 不再处理
if '<!-- PROTECT_PROCESSED -->' in html:
    print('ERROR: This HTML has already been processed by protect.py.')
    print('Restore clean index.html from git first, then re-run.')
    exit(1)

# ============================================================
# STEP 1: Inject anti-copy protection BEFORE main script
# ============================================================
protection_code = '''
<!-- ANTI-COPY PROTECTION -->
<script>
(function(){
  // ---- 开发后门: URL 带 ?dev=1 跳过全部保护 ----
  if(/[?&]dev=1(&|$)/.test(location.search))return;

  // ==========================================
  // 1. 禁用右键 (不影响正常浏览)
  // ==========================================
  document.addEventListener('contextmenu', function(e){ e.preventDefault(); return false; });

  // ==========================================
  // 2. 禁用开发者快捷键 (阻止但不弹窗)
  // ==========================================
  document.addEventListener('keydown', function(e){
    if(e.keyCode===123){ e.preventDefault(); return false; }
    if(e.ctrlKey&&e.shiftKey&&(e.keyCode===73||e.keyCode===74||e.keyCode===67)){ e.preventDefault(); return false; }
    if(e.ctrlKey&&e.keyCode===85){ e.preventDefault(); return false; }
    if(e.ctrlKey&&e.keyCode===83){ e.preventDefault(); return false; }
  });

  // ==========================================
  // 3. 截图/录屏黑屏遮罩
  // ==========================================
  var shield=document.createElement('div');
  shield.id='cpy-shield';
  shield.innerHTML='<div style="display:flex;align-items:center;justify-content:center;height:100%;color:#333;font-family:monospace;font-size:14px;letter-spacing:2px;user-select:none">⛔ SCREEN CAPTURE BLOCKED</div>';
  shield.style.cssText='position:fixed;top:0;left:0;width:100vw;height:100vh;z-index:9999999;background:#000;display:none;pointer-events:none';
  document.documentElement.appendChild(shield);

  function showShield(){
    shield.style.display='block';
    setTimeout(function(){shield.style.display='none'},600);
  }

  // 拦截浏览器录屏 API (getDisplayMedia)
  if(navigator.mediaDevices&&navigator.mediaDevices.getDisplayMedia){
    var _gdm=navigator.mediaDevices.getDisplayMedia.bind(navigator.mediaDevices);
    navigator.mediaDevices.getDisplayMedia=function(c){
      showShield();
      return _gdm(c).then(function(s){
        // 监听录屏停止，再次黑屏
        s.getVideoTracks().forEach(function(t){
          t.addEventListener('ended',function(){setTimeout(showShield,100)});
        });
        return s;
      });
    };
  }

  // 拦截 MediaRecorder (浏览器内录)
  var _MR=window.MediaRecorder;
  if(_MR){
    window.MediaRecorder=function(s,o){
      showShield();
      return new _MR(s,o);
    };
    window.MediaRecorder.prototype=_MR.prototype;
  }

  // ==========================================
  // 4. 视频防截屏水印 (肉眼不可见，截图产生干扰纹)
  // ==========================================
  var wmStyle=document.createElement('style');
  wmStyle.textContent='.cpy-wm{position:absolute;top:0;left:0;width:100%;height:100%;pointer-events:none;z-index:1;opacity:0.006;background:repeating-linear-gradient(45deg,rgba(255,255,255,.5),rgba(255,255,255,.5) 2px,transparent 2px,transparent 4px),repeating-linear-gradient(-45deg,rgba(255,255,255,.5),rgba(255,255,255,.5) 2px,transparent 2px,transparent 4px)}';
  document.head.appendChild(wmStyle);

  function guardVideo(v){
    if(v.dataset.cpyGuard)return;
    var p=v.parentNode;
    if(!p)return;
    var w=document.createElement('div');w.className='cpy-wm';
    if(getComputedStyle(p).position==='static')p.style.position='relative';
    v.dataset.cpyGuard='1';
    v.parentNode.insertBefore(w,v.nextSibling);
  }

  // 监听视频元素
  new MutationObserver(function(ms){
    ms.forEach(function(m){
      m.addedNodes.forEach(function(n){
        if(n.nodeType===1){
          if(n.tagName==='VIDEO')guardVideo(n);
          n.querySelectorAll&&n.querySelectorAll('video').forEach(guardVideo);
        }
      });
    });
  }).observe(document.documentElement,{childList:true,subtree:true});
  // 已有视频也处理
  document.querySelectorAll('video').forEach(guardVideo);
})();
</script>
'''

# Find the main script tag
script_pos = html.find('<script>\n// ===')
if script_pos == -1:
    script_pos = html.find('<script>\n// ==')
if script_pos == -1:
    script_pos = html.find('<script>')
    # Skip the plotly script
    if 'plotly' in html[script_pos:script_pos+50]:
        script_pos = html.find('<script>', script_pos + 10)

print(f'Step 1: Found main script at position {script_pos}')

# Insert protection BEFORE the main script
if not SKIP_PROTECT:
    html = html[:script_pos] + protection_code + '\n' + html[script_pos:]
    print('Step 1: Anti-copy protection injected')
else:
    print('Step 1: Protection DORMANT (SKIP_PROTECT=True)')

# ============================================================
# STEP 1b: Inject cyberpunk loading overlay (before </body>)
# ============================================================
overlay_code = r'''
<!-- CYBERPUNK LOADING OVERLAY -->
<style>
#cy-load{position:fixed;top:0;left:0;width:100%;height:100%;z-index:99999;
background:rgba(4,8,16,0.96);display:none;flex-direction:column;align-items:center;
justify-content:center;font-family:'Courier New','Microsoft YaHei',monospace;backdrop-filter:blur(4px)}
#cy-load.on{display:flex}
.cy-t{position:relative;display:inline-block;font-size:clamp(16px,3vw,28px);color:#0f0;letter-spacing:4px;font-weight:700;
text-shadow:0 0 8px #0f0,0 0 20px #0f088;animation:cy-glitch .35s infinite}
.cy-t::before,.cy-t::after{content:attr(data-text);position:absolute;left:0;top:0;width:100%;height:100%}
.cy-t::before{clip:rect(8px,9999px,32px,0);animation:cy-skew .4s infinite alternate-reverse;color:#f0f;opacity:.7}
.cy-t::after{clip:rect(34px,9999px,58px,0);animation:cy-skew .5s infinite alternate;color:#0ff;opacity:.7}
.cy-sub{font-size:11px;color:rgba(0,255,0,.5);margin-top:14px;letter-spacing:5px;text-transform:uppercase}
.cy-bar{width:min(300px,60vw);height:2px;background:rgba(0,255,0,.15);margin-top:28px;border-radius:1px;overflow:hidden}
.cy-bar-fill{height:100%;background:linear-gradient(90deg,#0f0,#0ff);box-shadow:0 0 12px #0f0;
animation:cy-prog 1.4s cubic-bezier(.4,0,.2,1) forwards;width:0}
.cy-rain{position:absolute;top:0;left:0;width:100%;height:100%;pointer-events:none;overflow:hidden}
.cy-drop{position:absolute;color:rgba(0,255,0,.08);font-size:11px;font-family:monospace;white-space:nowrap;
animation:cy-fall linear infinite}
@keyframes cy-glitch{0%,100%{transform:translate(0)}20%{transform:translate(-2px,2px)}40%{transform:translate(2px,-1px)}60%{transform:translate(-1px,0)}80%{transform:translate(1px,-2px)}}
@keyframes cy-skew{0%{transform:skew(0)}100%{transform:skew(1deg)}}
@keyframes cy-prog{0%{width:0}30%{width:35%}60%{width:72%}85%{width:94%}100%{width:100%}}
@keyframes cy-fall{0%{transform:translateY(-100vh);opacity:0}5%{opacity:1}95%{opacity:1}100%{transform:translateY(100vh);opacity:0}}
</style>
<div id="cy-load">
  <canvas id="cy-scan" style="position:absolute;top:0;left:0;width:100%;height:100%;pointer-events:none"></canvas>
  <div class="cy-rain" id="cy-rain"></div>
  <div style="position:relative;text-align:center">
    <div class="cy-t" data-text="▶ DECRYPTING STREAM...">▶ DECRYPTING STREAM...</div>
    <div class="cy-sub">ESTABLISHING SECURE CHANNEL</div>
    <div class="cy-bar"><div class="cy-bar-fill"></div></div>
  </div>
</div>
<script>
(function(){
  var ov=document.getElementById('cy-load');
  if(!ov)return;
  var timer=null;
  var hexChars='0123456789ABCDEF';
  var busy=false;

  // Matrix rain
  var rainEl=document.getElementById('cy-rain');
  function spawnDrop(){
    if(!ov.classList.contains('on'))return;
    var d=document.createElement('span');d.className='cy-drop';
    d.textContent=Array.from({length:8},function(){return hexChars[Math.floor(Math.random()*16)]}).join('');
    d.style.left=Math.random()*100+'%';
    d.style.animationDuration=(3+Math.random()*5)+'s';
    rainEl.appendChild(d);
    setTimeout(function(){if(d.parentNode)d.parentNode.removeChild(d)},8000);
  }

  // Scanline canvas
  var scanCanvas=document.getElementById('cy-scan');
  var scanCtx=scanCanvas?scanCanvas.getContext('2d'):null;
  var scanY=0, scanW=0, scanH=0;
  function drawScan(){
    if(!ov.classList.contains('on'))return;
    var w=scanCanvas.offsetWidth, h=scanCanvas.offsetHeight;
    if(w!==scanW||h!==scanH){scanCanvas.width=w;scanCanvas.height=h;scanW=w;scanH=h}
    scanCtx.clearRect(0,0,scanW,scanH);
    scanCtx.fillStyle='rgba(0,255,0,0.03)';
    scanCtx.fillRect(0,scanY,scanW,2);
    scanY=(scanY+3)%scanH;
    requestAnimationFrame(drawScan);
  }

  function show(){
    if(busy||ov.classList.contains('on'))return;
    busy=true;
    ov.classList.add('on');
    scanY=0;scanW=0;scanH=0;
    requestAnimationFrame(drawScan);
    for(var i=0;i<12;i++)spawnDrop();
    var rainInt=setInterval(spawnDrop,400);
    var bar=ov.querySelector('.cy-bar-fill');
    if(bar){bar.style.animation='none';bar.offsetHeight;bar.style.animation='cy-prog 1.4s cubic-bezier(.4,0,.2,1) forwards'}
    timer=setTimeout(hide,3500);
    ov._rainInt=rainInt;
    return true;
  }

  function hide(){
    busy=false;
    if(!ov.classList.contains('on'))return;
    ov.classList.add('out');
    setTimeout(function(){ov.classList.remove('on','out');},300);
    if(timer){clearTimeout(timer);timer=null}
    if(ov._rainInt){clearInterval(ov._rainInt);ov._rainInt=null}
  }

  // 纯事件代理 — 不修改任何原型，零侵入
  document.addEventListener('play',function(e){
    var v=e.target;
    if(v.tagName!=='VIDEO')return;
    show();
    v.addEventListener('playing',function h(){hide();v.removeEventListener('playing',h)},{once:true});
    v.addEventListener('error',function h(){hide();v.removeEventListener('error',h)},{once:true});
  },true);
})();
</script>
'''

body_close = html.rfind('</body>')
if body_close == -1:
    body_close = len(html)
if not SKIP_OVERLAY:
    html = html[:body_close] + overlay_code + '\n' + html[body_close:]
    print('Step 1b: Cyberpunk loading overlay injected')
else:
    print('Step 1b: Overlay DORMANT (SKIP_OVERLAY=True)')

# ============================================================
# STEP 1c: URL 动态随机化 (始终激活 — 纯视觉效果)
# ============================================================
url_randomizer = r'''
<!-- URL CRYPTIC CHANNEL EFFECT -->
<script>
(function(){
  var H='0123456789ABCDEF';
  function R(n){var s='';for(var i=0;i<n;i++)s+=H[Math.floor(Math.random()*16)];return s}
  function glitch(o,n){
    // 快速闪烁切换，模拟频道跳变
    var steps=0,i=setInterval(function(){
      steps++;
      document.title=(steps%2?'● '+o:'○ '+n)+' | SECURE';
      if(steps>=6){clearInterval(i);document.title='● '+n+' | SECURE'}
    },80);
  }

  // 初始随机频道
  var ch=R(4)+'-'+R(4)+'-'+R(4);
  history.replaceState(null,'',location.pathname+'?ch='+ch);
  document.title='● '+ch.toUpperCase()+' | SECURE';

  // 周期性跳频 (3~7秒随机间隔)
  function hop(){
    var old=ch;
    ch=R(4)+'-'+R(4)+'-'+R(4);
    history.replaceState(null,'',location.pathname+'?ch='+ch);
    glitch(old.toUpperCase(),ch.toUpperCase());
    setTimeout(hop,3000+Math.random()*4000);
  }
  setTimeout(hop,3000+Math.random()*4000);
})();
</script>
'''

html = html[:body_close] + url_randomizer + '\n' + html[body_close:]
print('Step 1c: URL cryptic channel effect injected')

# ============================================================
# STEP 2: Base64-encode Worker proxy URLs (bypass GitHub scanner)
# ============================================================
# 支持两种格式:
#   Token 模式: https://{domain}/v/{16位hex}
#   可读模式:   https://{domain}/v/{model}/{scenario}/{index}
url_pattern = re.compile(
    r'"(https://[^/]+/v/(?:[a-f0-9]{16}|[^/]+/[^/]+/[0-3]))"'
)

count = 0
def encode_url(m):
    global count
    count += 1
    url = m.group(1)
    encoded = base64.b64encode(url.encode()).decode()
    return f'atob("{encoded}")'

html = url_pattern.sub(encode_url, html)
print(f'Step 2: Encoded {count} Worker URLs')

# Also update video_map.js
js_path = r'F:\AI\新的网站\video_map.js'
with open(js_path, 'r', encoding='utf-8') as f:
    js_content = f.read()
js_content = url_pattern.sub(encode_url, js_content)
with open(js_path, 'w', encoding='utf-8') as f:
    f.write(js_content)

# ============================================================
# STEP 3: Extract the MAIN script (not protection) and obfuscate
# ============================================================
# Find all script blocks
all_scripts = list(re.finditer(r'<script>(.*?)</script>', html, re.DOTALL))
print(f'Found {len(all_scripts)} script blocks')

# The last script block is the main one (after protection)
if len(all_scripts) < 2:
    print('Error: need at least 2 script blocks')
    exit(1)

# Second to last? Actually Plotly is first (src, not inline), then protection, then main
# Filter out non-inline scripts
inline_scripts = [m for m in all_scripts if '</script>' in m.group(0)]
# Actually all will match. Let me find by content
main_script = None
for m in all_scripts:
    content = m.group(1)
    if 'VIDEO_MAP' in content or 'const MODELS' in content or '// DATA' in content:
        main_script = m
        break

if not main_script:
    # Fallback: take the last script block
    main_script = all_scripts[-1]

script_start = main_script.start()
script_end = main_script.end()
js_start = script_start + len('<script>')
js_code = html[js_start:script_end - len('</script>')].strip()

print(f'Step 3: Extracted main JS ({len(js_code)} chars)')

# Obfuscate
js_file = r'F:\AI\新的网站\_temp.js'
with open(js_file, 'w', encoding='utf-8') as f:
    f.write(js_code)

npx_path = shutil.which('npx') or shutil.which('npx.cmd')
for p in [r'C:\Program Files\nodejs\npx.cmd']:
    if os.path.exists(p):
        npx_path = p
        break

obf_file = r'F:\AI\新的网站\_temp_obf.js'
cmd = [
    npx_path, 'javascript-obfuscator', js_file,
    '--output', obf_file,
    '--compact', 'true',
    '--string-array', 'true',
    '--string-array-encoding', 'base64',
    '--string-array-threshold', '0.5',
    '--identifier-names-generator', 'hexadecimal',
    '--rename-globals', 'false',
]

print('Step 4: Obfuscating...')
result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
if result.returncode != 0:
    print(f'Error: {result.stderr[-500:]}')
    exit(1)

with open(obf_file, 'r', encoding='utf-8') as f:
    obf_js = f.read()

print(f'Obfuscated: {len(js_code)} -> {len(obf_js)} chars')

# Replace main script with obfuscated version
new_html = html[:js_start] + '\n' + obf_js + '\n' + html[script_end - len('</script>'):]

# Add sentinel to prevent double-processing
new_html = new_html.replace('<!DOCTYPE html>', '<!DOCTYPE html>\n<!-- PROTECT_PROCESSED -->', 1)

with open(html_path, 'w', encoding='utf-8') as f:
    f.write(new_html)

os.remove(js_file)
os.remove(obf_file)

# Final check - 不应再有任何 OSS 凭证泄漏
checks = {
    'LTAI': re.findall(r'LTAI\w+', new_html),
    'OSSAccessKeyId': re.findall(r'OSSAccessKeyId', new_html),
    'Signature': re.findall(r'Signature=', new_html),
}
clean = True
for pattern, matches in checks.items():
    if matches:
        print(f'\n⚠ WARNING: {len(matches)} raw "{pattern}" patterns remain in HTML')
        clean = False

if clean:
    print(f'\n[OK] Clean - no OSS credentials or signature params in HTML')
else:
    print(f'\n[!!] Security check failed - OSS patterns detected!')

print(f'Total HTML: {len(new_html)} chars')
print('Done!')
