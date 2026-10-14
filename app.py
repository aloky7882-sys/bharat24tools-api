from flask import Flask, request, send_file, render_template_string
from flask_cors import CORS
import os
import subprocess
import tempfile
import threading
import time
import shutil
import zipfile
import io
import re
import glob

app = Flask(__name__)
CORS(app)

MAX_FILE_SIZE = 20 * 1024 * 1024
MAX_FILES_COUNT = 20
PROCESSING_TIMEOUT = 120
CLEANUP_DELAY = 30

processing_lock = threading.Lock()

def auto_cleanup_worker():
    while True:
        try:
            time.sleep(60)
            now = time.time()
            cleaned = 0
            for folder in glob.glob('/tmp/tmp*'):
                try:
                    if os.path.getmtime(folder) < now - 120:
                        shutil.rmtree(folder, ignore_errors=True)
                        cleaned += 1
                except:
                    pass
            if cleaned > 0:
                print(f'🧹 Auto-cleanup: {cleaned} folders removed', flush=True)
        except Exception as e:
            print(f'⚠️ Cleanup error: {e}', flush=True)

cleanup_thread = threading.Thread(target=auto_cleanup_worker, daemon=True)
cleanup_thread.start()

@app.before_request
def fast_cleanup():
    try:
        now = time.time()
        for folder in glob.glob('/tmp/tmp*'):
            try:
                if os.path.getmtime(folder) < now - 60:
                    shutil.rmtree(folder, ignore_errors=True)
            except:
                pass
    except:
        pass

HTML = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Bharat24Tools API v9.5</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * { margin:0; padding:0; box-sizing:border-box; font-family:Arial,sans-serif; }
        body { background: linear-gradient(135deg, #0f0f1e, #533483); min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 20px; color: #fff; }
        .container { background: rgba(30,27,75,0.95); padding: 40px; border-radius: 20px; max-width: 700px; width: 100%; border: 1px solid rgba(168,85,247,0.3); }
        h1 { color: #a855f7; margin-bottom: 10px; text-align: center; font-size: 1.5rem; }
        .status-badge { text-align: center; color: #86efac; margin-bottom: 25px; font-weight: 600; }
        .section-title { color: #ffd166; margin: 20px 0 10px; font-size: 1rem; font-weight: 700; }
        .endpoint { background: rgba(99,102,241,0.1); padding: 10px; border-radius: 8px; margin: 5px 0; font-size: 0.85rem; border-left: 3px solid #a855f7; }
        .endpoint code { color: #86efac; background: rgba(0,0,0,0.3); padding: 2px 6px; border-radius: 4px; font-size: 0.8rem; }
        .endpoint .desc { color: #a5b4fc; margin-left: 8px; }
        .footer { text-align: center; margin-top: 20px; color: #a5b4fc; font-size: 0.85rem; }
    </style>
</head>
<body>
    <div class="container">
        <h1>⚡ Bharat24Tools API v9.5</h1>
        <p class="status-badge">Server is running ✅ — 24 Tools Active</p>
        <div class="section-title">📄 PDF Tools (13)</div>
        <div class="endpoint"><code>POST /compress</code><span class="desc">Compress PDF ✅ Extreme Nuclear (50KB min)</span></div>
        <div class="endpoint"><code>POST /pdf-to-jpg</code><span class="desc">PDF to Images</span></div>
        <div class="endpoint"><code>POST /jpg-to-pdf</code><span class="desc">Images to PDF</span></div>
        <div class="endpoint"><code>POST /pdf-to-word</code><span class="desc">PDF to Word</span></div>
        <div class="endpoint"><code>POST /word-to-pdf</code><span class="desc">Word to PDF</span></div>
        <div class="endpoint"><code>POST /excel-to-pdf</code><span class="desc">Excel to PDF</span></div>
        <div class="endpoint"><code>POST /pdf-to-excel</code><span class="desc">PDF to Excel</span></div>
        <div class="endpoint"><code>POST /excel-to-image</code><span class="desc">Excel to Image</span></div>
        <div class="endpoint"><code>POST /merge-pdf</code><span class="desc">Merge PDFs</span></div>
        <div class="endpoint"><code>POST /split-pdf</code><span class="desc">Split PDF</span></div>
        <div class="endpoint"><code>POST /rotate-pdf</code><span class="desc">Rotate PDF</span></div>
        <div class="endpoint"><code>POST /protect-pdf</code><span class="desc">Protect PDF</span></div>
        <div class="endpoint"><code>POST /unlock-pdf</code><span class="desc">Unlock PDF</span></div>
        <div class="section-title">🖼 Image Tools (11)</div>
        <div class="endpoint"><code>POST /heic-to-jpg</code><span class="desc">HEIC to JPG</span></div>
        <div class="endpoint"><code>POST /webp-to-jpg</code><span class="desc">WebP to JPG</span></div>
        <div class="endpoint"><code>POST /image-upscaler</code><span class="desc">AI Image Upscaler</span></div>
        <div class="endpoint"><code>POST /ocr</code><span class="desc">OCR Multi-Language</span></div>
        <div class="endpoint"><code>POST /image-to-sketch</code><span class="desc">Image to Sketch</span></div>
        <div class="endpoint"><code>POST /gif-maker</code><span class="desc">GIF Maker</span></div>
        <div class="endpoint"><code>POST /image-to-word</code><span class="desc">Image to Word ✅ AI + Fallback</span></div>
        <div class="endpoint"><code>POST /image-to-excel</code><span class="desc">Image to Excel ✅ AI + Fallback</span></div>
        <div class="endpoint"><code>POST /pdf-watermark</code><span class="desc">PDF Watermark</span></div>
        <div class="endpoint"><code>POST /pdf-page-delete</code><span class="desc">PDF Page Delete</span></div>
        <p class="footer">Version 9.5 — 24 Tools | Extreme Nuclear Compression</p>
    </div>
</body>
</html>
'''

def cleanup_dir(temp_dir, delay=CLEANUP_DELAY):
    def _cleanup():
        time.sleep(delay)
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except:
            pass
    threading.Thread(target=_cleanup, daemon=True).start()

def validate_file(file, allowed_ext=None, max_size=MAX_FILE_SIZE):
    if not file or file.filename == '':
        return False, 'No file selected'
    if allowed_ext:
        if not any(file.filename.lower().endswith(ext) for ext in allowed_ext):
            return False, f'Only {", ".join(allowed_ext)} files allowed'
    file.seek(0, 2)
    size = file.tell()
    file.seek(0)
    if size > max_size:
        return False, f'File too large. Max {max_size/1024/1024:.1f}MB'
    if size == 0:
        return False, 'File is empty'
    return True, 'OK'

def rebuild_pdf_from_images(input_path, output_path, dpi=50, jpeg_q=15, grayscale=False):
    try:
        img_dir = os.path.join(os.path.dirname(output_path), f'nuclear_{int(time.time()*1000)}')
        os.makedirs(img_dir, exist_ok=True)
        img_pattern = os.path.join(img_dir, 'page-%04d.jpg')
        cmd = ['gs', '-dNOPAUSE', '-dBATCH', '-dQUIET', '-dSAFER', '-sDEVICE=jpeg', f'-r{dpi}', f'-dJPEGQ={jpeg_q}', '-dTextAlphaBits=1', '-dGraphicsAlphaBits=1']
        if grayscale:
            cmd.extend(['-sColorConversionStrategy=Gray', '-dProcessColorModel=/DeviceGray'])
        cmd.extend([f'-sOutputFile={img_pattern}', input_path])
        print(f'  📸 GS convert: dpi={dpi}, q={jpeg_q}, gray={grayscale}', flush=True)
        result = subprocess.run(cmd, check=True, timeout=180, capture_output=True, text=True)
        img_files = sorted([f for f in os.listdir(img_dir) if f.endswith('.jpg')])
        if not img_files:
            print(f'  ⚠️ No images generated. GS stderr: {result.stderr[:200]}', flush=True)
            shutil.rmtree(img_dir, ignore_errors=True)
            return False
        print(f'  📸 Generated {len(img_files)} images', flush=True)
        rebuild_cmd = ['gs', '-dNOPAUSE', '-dBATCH', '-dQUIET', '-dSAFER', '-sDEVICE=pdfwrite', '-dCompatibilityLevel=1.4', '-dPDFSETTINGS=/screen', '-dDetectDuplicateImages=true', '-dCompressFonts=true', '-dSubsetFonts=true', '-dAutoRotatePages=/None', '-dDownsampleColorImages=true', f'-dColorImageResolution={dpi}', '-dDownsampleGrayImages=true', f'-dGrayImageResolution={dpi}', f'-sOutputFile={output_path}'] + [os.path.join(img_dir, f) for f in img_files]
        print(f'  🔨 Rebuilding PDF...', flush=True)
        subprocess.run(rebuild_cmd, check=True, timeout=180, capture_output=True)
        try:
            shutil.rmtree(img_dir, ignore_errors=True)
        except:
            pass
        if os.path.exists(output_path):
            final_size = os.path.getsize(output_path)
            print(f'  ✅ Nuclear done: {final_size/1024:.1f}KB', flush=True)
            return True
        return False
    except subprocess.CalledProcessError as e:
        print(f'  ❌ Nuclear GS error: {e.stderr[:200] if e.stderr else "Unknown"}', flush=True)
        return False
    except Exception as e:
        print(f'  ❌ Nuclear failed: {e}', flush=True)
        return False

def generate_gemini_response(client, prompt_text, img, filename=""):
    import time as _time
    import random
    models_to_try = ['gemini-3.8-flash', 'gemini-2.5-flash', 'gemini-2.0-flash', 'gemini-1.5-flash']
    last_error = None
    for model_name in models_to_try:
        for attempt in range(3):
            try:
                print(f'🤖 Trying {model_name} (attempt {attempt+1}/3) for {filename}...', flush=True)
                response = client.models.generate_content(model=model_name, contents=[prompt_text, img])
                text = response.text.strip()
                print(f'✅ Success with {model_name}', flush=True)
                return text, model_name
            except Exception as e:
                error_str = str(e)
                last_error = error_str
                if '503' in error_str or 'UNAVAILABLE' in error_str or 'high demand' in error_str or 'overloaded' in error_str:
                    wait_time = (2 ** attempt) + random.uniform(0, 1)
                    print(f'⚠️ {model_name} overloaded. Waiting {wait_time:.1f}s...', flush=True)
                    _time.sleep(wait_time)
                    continue
                elif '404' in error_str or 'NOT_FOUND' in error_str or 'no longer available' in error_str:
                    print(f'⚠️ {model_name} not available. Next model...', flush=True)
                    break
                elif '429' in error_str or 'quota' in error_str.lower() or 'RESOURCE_EXHAUSTED' in error_str:
                    print(f'⚠️ {model_name} quota exceeded. Next model...', flush=True)
                    break
                else:
                    print(f'❌ {model_name} error: {error_str[:200]}', flush=True)
                    raise e
        print(f'⚠️ {model_name} failed. Next model...', flush=True)
    raise Exception(f'All AI models are busy. Please try again in 1-2 minutes.')

@app.route('/')
def index():
    return render_template_string(HTML)

@app.route('/health')
def health():
    return {
        'status': 'ok',
        'service': 'bharat24tools-api',
        'version': '9.5',
        'tools': 24,
        'ocr_engine': 'gemini-3.8-flash (with fallback)',
        'sdk': 'google-genai',
        'gemini_configured': bool(os.environ.get('GEMINI_API_KEY', '').strip()),
        'max_files_ocr': 3,
        'compression_range': '50KB - 2GB',
        'fallback_models': ['gemini-3.8-flash', 'gemini-2.5-flash', 'gemini-2.0-flash', 'gemini-1.5-flash'],
        'auto_cleanup': True
    }

# ========== 1. COMPRESS PDF (Extreme Nuclear — iLovePDF level) ==========
@app.route('/compress', methods=['POST'])
def compress():
    if not processing_lock.acquire(timeout=300):
        return 'Server busy. Try again.', 503
    temp_dir = tempfile.mkdtemp()
    try:
        if 'file' not in request.files:
            return 'No file uploaded', 400
        file = request.files['file']
        valid, msg = validate_file(file, allowed_ext=['.pdf'], max_size=20 * 1024 * 1024)
        if not valid:
            return msg, 400

        input_path = os.path.join(temp_dir, 'input.pdf')
        file.save(input_path)
        input_size = os.path.getsize(input_path)

        preset = request.form.get('preset', 'recommended')
        target_bytes = request.form.get('target_bytes', '').strip()
        dpi = request.form.get('dpi', '')
        quality = request.form.get('quality', '')
        grayscale = request.form.get('grayscale', 'no') == 'yes'
        font_subset = request.form.get('font_subset', 'yes') == 'yes'
        compress_fonts = request.form.get('compress_fonts', 'yes') == 'yes'

        try:
            target_size = int(target_bytes) if target_bytes else 0
        except:
            target_size = 0

        MIN_TARGET = 50 * 1024
        if target_size > 0 and target_size < MIN_TARGET:
            print(f'⚠️ Target {target_size/1024:.1f}KB too small. Setting to minimum 50KB.', flush=True)
            target_size = MIN_TARGET

        PRESETS = {
            'extreme': {'dpi': 50, 'quality': 30, 'pdf_settings': '/screen'},
            'recommended': {'dpi': 72, 'quality': 70, 'pdf_settings': '/ebook'},
            'high': {'dpi': 150, 'quality': 85, 'pdf_settings': '/printer'},
        }

        if preset in PRESETS:
            config = PRESETS[preset]
            use_dpi = config['dpi']
            use_quality = config['quality']
            use_pdf_settings = config['pdf_settings']
        else:
            use_dpi = int(dpi) if dpi else 72
            use_quality = int(quality) if quality else 70
            if use_dpi <= 72:
                use_pdf_settings = '/screen'
            elif use_dpi <= 150:
                use_pdf_settings = '/ebook'
            else:
                use_pdf_settings = '/printer'

        jpeg_q = max(10, min(100, use_quality))

        def build_gs_cmd(inp, outp, dpi_val, jpeg_quality, pdf_settings, gray=False):
            cmd = ['gs', '-sDEVICE=pdfwrite', '-dCompatibilityLevel=1.4', f'-dPDFSETTINGS={pdf_settings}', '-dNOPAUSE', '-dQUIET', '-dBATCH', '-dDetectDuplicateImages=true', '-dDownsampleColorImages=true', f'-dColorImageResolution={dpi_val}', '-dDownsampleGrayImages=true', f'-dGrayImageResolution={dpi_val}', '-dDownsampleMonoImages=true', f'-dMonoImageResolution={dpi_val}', f'-dJPEGQ={jpeg_quality}', '-dAutoRotatePages=/None']
            if compress_fonts:
                cmd.append('-dCompressFonts=true')
            if font_subset:
                cmd.append('-dSubsetFonts=true')
            if gray or grayscale:
                cmd.append('-sColorConversionStrategy=Gray')
                cmd.append('-dProcessColorModel=/DeviceGray')
            cmd.append(f'-sOutputFile={outp}')
            cmd.append(inp)
            return cmd

        method_used = preset
        target_hit = ''
        best_output = None
        best_size = input_size
        output_path = os.path.join(temp_dir, 'output.pdf')

        if target_size > 0 and target_size < input_size:
            print(f'🎯 Target: {target_size/1024:.1f}KB (original: {input_size/1024:.1f}KB)', flush=True)

            attempts = [
                (10, 5, '/screen', 'molecular'),
                (15, 8, '/screen', 'nuclear'),
                (20, 10, '/screen', 'super-extreme'),
                (25, 15, '/screen', 'hyper-aggressive'),
                (30, 20, '/screen', 'extreme-plus'),
                (40, 25, '/screen', 'ultra-aggressive'),
                (50, 30, '/screen', 'extreme'),
                (60, 40, '/screen', 'very-aggressive'),
                (72, 50, '/ebook', 'aggressive'),
                (72, 60, '/ebook', 'strong'),
                (72, 70, '/ebook', 'recommended'),
                (100, 75, '/ebook', 'balanced'),
                (120, 80, '/printer', 'high'),
                (150, 85, '/printer', 'very-high'),
                (200, 90, '/prepress', 'max-quality'),
            ]

            for i, (a_dpi, a_q, a_settings, a_label) in enumerate(attempts):
                if best_size <= target_size:
                    break
                attempt_path = os.path.join(temp_dir, f'attempt-{i}.pdf')
                try:
                    cmd = build_gs_cmd(input_path, attempt_path, a_dpi, a_q, a_settings)
                    subprocess.run(cmd, check=True, timeout=60, capture_output=True)
                    if os.path.exists(attempt_path):
                        out_size = os.path.getsize(attempt_path)
                        print(f'  [{i+1}] {a_label}: {out_size/1024:.1f}KB', flush=True)
                        if out_size < best_size:
                            best_output = attempt_path
                            best_size = out_size
                            method_used = a_label
                        if out_size <= target_size:
                            target_hit = f'{out_size/1024:.1f}KB'
                            print(f'  ✅ Target hit with {a_label}!', flush=True)
                            break
                except Exception as e:
                    print(f'  ⚠️ {a_label} failed: {e}', flush=True)
                    continue

            if best_size > target_size:
                print(f'💣 LEVEL 4: Nuclear rebuild — forcing even for text PDFs...', flush=True)
                nuclear_options = [
                    (100, 50, 'nuclear-100dpi'),
                    (75, 40, 'nuclear-75dpi'),
                    (60, 30, 'nuclear-60dpi'),
                    (50, 25, 'nuclear-50dpi'),
                    (40, 20, 'nuclear-40dpi'),
                    (35, 15, 'nuclear-35dpi'),
                    (30, 12, 'nuclear-30dpi'),
                    (25, 10, 'nuclear-25dpi'),
                    (20, 8, 'nuclear-20dpi'),
                    (15, 5, 'nuclear-15dpi'),
                ]
                for n_dpi, n_q, n_label in nuclear_options:
                    if best_size <= target_size:
                        break
                    nuclear_path = os.path.join(temp_dir, f'{n_label}.pdf')
                    try:
                        success = rebuild_pdf_from_images(input_path, nuclear_path, dpi=n_dpi, jpeg_q=n_q, grayscale=False)
                        if success and os.path.exists(nuclear_path):
                            n_size = os.path.getsize(nuclear_path)
                            print(f'  💣 {n_label}: {n_size/1024:.1f}KB', flush=True)
                            if n_size < best_size:
                                if best_output and os.path.exists(best_output) and best_output != nuclear_path:
                                    try: os.remove(best_output)
                                    except: pass
                                best_output = nuclear_path
                                best_size = n_size
                                method_used = n_label
                            if n_size <= target_size:
                                target_hit = f'{n_size/1024:.1f}KB'
                                print(f'  ✅ TARGET HIT with {n_label}!', flush=True)
                                break
                        else:
                            print(f'  ⚠️ {n_label} failed silently', flush=True)
                    except Exception as e:
                        print(f'  ⚠️ {n_label} exception: {e}', flush=True)
                        continue

            if best_size > target_size:
                print(f'⚫ LEVEL 5: Grayscale nuclear — B&W conversion...', flush=True)
                gray_options = [
                    (100, 40, 'gray-100dpi'),
                    (75, 30, 'gray-75dpi'),
                    (50, 25, 'gray-50dpi'),
                    (40, 20, 'gray-40dpi'),
                    (30, 15, 'gray-30dpi'),
                    (25, 10, 'gray-25dpi'),
                    (20, 8, 'gray-20dpi'),
                    (15, 5, 'gray-15dpi'),
                    (10, 3, 'gray-10dpi'),
                ]
                for g_dpi, g_q, g_label in gray_options:
                    if best_size <= target_size:
                        break
                    gray_path = os.path.join(temp_dir, f'{g_label}.pdf')
                    try:
                        success = rebuild_pdf_from_images(input_path, gray_path, dpi=g_dpi, jpeg_q=g_q, grayscale=True)
                        if success and os.path.exists(gray_path):
                            g_size = os.path.getsize(gray_path)
                            print(f'  ⚫ {g_label}: {g_size/1024:.1f}KB', flush=True)
                            if g_size < best_size:
                                if best_output and os.path.exists(best_output) and best_output != gray_path:
                                    try: os.remove(best_output)
                                    except: pass
                                best_output = gray_path
                                best_size = g_size
                                method_used = g_label
                            if g_size <= target_size:
                                target_hit = f'{g_size/1024:.1f}KB'
                                print(f'  ✅ TARGET HIT with {g_label}!', flush=True)
                                break
                    except Exception as e:
                        print(f'  ⚠️ {g_label} exception: {e}', flush=True)
                        continue

            if best_output and os.path.exists(best_output):
                shutil.copy(best_output, output_path)
                if target_hit == '':
                    target_hit = f'best-effort ({best_size/1024:.1f}KB)'
                    print(f'  ⚠️ Target not fully hit. Minimum possible: {best_size/1024:.1f}KB', flush=True)
            else:
                return 'Compression failed', 500

        else:
            output_path = os.path.join(temp_dir, 'output.pdf')
            cmd = build_gs_cmd(input_path, output_path, use_dpi, jpeg_q, use_pdf_settings)
            print(f'🔧 Compression: preset={preset}, dpi={use_dpi}, quality={jpeg_q}, gray={grayscale}', flush=True)
            subprocess.run(cmd, check=True, timeout=PROCESSING_TIMEOUT, capture_output=True)
            if not os.path.exists(output_path):
                return 'Compression failed', 500

        output_size = os.path.getsize(output_path)
        saved = ((input_size - output_size) / input_size * 100) if input_size > 0 else 0

        print(f'✅ Final: {input_size/1024:.1f}KB → {output_size/1024:.1f}KB ({saved:.1f}% saved) | method={method_used} | target={target_hit}', flush=True)

        response = send_file(output_path, mimetype='application/pdf', as_attachment=True, download_name='compressed.pdf')
        response.headers['X-Compression-Method'] = method_used
        response.headers['X-Target-Hit'] = target_hit
        response.headers['X-Original-Size'] = str(input_size)
        response.headers['X-Final-Size'] = str(output_size)
        response.headers['Access-Control-Expose-Headers'] = 'X-Compression-Method, X-Target-Hit, X-Original-Size, X-Final-Size'
        return response
    except subprocess.TimeoutExpired:
        return 'Timeout: File too complex', 500
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f'❌ Compress error: {e}', flush=True)
        return f'Error: {str(e)}', 500
    finally:
        processing_lock.release()
        cleanup_dir(temp_dir)

# ========== 2. PDF TO JPG ==========
@app.route('/pdf-to-jpg', methods=['POST'])
def pdf_to_jpg():
    if not processing_lock.acquire(timeout=300):
        return 'Server busy. Try again.', 503
    temp_dir = tempfile.mkdtemp()
    try:
        if 'file' not in request.files:
            return 'No file uploaded', 400
        file = request.files['file']
        valid, msg = validate_file(file, allowed_ext=['.pdf'])
        if not valid:
            return msg, 400
        input_path = os.path.join(temp_dir, 'input.pdf')
        file.save(input_path)
        output_pattern = os.path.join(temp_dir, 'page-%03d.jpg')
        subprocess.run(['gs', '-dNOPAUSE', '-dBATCH', '-dQUIET', '-sDEVICE=jpeg', '-r150', '-dJPEGQ=90', f'-sOutputFile={output_pattern}', input_path], check=True, timeout=PROCESSING_TIMEOUT, capture_output=True)
        jpg_files = sorted([f for f in os.listdir(temp_dir) if f.startswith('page-') and f.endswith('.jpg')])
        if not jpg_files:
            return 'No pages converted', 500
        if len(jpg_files) == 1:
            return send_file(os.path.join(temp_dir, jpg_files[0]), mimetype='image/jpeg', as_attachment=True, download_name='page-1.jpg')
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for jpg in jpg_files:
                zf.write(os.path.join(temp_dir, jpg), jpg)
        zip_buffer.seek(0)
        return send_file(zip_buffer, mimetype='application/zip', as_attachment=True, download_name='pdf-pages.zip')
    except subprocess.TimeoutExpired:
        return 'Timeout: PDF too large', 500
    except Exception as e:
        print(f'❌ PDF to JPG error: {e}', flush=True)
        return f'Error: {str(e)}', 500
    finally:
        processing_lock.release()
        cleanup_dir(temp_dir)

# ========== 3. JPG TO PDF ==========
@app.route('/jpg-to-pdf', methods=['POST'])
def jpg_to_pdf():
    if not processing_lock.acquire(timeout=300):
        return 'Server busy. Try again.', 503
    temp_dir = tempfile.mkdtemp()
    try:
        if 'files' not in request.files:
            return 'No files uploaded', 400
        files = request.files.getlist('files')
        if len(files) > MAX_FILES_COUNT:
            return f'Max {MAX_FILES_COUNT} files allowed', 400
        if not files:
            return 'No files selected', 400
        from PIL import Image
        images = []
        for i, file in enumerate(files):
            valid, msg = validate_file(file, allowed_ext=['.jpg', '.jpeg', '.png'])
            if not valid:
                return f'File {i+1}: {msg}', 400
            path = os.path.join(temp_dir, f'img-{i:03d}{os.path.splitext(file.filename)[1].lower()}')
            file.save(path)
            img = Image.open(path)
            if img.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'RGBA':
                    background.paste(img, mask=img.split()[-1])
                else:
                    background.paste(img)
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            images.append(img)
        if not images:
            return 'No valid images', 400
        output_path = os.path.join(temp_dir, 'output.pdf')
        images[0].save(output_path, 'PDF', save_all=True, append_images=images[1:], resolution=100.0)
        if not os.path.exists(output_path):
            return 'PDF creation failed', 500
        return send_file(output_path, mimetype='application/pdf', as_attachment=True, download_name='images.pdf')
    except Exception as e:
        print(f'❌ JPG to PDF error: {e}', flush=True)
        return f'Error: {str(e)}', 500
    finally:
        processing_lock.release()
        cleanup_dir(temp_dir)

# ========== 4. PDF TO WORD ==========
@app.route('/pdf-to-word', methods=['POST'])
def pdf_to_word():
    if not processing_lock.acquire(timeout=300):
        return 'Server busy. Try again.', 503
    temp_dir = tempfile.mkdtemp()
    try:
        if 'file' not in request.files:
            return 'No file uploaded', 400
        file = request.files['file']
        valid, msg = validate_file(file, allowed_ext=['.pdf'])
        if not valid:
            return msg, 400
        input_path = os.path.join(temp_dir, 'input.pdf')
        output_path = os.path.join(temp_dir, 'output.docx')
        txt_path = os.path.join(temp_dir, 'extracted.txt')
        file.save(input_path)
        subprocess.run(['gs', '-sDEVICE=txtwrite', '-dNOPAUSE', '-dBATCH', '-dQUIET', f'-sOutputFile={txt_path}', input_path], check=True, timeout=PROCESSING_TIMEOUT, capture_output=True)
        if not os.path.exists(txt_path):
            return 'Text extraction failed', 500
        with open(txt_path, 'r', encoding='utf-8', errors='ignore') as f:
            text = f.read()
        if not text.strip():
            return 'No text found', 400
        from docx import Document
        from docx.shared import Pt, RGBColor
        doc = Document()
        heading = doc.add_heading('Converted from PDF', 0)
        heading.runs[0].font.color.rgb = RGBColor(0xa8, 0x55, 0xf7)
        for line in text.split('\n'):
            if line.strip():
                doc.add_paragraph(line)
        doc.add_paragraph('')
        foot = doc.add_paragraph('Created with Bharat24Tools')
        foot.runs[0].italic = True
        foot.runs[0].font.size = Pt(9)
        doc.save(output_path)
        return send_file(output_path, mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document', as_attachment=True, download_name='converted.docx')
    except Exception as e:
        print(f'❌ PDF to Word error: {e}', flush=True)
        return f'Error: {str(e)}', 500
    finally:
        processing_lock.release()
        cleanup_dir(temp_dir)

# ========== 5. WORD TO PDF ==========
@app.route('/word-to-pdf', methods=['POST'])
def word_to_pdf():
    if not processing_lock.acquire(timeout=300):
        return 'Server busy. Try again.', 503
    temp_dir = tempfile.mkdtemp()
    try:
        if 'file' not in request.files:
            return 'No file uploaded', 400
        file = request.files['file']
        valid, msg = validate_file(file, allowed_ext=['.docx'])
        if not valid:
            return msg, 400
        input_path = os.path.join(temp_dir, 'input.docx')
        output_path = os.path.join(temp_dir, 'output.pdf')
        file.save(input_path)
        from docx import Document
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib.enums import TA_LEFT
        doc = Document(input_path)
        pdf = SimpleDocTemplate(output_path, pagesize=A4, leftMargin=20*mm, rightMargin=20*mm, topMargin=20*mm, bottomMargin=20*mm)
        styles = getSampleStyleSheet()
        normal_style = ParagraphStyle('CustomNormal', parent=styles['Normal'], fontSize=11, leading=15, alignment=TA_LEFT)
        heading_style = ParagraphStyle('CustomHeading', parent=styles['Heading1'], fontSize=16, leading=20, spaceAfter=10, textColor='#a855f7')
        story = []
        for para in doc.paragraphs:
            text = para.text.strip()
            if not text:
                story.append(Spacer(1, 6))
                continue
            safe_text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            if para.style.name.startswith('Heading'):
                story.append(Paragraph(safe_text, heading_style))
            else:
                story.append(Paragraph(safe_text, normal_style))
                story.append(Spacer(1, 4))
        pdf.build(story)
        return send_file(output_path, mimetype='application/pdf', as_attachment=True, download_name='converted.pdf')
    except Exception as e:
        print(f'❌ Word to PDF error: {e}', flush=True)
        return f'Error: {str(e)}', 500
    finally:
        processing_lock.release()
        cleanup_dir(temp_dir)

# ========== 6. EXCEL TO PDF ==========
@app.route('/excel-to-pdf', methods=['POST'])
def excel_to_pdf():
    if not processing_lock.acquire(timeout=300):
        return 'Server busy. Try again.', 503
    temp_dir = tempfile.mkdtemp()
    try:
        if 'file' not in request.files:
            return 'No file uploaded', 400
        file = request.files['file']
        valid, msg = validate_file(file, allowed_ext=['.xlsx', '.xls'], max_size=15 * 1024 * 1024)
        if not valid:
            return msg, 400
        input_path = os.path.join(temp_dir, 'input.xlsx')
        output_path = os.path.join(temp_dir, 'output.pdf')
        file.save(input_path)
        from openpyxl import load_workbook
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
        from datetime import datetime

        def clean_cell(value):
            if value is None: return ''
            try:
                s = str(value)
                if s.lower() == 'nan' or s.lower() == 'none': return ''
                return s.strip()
            except: return ''

        def detect_column_type(values):
            non_empty = [v for v in values if v and str(v).strip()]
            if not non_empty: return 'text'
            num_count = 0
            for v in non_empty:
                clean = str(v).replace(',', '').replace('₹', '').replace('$', '').replace('%', '').strip()
                try:
                    float(clean); num_count += 1
                except: pass
            if num_count / len(non_empty) > 0.7: return 'number'
            return 'text'

        def calc_widths(table_data, max_cols=15):
            if not table_data: return []
            widths = []
            for col_idx in range(min(len(table_data[0]), max_cols)):
                max_len = 0
                for row in table_data[:100]:
                    if col_idx < len(row):
                        max_len = max(max_len, len(str(row[col_idx]) if row[col_idx] else ''))
                if max_len <= 5: w = 20 * mm
                elif max_len <= 10: w = 28 * mm
                elif max_len <= 20: w = 38 * mm
                elif max_len <= 35: w = 50 * mm
                else: w = 65 * mm
                widths.append(w)
            return widths

        def smart_truncate(text, max_len=50):
            text = str(text) if text is not None else ''
            return text[:max_len - 3] + '...' if len(text) > max_len else text

        def esc(text):
            return str(text).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

        try:
            wb = load_workbook(input_path, data_only=True, read_only=True)
        except:
            try:
                wb = load_workbook(input_path, data_only=True, read_only=False)
            except:
                return 'Cannot read this Excel file.', 400

        pdf = SimpleDocTemplate(output_path, pagesize=landscape(A4), leftMargin=10*mm, rightMargin=10*mm, topMargin=25*mm, bottomMargin=18*mm)
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle('T', parent=styles['Heading1'], fontSize=18, textColor=colors.HexColor('#a855f7'), fontName='Helvetica-Bold')
        sheet_style = ParagraphStyle('S', parent=styles['Heading2'], fontSize=13, textColor=colors.HexColor('#533483'), fontName='Helvetica-Bold')

        story = [Paragraph('⚡ Bharat24Tools', title_style), Spacer(1, 6)]
        total_sheets = len(wb.sheetnames)
        total_rows = 0
        MAX_COLS = 15

        for s_idx, s_name in enumerate(wb.sheetnames):
            try:
                sheet = wb[s_name]
            except: continue
            raw_data = []
            try:
                for row in sheet.iter_rows(values_only=True):
                    if row is None: continue
                    cleaned = [clean_cell(c) for c in row[:MAX_COLS]]
                    if any(cleaned): raw_data.append(cleaned)
            except: continue
            if not raw_data: continue
            if total_sheets > 1:
                story.append(Paragraph(f'📄 Sheet {s_idx + 1}: {esc(s_name)}', sheet_style))
            else:
                story.append(Paragraph(f'📄 Sheet: {esc(s_name)}', sheet_style))
            display_data = []
            for row in raw_data:
                d = [smart_truncate(c, 50) for c in row]
                while len(d) < MAX_COLS: d.append('')
                display_data.append(d)
            col_widths = calc_widths(display_data)
            tbl = Table(display_data, colWidths=col_widths, repeatRows=1)
            tbl.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#a855f7')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#d1d5db')),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f5ff')]),
            ]))
            story.append(tbl)
            story.append(Spacer(1, 8))
            total_rows += len(display_data) - 1
            if s_idx < total_sheets - 1:
                story.append(PageBreak())
        try: wb.close()
        except: pass
        if total_rows == 0:
            return 'Excel file is empty', 400
        pdf.build(story)
        return send_file(output_path, mimetype='application/pdf', as_attachment=True, download_name=f'Bharat24Tools_{file.filename.rsplit(".", 1)[0]}.pdf')
    except Exception as e:
        import traceback
        traceback.print_exc()
        return f'Error: {str(e)}', 500
    finally:
        processing_lock.release()
        cleanup_dir(temp_dir)

# ========== 7. PDF TO EXCEL ==========
@app.route('/pdf-to-excel', methods=['POST'])
def pdf_to_excel():
    if not processing_lock.acquire(timeout=300):
        return 'Server busy. Try again.', 503
    temp_dir = tempfile.mkdtemp()
    try:
        if 'file' not in request.files:
            return 'No file uploaded', 400
        file = request.files['file']
        valid, msg = validate_file(file, allowed_ext=['.pdf'])
        if not valid: return msg, 400
        input_path = os.path.join(temp_dir, 'input.pdf')
        txt_path = os.path.join(temp_dir, 'extracted.txt')
        output_path = os.path.join(temp_dir, 'output.xlsx')
        file.save(input_path)
        subprocess.run(['gs', '-sDEVICE=txtwrite', '-dNOPAUSE', '-dBATCH', '-dQUIET', f'-sOutputFile={txt_path}', input_path], check=True, timeout=PROCESSING_TIMEOUT, capture_output=True)
        if not os.path.exists(txt_path): return 'Text extraction failed', 500
        with open(txt_path, 'r', encoding='utf-8', errors='ignore') as f: text = f.read()
        if not text.strip(): return 'No text found in PDF', 400
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment
        wb = Workbook()
        ws = wb.active
        ws.title = 'PDF Content'
        ws['A1'] = 'Extracted from PDF'
        ws['A1'].font = Font(bold=True, size=14, color='FFFFFF')
        ws['A1'].fill = PatternFill('solid', fgColor='A855F7')
        ws.merge_cells('A1:C1')
        row = 3
        for line in text.split('\n'):
            if line.strip():
                ws.cell(row=row, column=1, value=line.strip())
                row += 1
        ws.column_dimensions['A'].width = 100
        wb.save(output_path)
        return send_file(output_path, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', as_attachment=True, download_name='converted.xlsx')
    except Exception as e:
        print(f'❌ PDF to Excel error: {e}', flush=True)
        return f'Error: {str(e)}', 500
    finally:
        processing_lock.release()
        cleanup_dir(temp_dir)

# ========== 8. EXCEL TO IMAGE ==========
@app.route('/excel-to-image', methods=['POST'])
def excel_to_image():
    if not processing_lock.acquire(timeout=300):
        return 'Server busy. Try again.', 503
    temp_dir = tempfile.mkdtemp()
    try:
        if 'file' not in request.files:
            return 'No file uploaded', 400
        file = request.files['file']
        valid, msg = validate_file(file, allowed_ext=['.xlsx', '.xls'])
        if not valid: return msg, 400
        input_path = os.path.join(temp_dir, 'input.xlsx')
        output_path = os.path.join(temp_dir, 'output.png')
        file.save(input_path)
        from openpyxl import load_workbook
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        wb = load_workbook(input_path, data_only=True)
        sheet = wb.active
        data = []
        for row in sheet.iter_rows(values_only=True):
            rd = [str(c) if c is not None else '' for c in row]
            if any(rd): data.append(rd)
        if not data: return 'Excel file is empty', 400
        data = data[:30]
        cols = len(data[0]) if data else 0
        fig, ax = plt.subplots(figsize=(max(8, cols * 2), max(4, len(data) * 0.5)))
        ax.axis('tight'); ax.axis('off')
        tbl = ax.table(cellText=data, loc='center', cellLoc='left')
        tbl.auto_set_font_size(False); tbl.set_fontsize(9); tbl.scale(1, 1.5)
        for i in range(cols):
            cell = tbl[(0, i)]
            cell.set_facecolor('#a855f7')
            cell.set_text_props(color='white', weight='bold')
        plt.title('Excel Content — Bharat24Tools', fontsize=14, fontweight='bold', pad=20)
        plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
        plt.close()
        return send_file(output_path, mimetype='image/png', as_attachment=True, download_name='excel-image.png')
    except Exception as e:
        print(f'❌ Excel to Image error: {e}', flush=True)
        return f'Error: {str(e)}', 500
    finally:
        processing_lock.release()
        cleanup_dir(temp_dir)

# ========== 9. MERGE PDF ==========
@app.route('/merge-pdf', methods=['POST'])
def merge_pdf():
    if not processing_lock.acquire(timeout=300):
        return 'Server busy. Try again.', 503
    temp_dir = tempfile.mkdtemp()
    try:
        if 'files' not in request.files:
            return 'No files uploaded', 400
        files = request.files.getlist('files')
        if len(files) < 2: return 'At least 2 PDFs required', 400
        if len(files) > MAX_FILES_COUNT: return f'Max {MAX_FILES_COUNT} files allowed', 400
        pdf_paths = []
        for i, file in enumerate(files):
            valid, msg = validate_file(file, allowed_ext=['.pdf'])
            if not valid: return f'File {i+1}: {msg}', 400
            path = os.path.join(temp_dir, f'input-{i:03d}.pdf')
            file.save(path); pdf_paths.append(path)
        output_path = os.path.join(temp_dir, 'merged.pdf')
        cmd = ['gs', '-sDEVICE=pdfwrite', '-dNOPAUSE', '-dBATCH', '-dQUIET', '-dCompatibilityLevel=1.4', f'-sOutputFile={output_path}'] + pdf_paths
        subprocess.run(cmd, check=True, timeout=PROCESSING_TIMEOUT, capture_output=True)
        if not os.path.exists(output_path): return 'Merge failed', 500
        return send_file(output_path, mimetype='application/pdf', as_attachment=True, download_name='merged.pdf')
    except Exception as e:
        print(f'❌ Merge error: {e}', flush=True)
        return f'Error: {str(e)}', 500
    finally:
        processing_lock.release()
        cleanup_dir(temp_dir)

# ========== 10. SPLIT PDF ==========
@app.route('/split-pdf', methods=['POST'])
def split_pdf():
    if not processing_lock.acquire(timeout=300):
        return 'Server busy. Try again.', 503
    temp_dir = tempfile.mkdtemp()
    try:
        if 'file' not in request.files:
            return 'No file uploaded', 400
        file = request.files['file']
        valid, msg = validate_file(file, allowed_ext=['.pdf'])
        if not valid: return msg, 400
        input_path = os.path.join(temp_dir, 'input.pdf')
        file.save(input_path)
        try:
            result = subprocess.run(['qpdf', '--show-npages', input_path], capture_output=True, text=True, timeout=30)
            total_pages = int(result.stdout.strip())
        except: total_pages = 0
        if total_pages == 0: return 'Cannot read PDF page count', 400
        output_pattern = os.path.join(temp_dir, 'page-%03d.pdf')
        cmd = ['qpdf', '--split-pages', '1', input_path, output_pattern]
        subprocess.run(cmd, check=True, timeout=PROCESSING_TIMEOUT, capture_output=True)
        pdf_files = sorted([f for f in os.listdir(temp_dir) if f.startswith('page-') and f.endswith('.pdf')])
        if not pdf_files: return 'Split failed', 500
        if len(pdf_files) == 1:
            return send_file(os.path.join(temp_dir, pdf_files[0]), mimetype='application/pdf', as_attachment=True, download_name='page-1.pdf')
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for pdf in pdf_files: zf.write(os.path.join(temp_dir, pdf), pdf)
        zip_buffer.seek(0)
        return send_file(zip_buffer, mimetype='application/zip', as_attachment=True, download_name='split-pages.zip')
    except Exception as e:
        print(f'❌ Split error: {e}', flush=True)
        return f'Error: {str(e)}', 500
    finally:
        processing_lock.release()
        cleanup_dir(temp_dir)

# ========== 11. ROTATE PDF ==========
@app.route('/rotate-pdf', methods=['POST'])
def rotate_pdf():
    if not processing_lock.acquire(timeout=300):
        return 'Server busy. Try again.', 503
    temp_dir = tempfile.mkdtemp()
    try:
        if 'file' not in request.files:
            return 'No file uploaded', 400
        file = request.files['file']
        valid, msg = validate_file(file, allowed_ext=['.pdf'])
        if not valid: return msg, 400
        angle = request.form.get('angle', '90')
        try:
            angle = int(angle)
            if angle not in [90, 180, 270]: angle = 90
        except: angle = 90
        input_path = os.path.join(temp_dir, 'input.pdf')
        output_path = os.path.join(temp_dir, 'rotated.pdf')
        file.save(input_path)
        try:
            result = subprocess.run(['qpdf', '--show-npages', input_path], capture_output=True, text=True, timeout=30)
            total_pages = int(result.stdout.strip())
        except: total_pages = 0
        if total_pages == 0: return 'Cannot read PDF page count', 400
        rotate_spec = f'+{angle}:1-{total_pages}'
        subprocess.run(['qpdf', f'--rotate={rotate_spec}', input_path, output_path], check=True, timeout=PROCESSING_TIMEOUT, capture_output=True)
        if not os.path.exists(output_path): return 'Rotation failed', 500
        return send_file(output_path, mimetype='application/pdf', as_attachment=True, download_name='rotated.pdf')
    except Exception as e:
        print(f'❌ Rotate error: {e}', flush=True)
        return f'Error: {str(e)}', 500
    finally:
        processing_lock.release()
        cleanup_dir(temp_dir)

# ========== 12. PROTECT PDF ==========
@app.route('/protect-pdf', methods=['POST'])
def protect_pdf():
    if not processing_lock.acquire(timeout=300):
        return 'Server busy. Try again.', 503
    temp_dir = tempfile.mkdtemp()
    try:
        if 'file' not in request.files:
            return 'No file uploaded', 400
        file = request.files['file']
        valid, msg = validate_file(file, allowed_ext=['.pdf'])
        if not valid: return msg, 400
        password = request.form.get('password', '').strip()
        if not password or len(password) < 4:
            return 'Password must be at least 4 characters', 400
        input_path = os.path.join(temp_dir, 'input.pdf')
        output_path = os.path.join(temp_dir, 'protected.pdf')
        file.save(input_path)
        subprocess.run(['qpdf', '--encrypt', password, password, '256', '--', input_path, output_path], check=True, timeout=PROCESSING_TIMEOUT, capture_output=True)
        if not os.path.exists(output_path): return 'Encryption failed', 500
        return send_file(output_path, mimetype='application/pdf', as_attachment=True, download_name='protected.pdf')
    except Exception as e:
        print(f'❌ Protect error: {e}', flush=True)
        return f'Error: {str(e)}', 500
    finally:
        processing_lock.release()
        cleanup_dir(temp_dir)

# ========== 13. UNLOCK PDF ==========
@app.route('/unlock-pdf', methods=['POST'])
def unlock_pdf():
    if not processing_lock.acquire(timeout=300):
        return 'Server busy. Try again.', 503
    temp_dir = tempfile.mkdtemp()
    try:
        if 'file' not in request.files:
            return 'No file uploaded', 400
        file = request.files['file']
        valid, msg = validate_file(file, allowed_ext=['.pdf'])
        if not valid: return msg, 400
        password = request.form.get('password', '').strip()
        if not password: return 'Password required', 400
        input_path = os.path.join(temp_dir, 'input.pdf')
        output_path = os.path.join(temp_dir, 'unlocked.pdf')
        file.save(input_path)
        subprocess.run(['qpdf', f'--password={password}', '--decrypt', input_path, output_path], check=True, timeout=PROCESSING_TIMEOUT, capture_output=True)
        if not os.path.exists(output_path): return 'Unlock failed', 500
        return send_file(output_path, mimetype='application/pdf', as_attachment=True, download_name='unlocked.pdf')
    except Exception as e:
        print(f'❌ Unlock error: {e}', flush=True)
        return f'Error: {str(e)}', 500
    finally:
        processing_lock.release()
        cleanup_dir(temp_dir)

# ========== 14. HEIC TO JPG ==========
@app.route('/heic-to-jpg', methods=['POST'])
def heic_to_jpg():
    if not processing_lock.acquire(timeout=300):
        return 'Server busy. Try again.', 503
    temp_dir = tempfile.mkdtemp()
    try:
        if 'file' not in request.files:
            return 'No file uploaded', 400
        file = request.files['file']
        valid, msg = validate_file(file, allowed_ext=['.heic', '.heif'])
        if not valid: return msg, 400
        input_path = os.path.join(temp_dir, 'input.heic')
        output_path = os.path.join(temp_dir, 'output.jpg')
        file.save(input_path)
        from pillow_heif import register_heif_opener
        from PIL import Image
        register_heif_opener()
        img = Image.open(input_path)
        if img.mode != 'RGB': img = img.convert('RGB')
        img.save(output_path, 'JPEG', quality=90)
        return send_file(output_path, mimetype='image/jpeg', as_attachment=True, download_name='converted.jpg')
    except Exception as e:
        print(f'❌ HEIC error: {e}', flush=True)
        return f'Error: {str(e)}', 500
    finally:
        processing_lock.release()
        cleanup_dir(temp_dir)

# ========== 15. WEBP TO JPG ==========
@app.route('/webp-to-jpg', methods=['POST'])
def webp_to_jpg():
    if not processing_lock.acquire(timeout=300):
        return 'Server busy. Try again.', 503
    temp_dir = tempfile.mkdtemp()
    try:
        if 'file' not in request.files:
            return 'No file uploaded', 400
        file = request.files['file']
        valid, msg = validate_file(file, allowed_ext=['.webp'])
        if not valid: return msg, 400
        input_path = os.path.join(temp_dir, 'input.webp')
        output_path = os.path.join(temp_dir, 'output.jpg')
        file.save(input_path)
        from PIL import Image
        img = Image.open(input_path)
        if img.mode in ('RGBA', 'LA', 'P'):
            bg = Image.new('RGB', img.size, (255, 255, 255))
            bg.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
            img = bg
        elif img.mode != 'RGB':
            img = img.convert('RGB')
        img.save(output_path, 'JPEG', quality=92)
        return send_file(output_path, mimetype='image/jpeg', as_attachment=True, download_name='converted.jpg')
    except Exception as e:
        print(f'❌ WebP error: {e}', flush=True)
        return f'Error: {str(e)}', 500
    finally:
        processing_lock.release()
        cleanup_dir(temp_dir)

# ========== 16. IMAGE UPSCALER ==========
@app.route('/image-upscaler', methods=['POST'])
def image_upscaler():
    if not processing_lock.acquire(timeout=300):
        return 'Server busy. Try again.', 503
    temp_dir = tempfile.mkdtemp()
    try:
        if 'file' not in request.files:
            return 'No file uploaded', 400
        file = request.files['file']
        valid, msg = validate_file(file, allowed_ext=['.jpg', '.jpeg', '.png', '.webp'])
        if not valid: return msg, 400
        scale = int(request.form.get('scale', '2'))
        if scale not in [2, 3, 4]: scale = 2
        input_path = os.path.join(temp_dir, 'input.png')
        output_path = os.path.join(temp_dir, 'output.png')
        file.save(input_path)
        from PIL import Image
        img = Image.open(input_path)
        new_size = (img.width * scale, img.height * scale)
        upscaled = img.resize(new_size, Image.LANCZOS)
        upscaled.save(output_path, 'PNG')
        return send_file(output_path, mimetype='image/png', as_attachment=True, download_name='upscaled.png')
    except Exception as e:
        print(f'❌ Upscaler error: {e}', flush=True)
        return f'Error: {str(e)}', 500
    finally:
        processing_lock.release()
        cleanup_dir(temp_dir)

# ========== 17. OCR MULTILINGUAL ==========
@app.route('/ocr', methods=['POST'])
def ocr():
    if not processing_lock.acquire(timeout=300):
        return 'Server busy. Try again.', 503
    temp_dir = tempfile.mkdtemp()
    try:
        if 'file' not in request.files:
            return 'No file uploaded', 400
        file = request.files['file']
        valid, msg = validate_file(file, allowed_ext=['.jpg', '.jpeg', '.png', '.webp'])
        if not valid: return msg, 400
        lang = request.form.get('lang', 'eng')
        input_path = os.path.join(temp_dir, 'input.png')
        file.save(input_path)
        import pytesseract
        from PIL import Image
        pytesseract.pytesseract.tesseract_cmd = r'/usr/bin/tesseract'
        img = Image.open(input_path)
        text = pytesseract.image_to_string(img, lang=lang)
        output_path = os.path.join(temp_dir, 'output.txt')
        with open(output_path, 'w', encoding='utf-8') as f: f.write(text)
        return send_file(output_path, mimetype='text/plain', as_attachment=True, download_name='extracted.txt')
    except Exception as e:
        print(f'❌ OCR error: {e}', flush=True)
        return f'Error: {str(e)}', 500
    finally:
        processing_lock.release()
        cleanup_dir(temp_dir)

# ========== 18. AVIF TO JPG ==========
@app.route('/avif-to-jpg', methods=['POST'])
def avif_to_jpg():
    return 'Please use client-side version', 400

# ========== 19. IMAGE TO SKETCH ==========
@app.route('/image-to-sketch', methods=['POST'])
def image_to_sketch():
    if not processing_lock.acquire(timeout=300):
        return 'Server busy. Try again.', 503
    temp_dir = tempfile.mkdtemp()
    try:
        if 'file' not in request.files:
            return 'No file uploaded', 400
        file = request.files['file']
        valid, msg = validate_file(file, allowed_ext=['.jpg', '.jpeg', '.png', '.webp'])
        if not valid: return msg, 400
        input_path = os.path.join(temp_dir, 'input.png')
        output_path = os.path.join(temp_dir, 'output.png')
        file.save(input_path)
        import cv2
        import numpy as np
        img = cv2.imread(input_path)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        inverted = cv2.bitwise_not(gray)
        blurred = cv2.GaussianBlur(inverted, (21, 21), 0)
        inverted_blur = cv2.bitwise_not(blurred)
        sketch = cv2.divide(gray, inverted_blur, scale=256.0)
        cv2.imwrite(output_path, sketch)
        return send_file(output_path, mimetype='image/png', as_attachment=True, download_name='sketch.png')
    except Exception as e:
        print(f'❌ Sketch error: {e}', flush=True)
        return f'Error: {str(e)}', 500
    finally:
        processing_lock.release()
        cleanup_dir(temp_dir)

# ========== 20. GIF MAKER ==========
@app.route('/gif-maker', methods=['POST'])
def gif_maker():
    if not processing_lock.acquire(timeout=300):
        return 'Server busy. Try again.', 503
    temp_dir = tempfile.mkdtemp()
    try:
        if 'files' not in request.files:
            return 'No files uploaded', 400
        files = request.files.getlist('files')
        if len(files) < 2: return 'At least 2 images required', 400
        if len(files) > 20: return 'Max 20 images', 400
        from PIL import Image
        images = []
        for i, file in enumerate(files):
            valid, msg = validate_file(file, allowed_ext=['.jpg', '.jpeg', '.png', '.webp'])
            if not valid: return f'File {i+1}: {msg}', 400
            path = os.path.join(temp_dir, f'img-{i:03d}.png')
            file.save(path)
            img = Image.open(path)
            if img.mode != 'RGBA': img = img.convert('RGBA')
            img = img.resize((500, 500), Image.LANCZOS)
            images.append(img)
        output_path = os.path.join(temp_dir, 'animation.gif')
        duration = int(request.form.get('duration', '200'))
        images[0].save(output_path, 'GIF', save_all=True, append_images=images[1:], duration=duration, loop=0, optimize=True)
        return send_file(output_path, mimetype='image/gif', as_attachment=True, download_name='animation.gif')
    except Exception as e:
        print(f'❌ GIF error: {e}', flush=True)
        return f'Error: {str(e)}', 500
    finally:
        processing_lock.release()
        cleanup_dir(temp_dir)

# ========== 21. IMAGE TO WORD (Gemini AI + Fallback) ==========
@app.route('/image-to-word', methods=['POST'])
def image_to_word():
    if not processing_lock.acquire(timeout=300):
        return 'Server busy. Try again.', 503
    temp_dir = tempfile.mkdtemp()
    try:
        if 'files' in request.files:
            files = request.files.getlist('files')
        elif 'file' in request.files:
            files = [request.files['file']]
        else:
            return 'No files uploaded', 400
        files = [f for f in files if f and f.filename]
        if not files: return 'No files uploaded', 400
        if len(files) > 3: return 'Max 3 files allowed per request', 400
        custom_title = request.form.get('title', 'Extracted Text')[:60]
        from google import genai
        from PIL import Image
        import json
        from docx import Document
        from docx.shared import Pt, RGBColor, Cm
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from datetime import datetime
        api_key = os.environ.get('GEMINI_API_KEY', '').strip()
        if not api_key: return 'Server not configured. Contact admin.', 500
        client = genai.Client(api_key=api_key)
        prompt_text = """Extract ALL text from this image, preserving structure.
Return ONLY valid JSON, no explanation, no markdown:
{"tables":[{"rows":[["cell1","cell2"],["cell3","cell4"]]}],"plain_text":"any text outside tables"}
Rules:
- Preserve EXACT text including Hindi/Devanagari
- Each table row is an array of cell strings
- If no table but structured data exists, treat as 1-column table
- If only plain text, tables = [], plain_text = full text
- Return ONLY JSON"""
        results = []
        for idx, file in enumerate(files):
            valid, msg = validate_file(file, allowed_ext=['.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tiff', '.tif'], max_size=15 * 1024 * 1024)
            if not valid: return f'File {idx+1} ({file.filename}): {msg}', 400
            ext = os.path.splitext(file.filename)[1].lower() or '.png'
            input_path = os.path.join(temp_dir, f'input_{idx}{ext}')
            file.save(input_path)
            try:
                img = Image.open(input_path)
                if img.mode != 'RGB': img = img.convert('RGB')
                max_dim = 2000
                if max(img.size) > max_dim:
                    ratio = max_dim / max(img.size)
                    img = img.resize((int(img.width * ratio), int(img.height * ratio)), Image.LANCZOS)
                text, model_used = generate_gemini_response(client, prompt_text, img, file.filename)
                print(f'✅ Used model: {model_used}', flush=True)
                if text.startswith('```'):
                    parts = text.split('```')
                    text = parts[1] if len(parts) > 1 else text
                    if text.startswith('json'): text = text[4:]
                text = text.strip()
                try: data = json.loads(text)
                except: data = {'tables': [], 'plain_text': text}
                doc = Document()
                for section in doc.sections:
                    section.top_margin = Cm(2); section.bottom_margin = Cm(2)
                    section.left_margin = Cm(2); section.right_margin = Cm(2)
                title_text = custom_title if len(files) == 1 else f'{custom_title} - {idx+1}'
                title_para = doc.add_heading(title_text, 0)
                title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
                if title_para.runs:
                    title_para.runs[0].font.color.rgb = RGBColor(0xa8, 0x55, 0xf7)
                    title_para.runs[0].font.size = Pt(22)
                sub = doc.add_paragraph(); sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
                sub_run = sub.add_run(f'AI OCR • {datetime.now().strftime("%d %b %Y, %I:%M %p")}')
                sub_run.font.size = Pt(9)
                sub_run.font.color.rgb = RGBColor(0x66, 0x66, 0x66)
                sub_run.italic = True
                doc.add_paragraph()
                tables = data.get('tables', [])
                plain_text = data.get('plain_text', '').strip()
                for t_idx, table_data in enumerate(tables):
                    rows = table_data.get('rows', [])
                    if not rows: continue
                    cols = max(len(r) for r in rows)
                    if cols == 0: continue
                    tbl = doc.add_table(rows=len(rows), cols=cols)
                    try: tbl.style = 'Light Grid Accent 1'
                    except: tbl.style = 'Table Grid'
                    for r_idx, row in enumerate(rows):
                        for c_idx in range(cols):
                            cell_text = row[c_idx] if c_idx < len(row) else ''
                            cell = tbl.cell(r_idx, c_idx)
                            cell.text = str(cell_text)
                            for p in cell.paragraphs:
                                for run in p.runs:
                                    run.font.size = Pt(10)
                                    if r_idx == 0: run.font.bold = True
                    try:
                        from docx.oxml.ns import qn
                        from docx.oxml import OxmlElement
                        for c_idx in range(cols):
                            cell = tbl.cell(0, c_idx)
                            tcPr = cell._tc.get_or_add_tcPr()
                            shd = OxmlElement('w:shd')
                            shd.set(qn('w:fill'), 'A855F7')
                            tcPr.append(shd)
                            for p in cell.paragraphs:
                                for run in p.runs:
                                    run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
                    except: pass
                    if t_idx < len(tables) - 1: doc.add_paragraph()
                if plain_text:
                    for line in plain_text.split('\n'):
                        if line.strip():
                            p = doc.add_paragraph()
                            run = p.add_run(line.strip())
                            run.font.size = Pt(11)
                            p.paragraph_format.space_after = Pt(6)
                doc.add_paragraph()
                footer = doc.add_paragraph(); footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
                fr = footer.add_run('Generated by Bharat24Tools — AI Powered')
                fr.font.size = Pt(9)
                fr.font.color.rgb = RGBColor(0x99, 0x99, 0x99)
                fr.italic = True
                base_name = os.path.splitext(file.filename)[0]
                base_name = re.sub(r'[\\/\*\?\:\[\]<>|]', '_', base_name)[:50] or f'file_{idx+1}'
                output_path = os.path.join(temp_dir, f'output_{idx}.docx')
                doc.save(output_path)
                results.append((base_name, output_path))
                print(f'✅ {file.filename} done', flush=True)
            except Exception as e:
                import traceback
                traceback.print_exc()
                return f'AI Error ({file.filename}): {str(e)[:300]}', 500
        if not results: return 'No content extracted from any file.', 400
        if len(results) == 1:
            base_name, output_path = results[0]
            return send_file(output_path, mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document', as_attachment=True, download_name=f'Bharat24Tools_AI_{base_name}.docx')
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for base_name, path in results: zf.write(path, f'{base_name}.docx')
        zip_buffer.seek(0)
        return send_file(zip_buffer, mimetype='application/zip', as_attachment=True, download_name=f'Bharat24Tools_AI_{datetime.now().strftime("%Y%m%d_%H%M")}.zip')
    except Exception as e:
        import traceback
        traceback.print_exc()
        return f'Error: {str(e)}', 500
    finally:
        processing_lock.release()
        cleanup_dir(temp_dir)

# ========== 22. IMAGE TO EXCEL (Gemini AI + Fallback) ==========
@app.route('/image-to-excel', methods=['POST'])
def image_to_excel():
    if not processing_lock.acquire(timeout=300):
        return 'Server busy. Try again.', 503
    temp_dir = tempfile.mkdtemp()
    try:
        if 'files' in request.files:
            files = request.files.getlist('files')
        elif 'file' in request.files:
            files = [request.files['file']]
        else:
            return 'No files uploaded', 400
        files = [f for f in files if f and f.filename]
        if not files: return 'No files uploaded', 400
        if len(files) > 3: return 'Max 3 files allowed per request', 400
        from google import genai
        from PIL import Image
        import json
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.utils import get_column_letter
        from datetime import datetime
        api_key = os.environ.get('GEMINI_API_KEY', '').strip()
        if not api_key: return 'Server not configured. Contact admin.', 500
        client = genai.Client(api_key=api_key)
        prompt_text = """Extract ALL table data from this image.
Return ONLY valid JSON, no explanation, no markdown:
{"tables":[{"name":"Table 1","rows":[["cell1","cell2"],["cell3","cell4"]]}]}
Rules:
- Preserve EXACT text including Hindi/Devanagari
- Each row is array of cell strings, keep same column count
- If multiple tables, return multiple objects
- If no table, treat whole content as one table
- Empty cells = ""
- Return ONLY JSON, nothing else"""
        results = []
        for idx, file in enumerate(files):
            valid, msg = validate_file(file, allowed_ext=['.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tiff', '.tif'], max_size=15 * 1024 * 1024)
            if not valid: return f'File {idx+1} ({file.filename}): {msg}', 400
            ext = os.path.splitext(file.filename)[1].lower() or '.png'
            input_path = os.path.join(temp_dir, f'input_{idx}{ext}')
            file.save(input_path)
            try:
                img = Image.open(input_path)
                if img.mode != 'RGB': img = img.convert('RGB')
                max_dim = 2000
                if max(img.size) > max_dim:
                    ratio = max_dim / max(img.size)
                    img = img.resize((int(img.width * ratio), int(img.height * ratio)), Image.LANCZOS)
                text, model_used = generate_gemini_response(client, prompt_text, img, file.filename)
                print(f'✅ Used model: {model_used}', flush=True)
                if text.startswith('```'):
                    parts = text.split('```')
                    text = parts[1] if len(parts) > 1 else text
                    if text.startswith('json'): text = text[4:]
                text = text.strip()
                try: data = json.loads(text)
                except: return f'AI could not parse {file.filename}.', 400
                tables = data.get('tables', [])
                if not tables: return f'No table data found in {file.filename}.', 400
                wb = Workbook()
                ws = wb.active
                ws.title = 'Extracted Data'
                thin = Border(left=Side(style='thin', color='CCCCCC'), right=Side(style='thin', color='CCCCCC'), top=Side(style='thin', color='CCCCCC'), bottom=Side(style='thin', color='CCCCCC'))
                current_row = 1
                for t_idx, table_data in enumerate(tables):
                    rows = table_data.get('rows', [])
                    if not rows: continue
                    cols = max(len(r) for r in rows) if rows else 0
                    if cols == 0: continue
                    if len(tables) > 1:
                        title_cell = ws.cell(row=current_row, column=1, value=f'📄 {table_data.get("name", f"Table {t_idx+1}")}')
                        title_cell.font = Font(bold=True, size=12, color='FFFFFF')
                        title_cell.fill = PatternFill('solid', fgColor='A855F7')
                        ws.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=max(cols, 3))
                        current_row += 2
                    data_start = current_row
                    for r_idx, row in enumerate(rows):
                        for c_idx in range(cols):
                            val = row[c_idx] if c_idx < len(row) else ''
                            cell = ws.cell(row=data_start + r_idx, column=c_idx + 1, value=str(val))
                            cell.alignment = Alignment(wrap_text=True, vertical='center')
                            cell.border = thin
                            if r_idx == 0:
                                cell.font = Font(bold=True, color='FFFFFF', size=11)
                                cell.fill = PatternFill('solid', fgColor='A855F7')
                            elif r_idx % 2 == 0:
                                cell.fill = PatternFill('solid', fgColor='F8F5FF')
                    for c_idx in range(cols):
                        col_letter = get_column_letter(c_idx + 1)
                        max_len = 12
                        for r_idx in range(len(rows)):
                            if c_idx < len(rows[r_idx]):
                                max_len = max(max_len, min(len(str(rows[r_idx][c_idx])), 55))
                        ws.column_dimensions[col_letter].width = max_len
                    current_row = data_start + len(rows) + 2
                base_name = os.path.splitext(file.filename)[0]
                base_name = re.sub(r'[\\/\*\?\:\[\]<>|]', '_', base_name)[:50] or f'file_{idx+1}'
                output_path = os.path.join(temp_dir, f'output_{idx}.xlsx')
                wb.save(output_path)
                results.append((base_name, output_path))
                print(f'✅ {file.filename} done', flush=True)
            except Exception as e:
                import traceback
                traceback.print_exc()
                return f'AI Error ({file.filename}): {str(e)[:300]}', 500
        if not results: return 'No table data extracted from any file.', 400
        if len(results) == 1:
            base_name, output_path = results[0]
            return send_file(output_path, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', as_attachment=True, download_name=f'Bharat24Tools_AI_{base_name}.xlsx')
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for base_name, path in results: zf.write(path, f'{base_name}.xlsx')
        zip_buffer.seek(0)
        return send_file(zip_buffer, mimetype='application/zip', as_attachment=True, download_name=f'Bharat24Tools_AI_{datetime.now().strftime("%Y%m%d_%H%M")}.zip')
    except Exception as e:
        import traceback
        traceback.print_exc()
        return f'Error: {str(e)}', 500
    finally:
        processing_lock.release()
        cleanup_dir(temp_dir)

# ========== 23. PDF WATERMARK ==========
@app.route('/pdf-watermark', methods=['POST'])
def pdf_watermark():
    if not processing_lock.acquire(timeout=300):
        return 'Server busy. Try again.', 503
    temp_dir = tempfile.mkdtemp()
    try:
        if 'file' not in request.files:
            return 'No file uploaded', 400
        file = request.files['file']
        valid, msg = validate_file(file, allowed_ext=['.pdf'])
        if not valid: return msg, 400
        text = request.form.get('text', 'Bharat24Tools')
        opacity = float(request.form.get('opacity', '0.3'))
        if opacity < 0.1 or opacity > 1.0: opacity = 0.3
        input_path = os.path.join(temp_dir, 'input.pdf')
        output_path = os.path.join(temp_dir, 'watermarked.pdf')
        file.save(input_path)
        from reportlab.pdfgen import canvas
        from PyPDF2 import PdfReader, PdfWriter
        reader = PdfReader(input_path)
        writer = PdfWriter()
        for page in reader.pages:
            pw = float(page.mediabox.width)
            ph = float(page.mediabox.height)
            packet = io.BytesIO()
            can = canvas.Canvas(packet, pagesize=(pw, ph))
            can.setFont('Helvetica-Bold', 60)
            can.setFillColorRGB(0.66, 0.33, 0.97, alpha=opacity)
            can.translate(pw / 2, ph / 2)
            can.rotate(45)
            can.drawCentredString(0, 0, text)
            can.save()
            packet.seek(0)
            wm_page = PdfReader(packet).pages[0]
            page.merge_page(wm_page)
            writer.add_page(page)
        with open(output_path, 'wb') as f: writer.write(f)
        return send_file(output_path, mimetype='application/pdf', as_attachment=True, download_name='watermarked.pdf')
    except Exception as e:
        print(f'❌ Watermark error: {e}', flush=True)
        return f'Error: {str(e)}', 500
    finally:
        processing_lock.release()
        cleanup_dir(temp_dir)

# ========== 24. PDF PAGE DELETE ==========
@app.route('/pdf-page-delete', methods=['POST'])
def pdf_page_delete():
    if not processing_lock.acquire(timeout=300):
        return 'Server busy. Try again.', 503
    temp_dir = tempfile.mkdtemp()
    try:
        if 'file' not in request.files:
            return 'No file uploaded', 400
        file = request.files['file']
        valid, msg = validate_file(file, allowed_ext=['.pdf'])
        if not valid: return msg, 400
        pages_to_delete = request.form.get('pages', '').strip()
        if not pages_to_delete: return 'Page numbers required', 400
        input_path = os.path.join(temp_dir, 'input.pdf')
        output_path = os.path.join(temp_dir, 'output.pdf')
        file.save(input_path)
        delete_pages = set()
        for part in pages_to_delete.split(','):
            part = part.strip()
            if '-' in part:
                start, end = part.split('-')
                delete_pages.update(range(int(start), int(end) + 1))
            else:
                delete_pages.add(int(part))
        from PyPDF2 import PdfReader, PdfWriter
        reader = PdfReader(input_path)
        writer = PdfWriter()
        total_pages = len(reader.pages)
        for i, page in enumerate(reader.pages):
            if (i + 1) not in delete_pages:
                writer.add_page(page)
        with open(output_path, 'wb') as f: writer.write(f)
        return send_file(output_path, mimetype='application/pdf', as_attachment=True, download_name='pages-deleted.pdf')
    except Exception as e:
        print(f'❌ Page Delete error: {e}', flush=True)
        return f'Error: {str(e)}', 500
    finally:
        processing_lock.release()
        cleanup_dir(temp_dir)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)