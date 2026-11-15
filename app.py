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
import PyPDF2
from google import genai

app = Flask(__name__)
CORS(app)

MAX_FILE_SIZE = 20 * 1024 * 1024
MAX_FILES_COUNT = 20
PROCESSING_TIMEOUT = 120
CLEANUP_DELAY = 30
ATTEMPT_TIMEOUT = 120 

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
    <title>Bharat24Tools API v10.1</title>
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
        <h1>⚡ Bharat24Tools API v10.1</h1>
        <p class="status-badge">Server is running ✅ — All Tools Active</p>
        
        <div class="section-title">📄 PDF Tools (11)</div>
        <div class="endpoint"><code>POST /compress</code><span class="desc">Compress PDF ✅ AI Scanner Mode (10KB Min)</span></div>
        <div class="endpoint"><code>POST /pdf-to-jpg</code><span class="desc">PDF to Images</span></div>
        <div class="endpoint"><code>POST /jpg-to-pdf</code><span class="desc">Images to PDF</span></div>
        <div class="endpoint"><code>POST /pdf-to-word</code><span class="desc">PDF to Word</span></div>
        <div class="endpoint"><code>POST /word-to-pdf</code><span class="desc">Word to PDF</span></div>
        <div class="endpoint"><code>POST /excel-to-pdf</code><span class="desc">Excel to PDF</span></div>
        <div class="endpoint"><code>POST /pdf-to-excel</code><span class="desc">PDF to Excel</span></div>
        <div class="endpoint"><code>POST /excel-to-image</code><span class="desc">Excel to Image</span></div>
        <div class="endpoint"><code>POST /merge-pdf</code><span class="desc">Merge PDFs</span></div>
        <div class="endpoint"><code>POST /split-pdf</code><span class="desc">Split PDF ✅ Advanced Visual Mode</span></div>
        <div class="endpoint"><code>POST /protect-pdf</code><span class="desc">Protect PDF</span></div>
        <div class="endpoint"><code>POST /unlock-pdf</code><span class="desc">Unlock PDF</span></div>
        <div class="endpoint"><code>POST /pdf-watermark</code><span class="desc">PDF Watermark</span></div>
        
        <div class="section-title">🖼 Image Tools (11)</div>
        <div class="endpoint"><code>POST /heic-to-jpg</code><span class="desc">HEIC to JPG</span></div>
        <div class="endpoint"><code>POST /webp-to-jpg</code><span class="desc">WebP to JPG</span></div>
        <div class="endpoint"><code>POST /image-upscaler</code><span class="desc">AI Image Upscaler</span></div>
        <div class="endpoint"><code>POST /ocr</code><span class="desc">OCR Multi-Language</span></div>
        <div class="endpoint"><code>POST /image-to-sketch</code><span class="desc">Image to Sketch ✅ 6 Styles + Intensity</span></div>
        <div class="endpoint"><code>POST /gif-maker</code><span class="desc">GIF Maker</span></div>
        <div class="endpoint"><code>POST /image-to-word</code><span class="desc">Image to Word ✅ AI + Fallback</span></div>
        <div class="endpoint"><code>POST /image-to-excel</code><span class="desc">Image to Excel ✅ AI + Fallback</span></div>
        <p class="footer">Version 10.1 — 22 Tools | API Server</p>
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
        'version': '10.1',
        'tools': 22,
        'ocr_engine': 'gemini-3.8-flash (with fallback)',
        'sdk': 'google-genai',
        'gemini_configured': bool(os.environ.get('GEMINI_API_KEY', '').strip()),
        'max_files_ocr': 3,
        'compression_range': '10KB - 2GB',
        'fallback_models': ['gemini-3.8-flash', 'gemini-2.5-flash', 'gemini-2.0-flash', 'gemini-1.5-flash'],
        'auto_cleanup': True,
        'sketch_styles': ['pencil', 'charcoal', 'ink', 'colored', 'edge', 'crosshatch'],
        'sketch_formats': ['png', 'jpg', 'webp']
    }

# ========== 1. COMPRESS PDF (ADVANCED AI SCANNER MODE) ==========
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

        preset = request.form.get('preset', 'extreme')
        target_bytes = request.form.get('target_bytes', '').strip()
        grayscale = request.form.get('grayscale', 'no') == 'yes'
        
        try:
            target_size = int(target_bytes) if target_bytes else 0
        except:
            target_size = 0

        MIN_TARGET = 10 * 1024 
        if target_size > 0 and target_size < MIN_TARGET:
            target_size = MIN_TARGET

        output_path = os.path.join(temp_dir, 'output.pdf')
        method_used = "Standard"
        target_hit = ""

        def build_gs_cmd(inp, outp, dpi_val, jpeg_quality, pdf_settings, gray=False):
            cmd = ['gs', '-sDEVICE=pdfwrite', '-dCompatibilityLevel=1.4', f'-dPDFSETTINGS={pdf_settings}', '-dNOPAUSE', '-dQUIET', '-dBATCH', '-dNOINTERPOLATE', '-dDetectDuplicateImages=true', '-dDownsampleColorImages=true', f'-dColorImageResolution={dpi_val}', '-dDownsampleGrayImages=true', f'-dGrayImageResolution={dpi_val}', '-dDownsampleMonoImages=true', f'-dMonoImageResolution={dpi_val}', f'-dJPEGQ={jpeg_quality}', '-dAutoRotatePages=/None', '-dMaxBitmap=500000000']
            if grayscale or gray:
                cmd.extend(['-sColorConversionStrategy=Gray', '-dProcessColorModel=/DeviceGray'])
            cmd.extend([f'-sOutputFile={outp}', inp])
            return cmd

        def fallback_compression(inp, outp):
            try:
                from PyPDF2 import PdfReader, PdfWriter
                print("⚠️ Ghostscript failed or timed out. Activating PyPDF2 Fallback...", flush=True)
                reader = PdfReader(inp)
                writer = PdfWriter()
                for page in reader.pages:
                    writer.add_page(page)
                writer.compress_identical_objects()
                with open(outp, 'wb') as f:
                    writer.write(f)
                return True
            except Exception as e:
                print(f"❌ PyPDF2 Fallback also failed: {e}", flush=True)
                return False

        if target_size > 0 and target_size < input_size:
            print(f'🎯 Target: {target_size/1024:.1f}KB (Original: {input_size/1024:.1f}KB)', flush=True)
            
            if target_size < (input_size * 0.25):
                print("⚡ Extreme size detected. Activating AI Scanner Mode...", flush=True)
                min_dpi, max_dpi = 10, 50
                attempts = 0
                jpg_files = []
                raster_path = None
                
                while attempts < 4:
                    attempts += 1
                    current_dpi = (min_dpi + max_dpi) // 2
                    
                    for f in glob.glob(f'{temp_dir}/page-*.jpg'): os.remove(f)
                    
                    jpg_pattern = f'{temp_dir}/page-%03d.jpg'
                    color_strategy = '-sColorConversionStrategy=Gray' if grayscale else '-sColorConversionStrategy=RGB'
                    
                    try:
                        subprocess.run([
                            'gs', '-dNOPAUSE', '-dBATCH', '-dQUIET', '-sDEVICE=jpeg', 
                            f'-r{current_dpi}', '-dJPEGQ=30', color_strategy, '-dMaxBitmap=500000000',
                            f'-sOutputFile={jpg_pattern}', input_path
                        ], check=True, timeout=ATTEMPT_TIMEOUT, capture_output=True)
                    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
                        print(f"  ⚠️ Ghostscript Rasterize failed/timed out. Trying fallback...", flush=True)
                        if fallback_compression(input_path, output_path):
                            target_hit = f'Fallback ({os.path.getsize(output_path)/1024:.1f}KB)'
                            method_used = "PyPDF2 Fallback"
                            break
                        else:
                            return 'This PDF is too complex to compress. Please try a smaller file.', 400
                    
                    jpg_files = sorted(glob.glob(jpg_pattern))
                    if not jpg_files: break
                    
                    raster_path = os.path.join(temp_dir, f'raster_{attempts}.pdf')
                    try:
                        subprocess.run([
                            'gs', '-sDEVICE=pdfwrite', '-dCompatibilityLevel=1.4', 
                            '-dNOPAUSE', '-dQUIET', '-dBATCH', '-dMaxBitmap=500000000',
                            f'-sOutputFile={raster_path}'
                        ] + jpg_files, check=True, timeout=ATTEMPT_TIMEOUT, capture_output=True)
                    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
                        print(f"  ⚠️ Ghostscript Merge failed/timed out. Trying fallback...", flush=True)
                        if fallback_compression(input_path, output_path):
                            target_hit = f'Fallback ({os.path.getsize(output_path)/1024:.1f}KB)'
                            method_used = "PyPDF2 Fallback"
                            break
                        else:
                            return 'This PDF is too complex to compress. Please try a smaller file.', 400

                    if os.path.exists(raster_path):
                        out_size = os.path.getsize(raster_path)
                        print(f'  [Scanner Mode {attempts}] DPI:{current_dpi} -> {out_size/1024:.1f}KB', flush=True)
                        
                        if out_size <= target_size:
                            shutil.copy(raster_path, output_path)
                            target_hit = f'Exact Hit ({out_size/1024:.1f}KB)'
                            method_used = "AI Extreme Scanner"
                            break
                        else:
                            max_dpi = current_dpi - 2 
                            
                if not os.path.exists(output_path) and raster_path and os.path.exists(raster_path):
                    shutil.copy(raster_path, output_path)
                    target_hit = f'Closest ({os.path.getsize(output_path)/1024:.1f}KB)'
                    method_used = "AI Scanner (Limit)"

            else:
                print("🔧 Applying Standard Text-Safe Compression...", flush=True)
                min_dpi, max_dpi = 20, 150
                attempts = 0
                attempt_path = None
                
                while attempts < 3:
                    attempts += 1
                    mid_dpi = (min_dpi + max_dpi) // 2
                    mid_quality = max(10, min(80, int((mid_dpi / 150) * 70) + 10))
                    attempt_path = os.path.join(temp_dir, f'attempt_{attempts}.pdf')
                    
                    cmd = build_gs_cmd(input_path, attempt_path, mid_dpi, mid_quality, '/screen')
                    
                    try:
                        subprocess.run(cmd, check=True, timeout=ATTEMPT_TIMEOUT, capture_output=True)
                    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
                        print(f"  ⚠️ Ghostscript Standard failed/timed out. Trying fallback...", flush=True)
                        if fallback_compression(input_path, output_path):
                            target_hit = f'Fallback ({os.path.getsize(output_path)/1024:.1f}KB)'
                            method_used = "PyPDF2 Fallback"
                            break
                        else:
                            return 'This PDF is too complex to compress. Please try a smaller file.', 400
                    
                    if os.path.exists(attempt_path):
                        out_size = os.path.getsize(attempt_path)
                        print(f'  [Standard Mode] DPI:{mid_dpi} -> {out_size/1024:.1f}KB', flush=True)
                        
                        if out_size <= target_size:
                            shutil.copy(attempt_path, output_path)
                            target_hit = f'Exact Hit ({out_size/1024:.1f}KB)'
                            method_used = "Smart Text-Safe"
                            break
                        else:
                            max_dpi = mid_dpi - 5
                            
                if not os.path.exists(output_path) and attempt_path and os.path.exists(attempt_path):
                    shutil.copy(attempt_path, output_path)
                    target_hit = f'Closest ({os.path.getsize(output_path)/1024:.1f}KB)'
                    method_used = "Smart Text-Safe (Limit)"

        else:
            cmd = build_gs_cmd(input_path, output_path, 72, 50, '/screen')
            try:
                subprocess.run(cmd, check=True, timeout=ATTEMPT_TIMEOUT, capture_output=True)
                method_used = "Normal Compress"
                target_hit = f"Done ({os.path.getsize(output_path)/1024:.1f}KB)"
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
                print(f"⚠️ Ghostscript Normal failed/timed out. Trying fallback...", flush=True)
                if fallback_compression(input_path, output_path):
                    method_used = "PyPDF2 Fallback"
                    target_hit = f"Fallback ({os.path.getsize(output_path)/1024:.1f}KB)"

        if not os.path.exists(output_path):
            print("🚨 Ultimate Fallback Activated: Output file missing.", flush=True)
            if fallback_compression(input_path, output_path):
                method_used = "Fallback Standard"
                target_hit = "Best Effort"
            else:
                return 'Compression failed: Could not generate output file.', 500

        if not os.path.exists(output_path):
            return 'Compression failed: Could not generate output file.', 500

        output_size = os.path.getsize(output_path)
        
        response = send_file(output_path, mimetype='application/pdf', as_attachment=True, download_name='compressed.pdf')
        response.headers['X-Compression-Method'] = method_used
        response.headers['X-Target-Hit'] = target_hit
        response.headers['X-Original-Size'] = str(input_size)
        response.headers['X-Final-Size'] = str(output_size)
        response.headers['Access-Control-Expose-Headers'] = 'X-Compression-Method, X-Target-Hit, X-Original-Size, X-Final-Size'
        return response
    except Exception as e:
        import traceback
        traceback.print_exc()
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
        
        subprocess.run([
            'gs', '-dNOPAUSE', '-dBATCH', '-dQUIET', 
            '-sDEVICE=jpeg', '-r150', '-dJPEGQ=90', '-dMaxBitmap=500000000',
            f'-sOutputFile={output_pattern}', input_path
        ], check=True, timeout=PROCESSING_TIMEOUT, capture_output=True)
        
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
        return 'Timeout: PDF is too large or complex for this server. Please try a smaller file.', 500
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
        subprocess.run(['gs', '-sDEVICE=txtwrite', '-dNOPAUSE', '-dBATCH', '-dQUIET', '-dMaxBitmap=500000000', f'-sOutputFile={txt_path}', input_path], check=True, timeout=PROCESSING_TIMEOUT, capture_output=True)
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

# ======================================================================
#  EXCEL -> PDF ENGINE  (BharatOS-Tools)
#  Draws every sheet exactly as laid out in Excel: real column widths,
#  row heights, merged cells, fills, borders, fonts, number formats.
#  Nothing is truncated: long text wraps or overflows, wide sheets are
#  scaled to fit the page (or split across pages), tall sheets continue
#  on the next page with the header row repeated.
# ======================================================================
import os as _os
import re as _re
import glob as _glob
import math as _math
import colorsys as _colorsys
import datetime as _dt
from decimal import Decimal as _Dec, ROUND_HALF_UP as _HALF_UP, InvalidOperation as _InvOp
from xml.etree import ElementTree as _ET

from reportlab.pdfgen import canvas as _rl_canvas
from reportlab.lib.pagesizes import A4 as _A4, A3 as _A3, LETTER as _LETTER, LEGAL as _LEGAL
from reportlab.lib.colors import HexColor as _HexColor
from reportlab.pdfbase import pdfmetrics as _pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont as _TTFont

_PAGE_SIZES = {'A4': _A4, 'A3': _A3, 'LETTER': _LETTER, 'LEGAL': _LEGAL}
_HERE = _os.path.dirname(_os.path.abspath(__file__))

# ---------------------------------------------------------------- fonts
_FALLBACK_FONTS = []          # [(registered_name, charToGlyph dict)]
_FONTS_READY = False

def _init_fonts():
    """Find extra TTF fonts (Hindi/Unicode symbols) once. Put .ttf files in a
    'fonts' folder next to app.py to add your own (e.g. NotoSansDevanagari)."""
    global _FONTS_READY
    if _FONTS_READY:
        return
    _FONTS_READY = True
    patterns = [
        _os.path.join(_HERE, 'fonts', '*.ttf'),
        '/usr/share/fonts/**/NotoSansDevanagari-Regular.ttf',
        '/usr/share/fonts/**/NotoSans-Regular.ttf',
        '/usr/share/fonts/**/Lohit-Devanagari.ttf',
        '/usr/share/fonts/**/FreeSans.ttf',
        '/usr/share/fonts/**/DejaVuSans.ttf',
        '/usr/share/fonts/**/LiberationSans-Regular.ttf',
        'C:/Windows/Fonts/Nirmala.ttf', 'C:/Windows/Fonts/mangal.ttf', 'C:/Windows/Fonts/arial.ttf',
        '/System/Library/Fonts/Supplemental/Arial Unicode.ttf',
    ]
    seen = set()
    for pat in patterns:
        for path in sorted(_glob.glob(pat, recursive=True)):
            if path in seen:
                continue
            seen.add(path)
            try:
                name = 'XLFB%d' % len(_FALLBACK_FONTS)
                _pdfmetrics.registerFont(_TTFont(name, path))
                cmap = _pdfmetrics.getFont(name).face.charToGlyph
                _FALLBACK_FONTS.append((name, cmap, path))
            except Exception:
                continue

_BASE = {(False, False): 'Helvetica', (True, False): 'Helvetica-Bold',
         (False, True): 'Helvetica-Oblique', (True, True): 'Helvetica-BoldOblique'}
_SEG_CACHE = {}

def _segments(text, bold, italic):
    """Split text into runs; each run uses a font that really has those glyphs."""
    key = (text, bold, italic)
    hit = _SEG_CACHE.get(key)
    if hit is not None:
        return hit
    base = _BASE[(bool(bold), bool(italic))]
    runs = []
    for ch in text:
        if ch in '\t\r\n\u00a0':
            ch = ' '
        font = None
        try:
            ch.encode('cp1252')
            font = base
        except UnicodeEncodeError:
            for name, cmap, _p in _FALLBACK_FONTS:
                if ord(ch) in cmap:
                    font = name
                    break
        if font is None:
            if ord(ch) < 32 or 0x200B <= ord(ch) <= 0x200F or ord(ch) == 0xFEFF:
                continue            # invisible characters
            ch, font = '?', base
        if runs and runs[-1][0] == font:
            runs[-1][1] += ch
        else:
            runs.append([font, ch])
    out = [(f, s) for f, s in runs]
    if len(_SEG_CACHE) > 20000:
        _SEG_CACHE.clear()
    _SEG_CACHE[key] = out
    return out

# ---- complex scripts (Hindi/Devanagari, Arabic ...) need real shaping.
# reportlab cannot do that, so such lines are drawn as pictures by Pillow+Raqm.
_COMPLEX_RE = _re.compile('[\u0900-\u0DFF\u0600-\u06FF\u0E00-\u0E7F]')
_RAQM = None
_PIL_FONTS = {}
_IMG_CACHE = {}
_K = 4          # picture resolution multiplier

def _raqm_available():
    global _RAQM
    if _RAQM is None:
        try:
            from PIL import features
            _RAQM = bool(features.check('raqm'))
        except Exception:
            _RAQM = False
    return _RAQM

def _complex_font_path(text):
    chars = [ord(c) for c in text if _COMPLEX_RE.match(c)]
    if not chars:
        return None
    for name, cmap, path in _FALLBACK_FONTS:
        if all(o in cmap for o in chars):
            return path
    for name, cmap, path in _FALLBACK_FONTS:
        if chars[0] in cmap:
            return path
    return None

def _pil_font(path, px):
    key = (path, px)
    f = _PIL_FONTS.get(key)
    if f is None:
        from PIL import ImageFont
        f = ImageFont.truetype(path, px, layout_engine=ImageFont.Layout.RAQM)
        if len(_PIL_FONTS) > 200:
            _PIL_FONTS.clear()
        _PIL_FONTS[key] = f
    return f

def _use_complex(text):
    return bool(_COMPLEX_RE.search(text)) and _raqm_available() and _complex_font_path(text) is not None

def _text_width(text, bold, italic, size):
    if _use_complex(text):
        try:
            return _pil_font(_complex_font_path(text), max(4, int(round(size * _K)))).getlength(text) / float(_K)
        except Exception:
            pass
    return sum(_pdfmetrics.stringWidth(s, f, size) for f, s in _segments(text, bold, italic))

def _draw_complex(cv, text, size, x, y, color):
    from PIL import Image, ImageDraw
    from reportlab.lib.utils import ImageReader
    px = max(4, int(round(size * _K)))
    key = (text, px, color)
    hit = _IMG_CACHE.get(key)
    if hit is None:
        font = _pil_font(_complex_font_path(text), px)
        w = int(font.getlength(text)) + 8
        h = int(px * 1.7) + 4
        base = int(px * 1.25)
        im = Image.new('RGBA', (w, h), (255, 255, 255, 0))
        c = (color or '000000')
        ImageDraw.Draw(im).text((4, base), text, font=font, fill=(int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16), 255), anchor='ls')
        hit = (ImageReader(im), w, h, base)
        if len(_IMG_CACHE) > 3000:
            _IMG_CACHE.clear()
        _IMG_CACHE[key] = hit
    reader, w, h, base = hit
    cv.drawImage(reader, x - 4.0 / _K, y - (h - base) / float(_K), width=w / float(_K), height=h / float(_K), mask='auto')
    return (w - 8) / float(_K)

# --------------------------------------------------------------- colours
_DEFAULT_THEME = ['FFFFFF', '000000', 'E7E6E6', '44546A', '4472C4', 'ED7D31', 'A5A5A5', 'FFC000', '5B9BD5', '70AD47']

def _theme_palette(wb):
    pal = list(_DEFAULT_THEME)
    try:
        raw = getattr(wb, 'loaded_theme', None)
        if not raw:
            return pal
        root = _ET.fromstring(raw)
        ns = {'a': 'http://schemas.openxmlformats.org/drawingml/2006/main'}
        scheme = root.find('.//a:clrScheme', ns)
        names = ['dk1', 'lt1', 'dk2', 'lt2', 'accent1', 'accent2', 'accent3', 'accent4', 'accent5', 'accent6']
        found = {}
        for n in names:
            el = scheme.find('a:' + n, ns)
            if el is None or len(el) == 0:
                continue
            ch = el[0]
            val = ch.get('lastClr') or ch.get('val')
            if val and len(val) == 6:
                found[n] = val.upper()
        # Excel theme index order: lt1, dk1, lt2, dk2, accents
        order = ['lt1', 'dk1', 'lt2', 'dk2', 'accent1', 'accent2', 'accent3', 'accent4', 'accent5', 'accent6']
        for i, n in enumerate(order):
            if n in found:
                pal[i] = found[n]
    except Exception:
        pass
    return pal

def _apply_tint(hex6, tint):
    try:
        if not tint:
            return hex6
        r, g, b = (int(hex6[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
        h, l, s = _colorsys.rgb_to_hls(r, g, b)
        l = l * (1 + tint) if tint < 0 else l * (1 - tint) + tint
        r, g, b = _colorsys.hls_to_rgb(h, max(0, min(1, l)), s)
        return '%02X%02X%02X' % (round(r * 255), round(g * 255), round(b * 255))
    except Exception:
        return hex6

def _color_hex(color, theme, default=None):
    """openpyxl Color -> 'RRGGBB' or default."""
    if color is None:
        return default
    try:
        ctype = color.type
        if ctype == 'rgb':
            v = color.rgb
            if isinstance(v, str) and len(v) in (6, 8):
                return v[-6:].upper()
        elif ctype == 'theme':
            idx = int(color.theme)
            if 0 <= idx < len(theme):
                return _apply_tint(theme[idx], color.tint or 0)
        elif ctype == 'indexed':
            from openpyxl.styles.colors import COLOR_INDEX
            idx = int(color.indexed)
            if 0 <= idx < len(COLOR_INDEX):
                v = COLOR_INDEX[idx]
                if isinstance(v, str) and len(v) == 8:
                    return v[-6:].upper()
            if idx in (64, 65):
                return default
    except Exception:
        pass
    return default

# ------------------------------------------------------- number formats
_MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August',
           'September', 'October', 'November', 'December']
_DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

def _split_sections(fmt):
    out, cur, q, br, i = [], '', False, False, 0
    while i < len(fmt):
        ch = fmt[i]
        if ch == '\\' and i + 1 < len(fmt):
            cur += fmt[i:i + 2]; i += 2; continue
        if ch == '"':
            q = not q
        elif ch == '[' and not q:
            br = True
        elif ch == ']' and not q:
            br = False
        if ch == ';' and not q and not br:
            out.append(cur); cur = ''
        else:
            cur += ch
        i += 1
    out.append(cur)
    return out

def _clean_brackets(sec):
    """Remove [Red], [>100] etc.; turn [$₹-4009] into the currency symbol."""
    def repl(m):
        inner = m.group(1)
        if inner.startswith('$'):
            sym = inner[1:].split('-')[0]
            return '"' + sym + '"' if sym else ''
        return ''
    return _re.sub(r'\[([^\]]*)\]', lambda m: m.group(0) if _re.fullmatch(r'h+|m+|s+', m.group(1), _re.I) else repl(m), sec)

def _general_number(v):
    if isinstance(v, int) or (isinstance(v, float) and v == int(v) and abs(v) < 1e11):
        return str(int(v))
    s = '%.10g' % v
    if 'e' in s:
        mant, exp = s.split('e')
        s = mant + 'E' + exp[0] + exp[1:].lstrip('0').rjust(2, '0')
    return s

def _group3(int_str):
    out = ''
    while len(int_str) > 3:
        out = ',' + int_str[-3:] + out
        int_str = int_str[:-3]
    return int_str + out

def _format_number(v, fmt):
    if not fmt or fmt.strip().lower() == 'general':
        return _general_number(v)
    secs = _split_sections(fmt)
    neg = v < 0
    minus = False
    if neg and len(secs) >= 2:
        sec, val = secs[1], -v
    elif v == 0 and len(secs) >= 3:
        sec, val = secs[2], v
    else:
        sec, val = secs[0], abs(v)
        minus = neg
    sec = _clean_brackets(sec)
    # tokenise into literals and numeric placeholders
    prefix, core, suffix, state = '', '', '', 0      # state 0=before digits 1=in digits 2=after
    percent = 0
    i = 0
    def add_lit(t):
        nonlocal prefix, suffix, core, state
        if state == 0:
            prefix += t
        else:
            state = 2
            suffix += t
    while i < len(sec):
        ch = sec[i]
        if ch == '"':
            j = sec.find('"', i + 1)
            j = len(sec) if j < 0 else j
            add_lit(sec[i + 1:j]); i = j + 1; continue
        if ch == '\\' and i + 1 < len(sec):
            add_lit(sec[i + 1]); i += 2; continue
        if ch == '_' and i + 1 < len(sec):
            add_lit(' '); i += 2; continue
        if ch == '*' and i + 1 < len(sec):
            i += 2; continue
        if ch == '%':
            percent += 1; add_lit('%'); i += 1; continue
        if ch in '0#?' or (ch in '.,' and state != 2 and (state == 1 or (i + 1 < len(sec) and sec[i + 1] in '0#?'))):
            if state == 2:
                add_lit(ch); i += 1; continue
            state = 1; core += ch; i += 1; continue
        if ch in 'Ee' and state == 1 and i + 1 < len(sec) and sec[i + 1] in '+-':
            core += sec[i:i + 2]; i += 2; continue
        if ch == '@':
            i += 1; continue
        add_lit(ch); i += 1
    if not core:
        return ('-' if minus else '') + prefix + suffix if (prefix or suffix) and not core else _general_number(v)
    if percent:
        val = val * (100 ** percent)
    # scientific
    if _re.search(r'[Ee][+-]', core):
        mant = core.split('E')[0].split('e')[0]
        dec = len(mant.split('.')[1].replace(',', '')) if '.' in mant else 0
        txt = format(val, '.%dE' % dec)
        return ('-' if minus else '') + prefix + txt + suffix
    int_pat, _, dec_pat = core.partition('.')
    thousands = ',' in int_pat
    trailing = len(int_pat) - len(int_pat.rstrip(','))
    if trailing:
        val = val / (1000 ** trailing)
    int_digits = _re.sub(r'[^0#?]', '', int_pat)
    dec_digits = _re.sub(r'[^0#?]', '', dec_pat)
    decimals = len(dec_digits)
    try:
        q = _Dec(repr(float(val))).quantize(_Dec(1).scaleb(-decimals), rounding=_HALF_UP)
    except (_InvOp, ValueError):
        return _general_number(v)
    txt = format(q, 'f')
    ip, _, dp = txt.partition('.')
    min_int = int_digits.count('0')
    ip = ip.lstrip('0')
    ip = ip.rjust(min_int, '0')
    if thousands:
        ip = _group3(ip)
    # optional decimals ('#') lose trailing zeros
    opt = len(dec_digits) - len(dec_digits.rstrip('#'))
    while opt and dp.endswith('0'):
        dp = dp[:-1]; opt -= 1
    res = ip + ('.' + dp if dp else '')
    if not ip and not dp and not (prefix or suffix):
        res = ''
    if minus and (ip or dp):
        res = '-' + prefix + res + suffix
    else:
        res = prefix + res + suffix
    return res

def _date_tokens(sec):
    toks, i = [], 0
    pat = _re.compile(r'(yyyy|yy|mmmmm|mmmm|mmm|mm|m|dddd|ddd|dd|d|hh|h|ss|s|AM/PM|am/pm|A/P|a/p)', _re.I)
    while i < len(sec):
        ch = sec[i]
        if ch == '"':
            j = sec.find('"', i + 1); j = len(sec) if j < 0 else j
            toks.append(('lit', sec[i + 1:j])); i = j + 1; continue
        if ch == '\\' and i + 1 < len(sec):
            toks.append(('lit', sec[i + 1])); i += 2; continue
        if ch == '_' and i + 1 < len(sec):
            toks.append(('lit', ' ')); i += 2; continue
        if ch == '*' and i + 1 < len(sec):
            i += 2; continue
        if ch == '[':
            j = sec.find(']', i)
            j = len(sec) - 1 if j < 0 else j
            inner = sec[i + 1:j]
            if _re.fullmatch(r'h+|m+|s+', inner, _re.I):
                toks.append(('elapsed', inner.lower()))
            i = j + 1; continue
        m = pat.match(sec, i)
        if m:
            toks.append(('tok', m.group(1))); i = m.end(); continue
        if ch == '.' and i + 1 < len(sec) and sec[i + 1] == '0':
            j = i + 1
            while j < len(sec) and sec[j] == '0':
                j += 1
            toks.append(('frac', j - i - 1)); i = j; continue
        toks.append(('lit', ch)); i += 1
    return toks

def _format_date(v, fmt):
    if isinstance(v, _dt.timedelta):
        total = int(v.total_seconds())
        sign = '-' if total < 0 else ''
        total = abs(total)
        return '%s%d:%02d:%02d' % (sign, total // 3600, (total % 3600) // 60, total % 60)
    if isinstance(v, _dt.time):
        dtv = _dt.datetime(1900, 1, 1, v.hour, v.minute, v.second, v.microsecond)
    elif isinstance(v, _dt.datetime):
        dtv = v
    else:
        dtv = _dt.datetime(v.year, v.month, v.day)
    if not fmt or fmt.strip().lower() == 'general' or not _re.search(r'[ymdhs]', _re.sub(r'"[^"]*"|\[[^\]]*\]|\\.', '', fmt), _re.I):
        if isinstance(v, _dt.time):
            return dtv.strftime('%H:%M:%S')
        s = dtv.strftime('%d-%m-%Y')
        if dtv.hour or dtv.minute or dtv.second:
            s += dtv.strftime(' %H:%M')
        return s
    sec = _clean_brackets(_split_sections(fmt)[0])
    toks = _date_tokens(sec)
    has_ampm = any(k == 'tok' and t.upper() in ('AM/PM', 'A/P') for k, t in toks)
    # decide whether each 'm' is month or minute
    kinds = [(k, t.lower() if k == 'tok' else t) for k, t in toks]
    for idx, (k, t) in enumerate(kinds):
        if k == 'tok' and t in ('m', 'mm'):
            prev = next((kinds[j][1] for j in range(idx - 1, -1, -1) if kinds[j][0] in ('tok', 'elapsed')), None)
            nxt = next((kinds[j][1] for j in range(idx + 1, len(kinds)) if kinds[j][0] in ('tok', 'elapsed')), None)
            if (prev in ('h', 'hh', 'h', 'hh')) or (nxt in ('s', 'ss')):
                kinds[idx] = ('min', t)
    out = ''
    for (k, t), (_, orig) in zip(kinds, toks):
        if k == 'lit':
            out += t
        elif k == 'elapsed':
            total = dtv.hour * 3600 + dtv.minute * 60 + dtv.second
            out += str(total // 3600) if t[0] == 'h' else (str(total // 60) if t[0] == 'm' else str(total))
        elif k == 'frac':
            out += ('%06d' % dtv.microsecond)[:t]
        elif k == 'min':
            out += ('%02d' if t == 'mm' else '%d') % dtv.minute
        else:
            if t == 'yyyy': out += '%04d' % dtv.year
            elif t == 'yy': out += '%02d' % (dtv.year % 100)
            elif t == 'mmmmm': out += _MONTHS[dtv.month - 1][0]
            elif t == 'mmmm': out += _MONTHS[dtv.month - 1]
            elif t == 'mmm': out += _MONTHS[dtv.month - 1][:3]
            elif t == 'mm': out += '%02d' % dtv.month
            elif t == 'm': out += str(dtv.month)
            elif t == 'dddd': out += _DAYS[dtv.weekday()]
            elif t == 'ddd': out += _DAYS[dtv.weekday()][:3]
            elif t == 'dd': out += '%02d' % dtv.day
            elif t == 'd': out += str(dtv.day)
            elif t in ('hh', 'h'):
                hh = dtv.hour
                if has_ampm:
                    hh = hh % 12 or 12
                out += ('%02d' if t == 'hh' else '%d') % hh
            elif t == 'ss': out += '%02d' % dtv.second
            elif t == 's': out += str(dtv.second)
            elif t in ('am/pm', 'a/p'):
                am = dtv.hour < 12
                if t == 'am/pm':
                    out += ('AM' if am else 'PM') if orig.isupper() else ('am' if am else 'pm')
                else:
                    out += ('A' if am else 'P') if orig.isupper() else ('a' if am else 'p')
    return out

def _display_text(value, fmt):
    if value is None:
        return '', 's'
    if isinstance(value, bool):
        return ('TRUE' if value else 'FALSE'), 'b'
    if isinstance(value, (_dt.datetime, _dt.date, _dt.time, _dt.timedelta)):
        return _format_date(value, fmt), 'd'
    if isinstance(value, (int, float, _Dec)):
        try:
            f = float(value)
            if f != f or f in (float('inf'), float('-inf')):
                return str(value), 's'
            return _format_number(value if not isinstance(value, _Dec) else f, fmt), 'n'
        except Exception:
            return str(value), 'n'
    s = str(value)
    return s, 's'

# ------------------------------------------------------------ sheet model
class _Cell(object):
    __slots__ = ('text', 'kind', 'bold', 'italic', 'underline', 'strike', 'size', 'color', 'fill',
                 'halign', 'valign', 'wrap', 'indent', 'borders')

_BORDER_W = {'hair': 0.25, 'thin': 0.5, 'dashed': 0.5, 'dotted': 0.5, 'dashDot': 0.5, 'dashDotDot': 0.5,
             'mediumDashed': 1.0, 'mediumDashDot': 1.0, 'mediumDashDotDot': 1.0, 'slantDashDot': 1.0,
             'medium': 1.0, 'double': 1.2, 'thick': 1.8}
_BORDER_DASH = {'dashed': (3, 2), 'mediumDashed': (4, 2), 'dotted': (1, 1.2), 'dashDot': (3, 1.5, 1, 1.5),
                'dashDotDot': (3, 1.5, 1, 1.5, 1, 1.5), 'hair': (1, 1)}

def _read_cell(cell, theme):
    c = _Cell()
    fmt = cell.number_format
    c.text, c.kind = _display_text(cell.value, fmt)
    f = cell.font
    c.bold = bool(f.b) if f is not None else False
    c.italic = bool(f.i) if f is not None else False
    c.underline = bool(f is not None and f.u and f.u != 'none')
    c.strike = bool(f is not None and f.strike)
    try:
        c.size = float(f.sz) if f is not None and f.sz else 11.0
    except Exception:
        c.size = 11.0
    c.color = _color_hex(f.color, theme, None) if f is not None else None
    fill = None
    try:
        fl = cell.fill
        if fl is not None and fl.fill_type == 'solid':
            fill = _color_hex(fl.fgColor, theme, None)
            if fill is not None and fill.upper() == 'FFFFFF':
                fill = None
    except Exception:
        fill = None
    c.fill = fill
    al = cell.alignment
    c.halign = (al.horizontal or 'general') if al is not None else 'general'
    c.valign = (al.vertical or 'bottom') if al is not None else 'bottom'
    c.wrap = bool(al.wrap_text) if al is not None else False
    c.indent = float(al.indent or 0) if al is not None else 0
    b = {}
    try:
        bd = cell.border
        for side in ('left', 'right', 'top', 'bottom'):
            sd = getattr(bd, side, None)
            if sd is not None and sd.style:
                b[side] = (_BORDER_W.get(sd.style, 0.5), _color_hex(sd.color, theme, '000000'), sd.style)
    except Exception:
        pass
    c.borders = b
    return c

class _Sheet(object):
    pass

def _load_sheet(ws, theme):
    cells_raw = getattr(ws, '_cells', None)
    if cells_raw is None:
        return None
    # --- find real extents (ignore huge empty formatted areas)
    items, min_r, max_r, min_c, max_c = [], None, 0, None, 0
    for (r, c), cell in list(cells_raw.items()):
        try:
            has_val = cell.value is not None and not (isinstance(cell.value, str) and not cell.value.strip())
            vis = False
            if not has_val:
                try:
                    fl = cell.fill
                    if fl is not None and fl.fill_type == 'solid':
                        col = _color_hex(fl.fgColor, theme, None)
                        vis = col is not None and col.upper() != 'FFFFFF'
                except Exception:
                    pass
                if not vis:
                    try:
                        bd = cell.border
                        vis = any(getattr(getattr(bd, s, None), 'style', None) for s in ('left', 'right', 'top', 'bottom'))
                    except Exception:
                        pass
            if has_val or vis:
                items.append((r, c, cell))
                min_r = r if min_r is None else min(min_r, r)
                min_c = c if min_c is None else min(min_c, c)
                max_r, max_c = max(max_r, r), max(max_c, c)
        except Exception:
            continue
    merges = []
    try:
        for rng in ws.merged_cells.ranges:
            merges.append((rng.min_row, rng.min_col, rng.max_row, rng.max_col))
            if rng.min_row < 100000 and rng.max_row <= max_r + 1000:
                pass
    except Exception:
        pass
    if not items:
        return None
    # merged areas can extend the used range only if their top-left is inside it
    merges = [m for m in merges if m[0] <= max_r and m[1] <= max_c]
    for (r1, c1, r2, c2) in merges:
        max_r, max_c = max(max_r, min(r2, max_r + 50)), max(max_c, min(c2, max_c + 50))

    sh = _Sheet()
    sh.name = ws.title
    sh.r0, sh.r1, sh.c0, sh.c1 = min_r, max_r, min_c, max_c
    # --- column widths
    fmt_pr = ws.sheet_format
    base_w = fmt_pr.defaultColWidth or ((fmt_pr.baseColWidth or 8) + 0.43)
    colw, colhidden = {}, set()
    for key, cd in list(ws.column_dimensions.items()):
        try:
            lo = cd.min or 0
            hi = cd.max or lo
            if not lo:
                from openpyxl.utils import column_index_from_string
                lo = hi = column_index_from_string(key)
            for ci in range(lo, min(hi, max_c) + 1):
                if cd.hidden:
                    colhidden.add(ci)
                if cd.width is not None:
                    colw[ci] = cd.width
        except Exception:
            continue
    sh.cols = [c for c in range(min_c, max_c + 1) if c not in colhidden]
    sh.colw = {c: max(2.0, ((colw.get(c, base_w) * 7 + 5) * 0.75)) for c in sh.cols}
    # --- row heights
    def_h = fmt_pr.defaultRowHeight or 15.0
    rowh, rowhidden, custom = {}, set(), set()
    for r, rd in list(ws.row_dimensions.items()):
        if r < min_r or r > max_r:
            continue
        if rd.hidden:
            rowhidden.add(r)
        if rd.height is not None:
            rowh[r] = float(rd.height)
            custom.add(r)
    sh.rows = [r for r in range(min_r, max_r + 1) if r not in rowhidden]
    sh.def_h, sh.rowh, sh.custom = def_h, rowh, custom
    # --- cells
    sh.cells = {}
    for r, c, cell in items:
        if r in rowhidden or c in colhidden:
            continue
        sh.cells[(r, c)] = _read_cell(cell, theme)
    # merged cells also need style of their master even if it was filtered as 'empty'
    sh.master, sh.covered = {}, set()
    for (r1, c1, r2, c2) in merges:
        sh.master[(r1, c1)] = (r1, c1, r2, c2)
        for rr in range(r1, min(r2, max_r) + 1):
            for cc in range(c1, min(c2, max_c) + 1):
                if (rr, cc) != (r1, c1):
                    sh.covered.add((rr, cc))
        if (r1, c1) not in sh.cells:
            try:
                sh.cells[(r1, c1)] = _read_cell(ws.cell(row=r1, column=c1), theme)
            except Exception:
                pass
        # borders/fills of a merged area are stored on its other cells too
        try:
            br = ws.cell(row=r1, column=c2)
            bb = ws.cell(row=r2, column=c1)
            m = sh.cells.get((r1, c1))
            if m is not None:
                if br.border is not None and br.border.right is not None and br.border.right.style:
                    m.borders['right'] = (_BORDER_W.get(br.border.right.style, 0.5), _color_hex(br.border.right.color, theme, '000000'), br.border.right.style)
                if bb.border is not None and bb.border.bottom is not None and bb.border.bottom.style:
                    m.borders['bottom'] = (_BORDER_W.get(bb.border.bottom.style, 0.5), _color_hex(bb.border.bottom.color, theme, '000000'), bb.border.bottom.style)
        except Exception:
            pass
    try:
        sh.landscape_hint = (ws.page_setup.orientation == 'landscape')
    except Exception:
        sh.landscape_hint = False
    return sh

# ---------------------------------------------------------- text layout
_PAD = 2.0

def _wrap_lines(text, bold, italic, size, avail):
    lines = []
    for para in text.replace('\r\n', '\n').replace('\r', '\n').split('\n'):
        words = para.split(' ')
        cur = ''
        for w in words:
            trial = w if not cur else cur + ' ' + w
            if _text_width(trial, bold, italic, size) <= avail:
                cur = trial
                continue
            if cur:
                lines.append(cur)
                cur = ''
            # a single word longer than the cell: break it by characters
            if _text_width(w, bold, italic, size) <= avail:
                cur = w
            else:
                piece = ''
                for ch in w:
                    if piece and _text_width(piece + ch, bold, italic, size) > avail:
                        lines.append(piece)
                        piece = ch
                    else:
                        piece += ch
                cur = piece
        lines.append(cur)
    return lines

def _auto_wrap(sh, smart):
    """Excel clips text that does not fit when the next cell is filled. We never
    want a cut line, so such text is wrapped (and its row grows) instead."""
    if not smart:
        return
    for r in sh.rows:
        for c in sh.cols:
            cell = sh.cells.get((r, c))
            if cell is None or cell.wrap or cell.kind != 's' or not cell.text.strip() or (r, c) in sh.covered:
                continue
            m = sh.master.get((r, c))
            if m is not None and m[2] > m[0]:
                continue
            width = sum(sh.colw.get(cc, 0) for cc in range(c, (m[3] if m else c) + 1) if cc in sh.colw)
            avail = width - 2 * _PAD - cell.indent * 6
            text = cell.text.replace('\r', ' ').replace('\n', ' ')
            tw = _text_width(text, cell.bold, cell.italic, cell.size)
            if tw <= avail:
                continue
            halign = cell.halign
            if halign in ('general', 'fill', 'distributed', 'justify'):
                halign = 'left'
            free_r = free_l = 0.0
            if m is None:
                pos = sh.cols.index(c)
                if halign in ('left', 'center'):
                    for nxt in sh.cols[pos + 1:]:
                        nc = sh.cells.get((r, nxt))
                        if (nc is not None and nc.text.strip()) or (r, nxt) in sh.covered or (r, nxt) in sh.master:
                            break
                        free_r += sh.colw[nxt]
                if halign in ('right', 'center'):
                    for prv in reversed(sh.cols[:pos]):
                        nc = sh.cells.get((r, prv))
                        if (nc is not None and nc.text.strip()) or (r, prv) in sh.covered or (r, prv) in sh.master:
                            break
                        free_l += sh.colw[prv]
            room = avail + (min(free_l, free_r) * 2 if halign == 'center' else free_l + free_r)
            if tw > room * 1.2:
                cell.wrap = True

def _row_heights(sh):
    """Real height of every row; rows grow so wrapped text is never cut."""
    heights = {}
    for r in sh.rows:
        base = sh.rowh.get(r)
        max_sz = 0.0
        need = 0.0
        for c in sh.cols:
            cell = sh.cells.get((r, c))
            if cell is None or (r, c) in sh.covered:
                continue
            max_sz = max(max_sz, cell.size if cell.text else 0)
            if cell.wrap and cell.text:
                m = sh.master.get((r, c))
                if m is not None and m[2] > m[0]:
                    continue        # multi-row merge: keep the Excel height
                width = sum(sh.colw.get(cc, 0) for cc in range(c, (m[3] if m else c) + 1) if cc in sh.colw)
                lines = _wrap_lines(cell.text, cell.bold, cell.italic, cell.size, max(4.0, width - 2 * _PAD - cell.indent * 6))
                need = max(need, len(lines) * cell.size * 1.2 + 4)
        if base is None:
            base = max(sh.def_h, max_sz * 1.36 if max_sz else 0)
        heights[r] = max(base, need, 4.0)
    return heights

# ------------------------------------------------------------- pagination
class _Page(object):
    pass

def _plan_sheet(sh, opts):
    image_mode = bool(opts.get('image_mode'))
    pw, ph = _PAGE_SIZES.get(opts['page_size'], _A4)
    M = 24.0
    foot = 20.0 if opts['footer'] else 8.0
    total_w = sum(sh.colw[c] for c in sh.cols)
    orient = opts['orientation']
    if image_mode:
        # the whole sheet becomes one picture: page = exactly the size of the content
        M = 14.0
        img_scale = min(1.0, float(opts.get('max_width_pt', 2600)) / total_w)
        pw = total_w * img_scale + 2 * M
        ph = float(opts.get('max_height_pt', 6000))
        foot = 0.0
    elif orient == 'auto':
        if not opts['fit_width']:
            orient = 'landscape' if (sh.landscape_hint or total_w > pw - 2 * M) else 'portrait'
        else:
            scale_p = min(1.0, (pw - 2 * M) / total_w)
            orient = 'portrait' if (scale_p >= 0.75 and not sh.landscape_hint) or scale_p >= 0.999 else 'landscape'
    if image_mode:
        pass
    elif orient == 'landscape':
        pw, ph = max(pw, ph), min(pw, ph)
    else:
        pw, ph = min(pw, ph), max(pw, ph)
    usable_w = pw - 2 * M
    usable_h = ph - M - M - foot
    # ---- column bands
    MIN_SCALE = 0.55
    bands = []
    if image_mode:
        bands = [list(sh.cols)]
    elif opts['fit_width'] and total_w * MIN_SCALE <= usable_w:
        bands = [list(sh.cols)]
    else:
        cap = usable_w / 0.7 if opts['fit_width'] else usable_w
        cur, cur_w = [], 0.0
        for c in sh.cols:
            w = sh.colw[c]
            if cur and cur_w + w > cap:
                bands.append(cur)
                cur, cur_w = [], 0.0
            cur.append(c)
            cur_w += w
        if cur:
            bands.append(cur)
    _auto_wrap(sh, opts.get('smart_wrap', True))
    heights = _row_heights(sh)
    # rows that must stay together (merged areas)
    keep = set()
    for (r1, c1, r2, c2) in sh.master.values():
        for rr in range(r1, r2):
            keep.add(rr)
    pages = []
    for band in bands:
        band_w = sum(sh.colw[c] for c in band)
        scale = min(1.0, usable_w / band_w) if (opts['fit_width'] or band_w > usable_w) else 1.0
        scale = max(scale, 0.25)
        if image_mode:
            scale = img_scale
        header = sh.rows[0] if (opts['repeat_header'] and len(sh.rows) > 1) else None
        hdr_h = heights[header] * scale if header is not None else 0.0
        idx = 0
        first = True
        while idx < len(sh.rows):
            page_rows, used = [], 0.0
            if not first and header is not None:
                page_rows.append(header)
                used += hdr_h
            start_len = len(page_rows)
            while idx < len(sh.rows):
                r = sh.rows[idx]
                rh = heights[r] * scale
                if page_rows and used + rh > usable_h and len(page_rows) > start_len:
                    # never split a merged block: move the whole block to the next page
                    j = len(page_rows) - 1
                    while j > start_len and page_rows[j - 1] in keep:
                        j -= 1
                    if page_rows[-1] in keep and j > start_len:
                        idx -= (len(page_rows) - j)
                        page_rows = page_rows[:j]
                    break
                page_rows.append(r)
                used += rh
                idx += 1
                if used > usable_h and len(page_rows) == start_len + 1:
                    break       # a single very tall row: keep it, it will be clipped
            if len(page_rows) == start_len:        # safety: avoid endless loop
                page_rows.append(sh.rows[idx]); idx += 1
            p = _Page()
            p.sheet, p.rows, p.cols, p.scale = sh, page_rows, band, scale
            p.pw, p.ph, p.heights = pw, ph, heights
            p.M = M
            if image_mode:      # shrink the picture to the real content height
                p.ph = 2 * M + sum(heights[r] for r in page_rows) * scale
            pages.append(p)
            first = False
    return pages

# ---------------------------------------------------------------- drawing
def _hex(c, default='000000'):
    return _HexColor('#' + (c or default))

def _draw_text_line(cv, text, bold, italic, size, x, y, color, underline=False, strike=False):
    cv.setFillColor(_hex(color))
    cx = x
    if _use_complex(text):
        try:
            cx = x + _draw_complex(cv, text, size, x, y, color)
        except Exception:
            cx = x
            for font, seg in _segments(text, bold, italic):
                cv.setFont(font, size); cv.drawString(cx, y, seg); cx += _pdfmetrics.stringWidth(seg, font, size)
    else:
        for font, seg in _segments(text, bold, italic):
            cv.setFont(font, size)
            cv.drawString(cx, y, seg)
            cx += _pdfmetrics.stringWidth(seg, font, size)
    if underline or strike:
        w = cx - x
        cv.setStrokeColor(_hex(color)); cv.setLineWidth(max(0.4, size * 0.05)); cv.setDash()
        if underline:
            cv.line(x, y - size * 0.12, x + w, y - size * 0.12)
        if strike:
            cv.line(x, y + size * 0.3, x + w, y + size * 0.3)

def _draw_page(cv, pg, opts, page_no, total, brand):
    sh, s = pg.sheet, pg.scale
    cv.setPageSize((pg.pw, pg.ph))
    M = getattr(pg, 'M', 24.0)
    col_x, x = {}, M
    for c in pg.cols:
        col_x[c] = x
        x += sh.colw[c] * s
    row_y, y = {}, pg.ph - M
    for r in pg.rows:
        row_y[r] = y                       # top edge of the row
        y -= pg.heights[r] * s
    def col_w(c): return sh.colw[c] * s
    def row_h(r): return pg.heights[r] * s
    colset, rowset = set(pg.cols), set(pg.rows)
    # ---------- pass 1: fills
    for r in pg.rows:
        for c in pg.cols:
            if (r, c) in sh.covered:
                continue
            cell = sh.cells.get((r, c))
            if cell is None or not cell.fill:
                continue
            w, h = col_w(c), row_h(r)
            m = sh.master.get((r, c))
            if m:
                w = sum(col_w(cc) for cc in range(m[1], m[3] + 1) if cc in colset)
                h = sum(row_h(rr) for rr in range(m[0], m[2] + 1) if rr in rowset)
            cv.setFillColor(_hex(cell.fill))
            cv.rect(col_x[c], row_y[r] - h, w, h, stroke=0, fill=1)
    # ---------- pass 2: gridlines
    if opts['gridlines']:
        cv.setStrokeColor(_HexColor('#D4D4D8')); cv.setLineWidth(0.3); cv.setDash()
        left, right = col_x[pg.cols[0]], col_x[pg.cols[-1]] + col_w(pg.cols[-1])
        top, bottom = row_y[pg.rows[0]], row_y[pg.rows[-1]] - row_h(pg.rows[-1])
        merged_inner = set()
        for (r1, c1, r2, c2) in sh.master.values():
            for rr in range(r1, r2 + 1):
                for cc in range(c1, c2 + 1):
                    merged_inner.add((rr, cc))
        for r in pg.rows:
            yy = row_y[r] - row_h(r)
            cv.line(left, yy, right, yy)
        cv.line(left, top, right, top)
        for c in pg.cols:
            cv.line(col_x[c], top, col_x[c], bottom)
        cv.line(right, top, right, bottom)
        # erase grid inside merged cells
        cv.setFillColor(_HexColor('#FFFFFF'))
        for (r1, c1, r2, c2) in sh.master.values():
            if r1 in rowset and c1 in colset:
                w = sum(col_w(cc) for cc in range(c1, c2 + 1) if cc in colset)
                h = sum(row_h(rr) for rr in range(r1, r2 + 1) if rr in rowset)
                cell = sh.cells.get((r1, c1))
                cv.setFillColor(_hex(cell.fill) if cell is not None and cell.fill else _HexColor('#FFFFFF'))
                cv.rect(col_x[c1] + 0.3, row_y[r1] - h + 0.3, w - 0.6, h - 0.6, stroke=0, fill=1)
    # ---------- pass 3: explicit borders
    for r in pg.rows:
        for c in pg.cols:
            if (r, c) in sh.covered:
                continue
            cell = sh.cells.get((r, c))
            if cell is None or not cell.borders:
                continue
            w, h = col_w(c), row_h(r)
            m = sh.master.get((r, c))
            if m:
                w = sum(col_w(cc) for cc in range(m[1], m[3] + 1) if cc in colset)
                h = sum(row_h(rr) for rr in range(m[0], m[2] + 1) if rr in rowset)
            x0, y1 = col_x[c], row_y[r]
            y0 = y1 - h
            for side, (bw, bc, bstyle) in cell.borders.items():
                cv.setStrokeColor(_hex(bc)); cv.setLineWidth(max(0.25, bw * max(s, 0.6)))
                dash = _BORDER_DASH.get(bstyle)
                cv.setDash(*dash) if dash else cv.setDash()
                if side == 'left': cv.line(x0, y0, x0, y1)
                elif side == 'right': cv.line(x0 + w, y0, x0 + w, y1)
                elif side == 'top': cv.line(x0, y1, x0 + w, y1)
                elif side == 'bottom': cv.line(x0, y0, x0 + w, y0)
    cv.setDash()
    # ---------- pass 4: text
    for r in pg.rows:
        for c in pg.cols:
            if (r, c) in sh.covered:
                continue
            cell = sh.cells.get((r, c))
            if cell is None or not cell.text.strip():
                continue
            m = sh.master.get((r, c))
            cw, ch_ = col_w(c), row_h(r)
            if m:
                cw = sum(col_w(cc) for cc in range(m[1], m[3] + 1) if cc in colset)
                ch_ = sum(row_h(rr) for rr in range(m[0], m[2] + 1) if rr in rowset)
            x0, ytop = col_x[c], row_y[r]
            size = max(3.5, cell.size * s)
            halign = cell.halign
            if halign in ('general', 'fill', 'distributed', 'justify'):
                halign = 'right' if cell.kind in ('n', 'd') else ('center' if cell.kind == 'b' else 'left')
            pad = _PAD * max(s, 0.6)
            ind = cell.indent * 6 * s
            avail = cw - 2 * pad - ind
            clip_x, clip_w = x0, cw
            lines = None
            if cell.wrap:
                lines = _wrap_lines(cell.text, cell.bold, cell.italic, size, max(3.0, avail))
            else:
                text = cell.text.replace('\r', ' ').replace('\n', ' ')
                tw = _text_width(text, cell.bold, cell.italic, size)
                if tw > avail and not m:
                    # let text flow into empty neighbouring cells like Excel does
                    extra_r = extra_l = 0.0
                    if halign in ('left', 'center') and cell.kind == 's':
                        cc = c
                        idxs = pg.cols
                        pos = idxs.index(c)
                        for nxt in idxs[pos + 1:]:
                            nc = sh.cells.get((r, nxt))
                            if (nc is not None and nc.text.strip()) or (r, nxt) in sh.covered or (r, nxt) in sh.master:
                                break
                            extra_r += col_w(nxt)
                            if tw <= avail + extra_r:
                                break
                    if halign in ('right', 'center') and cell.kind == 's':
                        idxs = pg.cols
                        pos = idxs.index(c)
                        for prv in reversed(idxs[:pos]):
                            nc = sh.cells.get((r, prv))
                            if (nc is not None and nc.text.strip()) or (r, prv) in sh.covered or (r, prv) in sh.master:
                                break
                            extra_l += col_w(prv)
                            if tw <= avail + extra_l:
                                break
                    if halign == 'center':
                        e = min(extra_l, extra_r)
                        extra_l = extra_r = e
                    clip_x, clip_w = x0 - extra_l, cw + extra_l + extra_r
                    avail_total = avail + extra_l + extra_r
                    if tw > avail_total:
                        # shrink to fit (never below 55%), the rest is clipped
                        k = max(0.55, avail_total / tw)
                        size *= k
                        tw = _text_width(text, cell.bold, cell.italic, size)
                elif tw > avail:
                    k = max(0.55, avail / tw)
                    size *= k
                lines = [text]
            lh = size * 1.2
            block = len(lines) * lh
            if cell.valign == 'top':
                ty = ytop - pad
            elif cell.valign == 'center':
                ty = ytop - (ch_ - block) / 2.0
            else:
                ty = ytop - ch_ + block + pad * 0.5
            cv.saveState()
            path = cv.beginPath()
            path.rect(clip_x, ytop - ch_, clip_w, ch_)
            cv.clipPath(path, stroke=0, fill=0)
            for i, ln in enumerate(lines):
                if not ln:
                    continue
                tw = _text_width(ln, cell.bold, cell.italic, size)
                if halign == 'left':
                    tx = x0 + pad + ind
                elif halign == 'center':
                    tx = x0 + (cw - tw) / 2.0
                else:
                    tx = x0 + cw - pad - tw
                base_y = ty - i * lh - size * 0.95
                _draw_text_line(cv, ln, cell.bold, cell.italic, size, tx, base_y, cell.color, cell.underline, cell.strike)
            cv.restoreState()
    # ---------- footer
    if opts['footer']:
        cv.setFillColor(_HexColor('#6B7280')); cv.setFont('Helvetica', 7)
        name = sh.name if len(sh.name) < 60 else sh.name[:57] + '...'
        for font, seg in _segments(name, False, False)[:1]:
            pass
        cv.drawString(M, 14, '')
        _draw_text_line(cv, name, False, False, 7, M, 14, '6B7280')
        cv.setFillColor(_HexColor('#6B7280')); cv.setFont('Helvetica', 7)
        cv.drawCentredString(pg.pw / 2.0, 14, 'Page %d of %d' % (page_no, total))
        cv.drawRightString(pg.pw - M, 14, brand)

# --------------------------------------------------------------- entry point
def _open_workbook(path):
    from openpyxl import load_workbook, Workbook
    with open(path, 'rb') as f:
        head = f.read(8)
    if head[:2] == b'PK':
        import io as _io
        with open(path, 'rb') as fh:          # a file object skips openpyxl's extension check
            return load_workbook(_io.BytesIO(fh.read()), data_only=True, read_only=False, keep_links=False)
    if head[:4] == b'\xd0\xcf\x11\xe0':          # old binary .xls  (needs the small 'xlrd' package)
        try:
            import xlrd
        except ImportError:
            raise ValueError('Old .xls format is not supported on this server. Please save the file as .xlsx in Excel and try again.')
        try:
            try:
                book = xlrd.open_workbook(path, formatting_info=True)    # also gives column widths
            except Exception:
                book = xlrd.open_workbook(path)
        except Exception:
            raise ValueError('Old .xls format could not be read. Please save the file as .xlsx in Excel and try again.')
        from openpyxl.utils import get_column_letter
        wb = Workbook()
        wb.remove(wb.active)
        for idx in range(book.nsheets):
            sh = book.sheet_by_index(idx)
            if getattr(sh, 'visibility', 0) != 0:
                continue
            ws = wb.create_sheet(str(sh.name)[:31] or 'Sheet%d' % (idx + 1))
            for r in range(sh.nrows):
                for c in range(sh.ncols):
                    ctype = sh.cell_type(r, c)
                    if ctype in (0, 5, 6):          # empty / error / blank
                        continue
                    val = sh.cell_value(r, c)
                    if ctype == 3:                   # date
                        try:
                            val = xlrd.xldate_as_datetime(val, book.datemode)
                        except Exception:
                            pass
                    elif ctype == 4:
                        val = bool(val)
                    elif ctype == 2 and float(val) == int(val) and abs(val) < 1e15:
                        val = int(val)
                    ws.cell(row=r + 1, column=c + 1, value=val)
            try:
                for c, info in (getattr(sh, 'colinfo_map', {}) or {}).items():
                    if info.width:
                        ws.column_dimensions[get_column_letter(c + 1)].width = max(2.0, info.width / 256.0)
                    if info.hidden:
                        ws.column_dimensions[get_column_letter(c + 1)].hidden = True
            except Exception:
                pass
        if not wb.worksheets:
            raise ValueError('Excel file is empty')
        return wb
    raise ValueError('This does not look like a valid Excel file.')

def excel_to_pdf_file(input_path, output_path, page_size='A4', orientation='auto', gridlines=True,
                      repeat_header=True, fit_width=True, footer=True, smart_wrap=True, brand='BharatOS-Tools', max_pages=500,
                      image_mode=False, max_width_pt=2600, max_height_pt=6000):
    _init_fonts()
    opts = {'page_size': (page_size or 'A4').upper(), 'orientation': (orientation or 'auto').lower(),
            'gridlines': bool(gridlines), 'repeat_header': bool(repeat_header), 'fit_width': bool(fit_width),
            'footer': bool(footer), 'smart_wrap': bool(smart_wrap), 'image_mode': bool(image_mode),
            'max_width_pt': max_width_pt, 'max_height_pt': max_height_pt}
    if opts['page_size'] not in _PAGE_SIZES:
        opts['page_size'] = 'A4'
    if opts['orientation'] not in ('auto', 'portrait', 'landscape'):
        opts['orientation'] = 'auto'
    wb = _open_workbook(input_path)
    theme = _theme_palette(wb)
    plans = []
    total_cells = 0
    for ws in wb.worksheets:
        if getattr(ws, 'sheet_state', 'visible') != 'visible':
            continue
        try:
            sh = _load_sheet(ws, theme)
        except Exception:
            import traceback; traceback.print_exc()
            continue
        if sh is None:
            continue
        total_cells += len(sh.cells)
        if total_cells > 350000:
            raise ValueError('This workbook is too large for one conversion (more than 350,000 filled cells). Please split it into smaller files.')
        plans.extend(_plan_sheet(sh, opts))
        if len(plans) > max_pages:
            raise ValueError('This workbook needs more than %d pages. Please split the file into smaller files.' % max_pages)
    try:
        wb.close()
    except Exception:
        pass
    if not plans:
        raise ValueError('Excel file is empty')
    cv = _rl_canvas.Canvas(output_path, pagesize=(plans[0].pw, plans[0].ph))
    cv.setTitle('Excel to PDF'); cv.setAuthor(brand)
    total = len(plans)
    for i, pg in enumerate(plans, start=1):
        _draw_page(cv, pg, opts, i, total, brand)
        cv.showPage()
    cv.save()
    return {'pages': total, 'sheets': len({id(p.sheet) for p in plans}),
            'page_sheets': [p.sheet.name for p in plans], 'page_sizes': [(p.pw, p.ph) for p in plans]}


# ========== 6. EXCEL TO PDF ==========
def _flag(value, default=True):
    if value is None or str(value).strip() == '':
        return default
    return str(value).strip().lower() in ('1', 'true', 'yes', 'on')

@app.route('/excel-to-pdf', methods=['POST'])
def excel_to_pdf():
    if not processing_lock.acquire(timeout=300):
        return 'Server busy. Try again.', 503
    temp_dir = tempfile.mkdtemp()
    try:
        if 'file' not in request.files:
            return 'No file uploaded', 400
        file = request.files['file']
        valid, msg = validate_file(file, allowed_ext=['.xlsx', '.xlsm', '.xls'], max_size=15 * 1024 * 1024)
        if not valid:
            return msg, 400
        input_path = os.path.join(temp_dir, 'input.xlsx')
        output_path = os.path.join(temp_dir, 'output.pdf')
        file.save(input_path)

        # optional settings sent by the website (all have safe defaults)
        opts = dict(
            page_size=request.form.get('page_size', 'A4'),
            orientation=request.form.get('orientation', 'auto'),
            gridlines=_flag(request.form.get('gridlines'), True),
            repeat_header=_flag(request.form.get('repeat_header'), True),
            fit_width=_flag(request.form.get('fit_width'), True),
            footer=_flag(request.form.get('footer'), True),
            smart_wrap=_flag(request.form.get('smart_wrap'), True),
        )
        try:
            info = excel_to_pdf_file(input_path, output_path, **opts)
        except ValueError as e:
            return str(e), 400
        except Exception as e:
            import traceback
            traceback.print_exc()
            return 'Cannot read this Excel file. It may be damaged or password protected.', 400

        base = re.sub(r'[\\/\*\?\:"<>|]', '_', file.filename.rsplit('.', 1)[0])[:80] or 'excel'
        response = send_file(output_path, mimetype='application/pdf', as_attachment=True, download_name=f'{base}.pdf')
        response.headers['X-Pages'] = str(info['pages'])
        response.headers['X-Sheets'] = str(info['sheets'])
        response.headers['Access-Control-Expose-Headers'] = 'X-Pages, X-Sheets'
        return response
    except Exception as e:
        import traceback
        traceback.print_exc()
        return f'Error: {str(e)}', 500
    finally:
        processing_lock.release()
        cleanup_dir(temp_dir)

# ======================================================================
#  PDF -> EXCEL ENGINE  (BharatOS-Tools)
#  Rebuilds the real table structure of a PDF in Excel:
#   * bordered tables  -> one Excel table (pdfplumber)
#   * forms / tickets / invoices / statements without borders -> text is
#     split into columns by its position on the page, so every value
#     lands in its own cell (never "whole line in one cell")
#   * normal paragraphs -> one line per row
#  Numbers become real numbers, bold text stays bold, one sheet per page.
# ======================================================================
import re as _re
import statistics as _stats
import subprocess as _subprocess

_PX_NUM = _re.compile(r'(\(?)(-?)\s*(Rs\.?|INR|[\u20b9$\u20ac\u00a3])?\s*(\d{1,3}(?:,\d{2,3})+(?:\.\d+)?|\d+(?:\.\d+)?)(\)?)\s*(%?)$')
_PX_BOLD = ('bold', 'black', 'heavy', 'semibold', 'demi')

def _px_value(text, numbers=True):
    """-> (value, number_format or None). IDs, phone numbers, dates stay text."""
    t = (text or '').strip()
    if not numbers or not t:
        return t, None
    m = _PX_NUM.match(t)
    if not m:
        return t, None
    paren_open, minus, sym, digits, paren_close, pct = m.groups()
    if paren_open and not paren_close or paren_close and not paren_open:
        return t, None
    raw = digits.replace(',', '')
    int_part, _, frac = raw.partition('.')
    if len(int_part) > 15:
        return t, None
    if len(int_part) > 1 and int_part.startswith('0'):
        return t, None                                  # 0000003940, 007 ... keep as text
    if len(int_part) >= 10 and not frac and not sym and not ',' in digits:
        return t, None                                  # phone numbers / long IDs
    try:
        val = float(raw)
    except ValueError:
        return t, None
    if minus or (paren_open and paren_close):
        val = -val
    if pct:
        val = val / 100.0
    base = '#,##0' if ',' in digits else '0'
    if frac:
        base += '.' + '0' * len(frac)
    if sym:
        s = 'Rs.' if sym.upper().startswith(('RS', 'INR')) else sym
        base = '"%s "%s' % (s, base) if s in ('Rs.',) else '"%s"%s' % (s, base)
    fmt = base + ('%' if pct else '')
    if not frac and not pct and ',' not in digits and not sym:
        fmt = None
    if val == int(val) and not frac and not pct:
        val = int(val)
    return val, fmt

# --------------------------------------------------------------- reading
class _PxSeg(object):
    __slots__ = ('x0', 'x1', 'text', 'bold')
    def __init__(self, x0, x1, text, bold):
        self.x0, self.x1, self.text, self.bold = x0, x1, text, bold

class _PxLine(object):
    __slots__ = ('top', 'bottom', 'size', 'segs')

def _px_split_segments(words, gap_thr):
    words = sorted(words, key=lambda w: w['x0'])
    segs, cur = [], []
    for w in words:
        if cur and w['x0'] - cur[-1]['x1'] > gap_thr:
            segs.append(cur); cur = []
        cur.append(w)
    if cur:
        segs.append(cur)
    out = []
    for grp in segs:
        chars = sum(len(w['text']) for w in grp) or 1
        bold_chars = sum(len(w['text']) for w in grp if w.get('bold'))
        out.append(_PxSeg(grp[0]['x0'], grp[-1]['x1'], ' '.join(w['text'] for w in grp), bold_chars * 2 >= chars))
    return out

def _px_words_to_lines(words):
    lines = []
    for w in sorted(words, key=lambda w: (w['top'], w['x0'])):
        mid = (w['top'] + w['bottom']) / 2.0
        if lines and abs(mid - lines[-1]['mid']) <= 0.5 * max(w['size'], lines[-1]['size']):
            ln = lines[-1]
            ln['words'].append(w)
            ln['top'] = min(ln['top'], w['top']); ln['bottom'] = max(ln['bottom'], w['bottom'])
            ln['size'] = max(ln['size'], w['size'])
        else:
            lines.append({'mid': mid, 'top': w['top'], 'bottom': w['bottom'], 'size': w['size'], 'words': [w]})
    out = []
    for ln in lines:
        l = _PxLine()
        l.top, l.bottom, l.size = ln['top'], ln['bottom'], ln['size']
        l.segs = _px_split_segments(ln['words'], max(4.8, 0.55 * ln['size']))
        out.append(l)
    return out

def _px_page_plumber(page):
    """-> (page_width, items) ; items = ('table', top, bottom, rows) | ('line', _PxLine)"""
    W = float(page.width)
    tables = []
    try:
        for t in page.find_tables():
            rows = t.extract() or []
            clean = [[(c or '').replace('\n', ' ').strip() for c in r] for r in rows]
            clean = [r for r in clean if any(r)]
            if len(clean) < 2:
                continue
            ncols = max(len(r) for r in clean)
            clean = [r + [''] * (ncols - len(r)) for r in clean]
            keep = [j for j in range(ncols) if any(r[j] for r in clean)]
            clean = [[r[j] for j in keep] for r in clean]
            if len(keep) < 2:
                continue
            filled = sum(1 for r in clean for c in r if c) / float(len(clean) * len(keep))
            if filled < 0.3:
                continue
            tables.append((t.bbox, clean))
    except Exception:
        tables = []
    words = []
    for w in page.extract_words(x_tolerance=1.5, y_tolerance=2, keep_blank_chars=False, use_text_flow=False, extra_attrs=['fontname', 'size']):
        cx, cy = (w['x0'] + w['x1']) / 2.0, (w['top'] + w['bottom']) / 2.0
        if any(b[0] - 1 <= cx <= b[2] + 1 and b[1] - 1 <= cy <= b[3] + 1 for b, _ in tables):
            continue
        w['bold'] = any(k in (w.get('fontname') or '').lower() for k in _PX_BOLD)
        words.append(w)
    items = [('table', b[1], b[3], rows) for b, rows in tables]
    items += [('line', l) for l in _px_words_to_lines(words)]
    items.sort(key=lambda it: it[1] if it[0] == 'table' else it[1].top)
    return W, items

def _px_page_text(text):
    """Fallback when pdfplumber is not installed: Ghostscript 'txtwrite' text keeps the layout with spaces."""
    items, width = [], 1.0
    for i, raw in enumerate(text.split('\n')):
        raw = raw.rstrip()
        if not raw.strip():
            continue
        l = _PxLine(); l.top, l.bottom, l.size = i * 12.0, i * 12.0 + 10.0, 10.0
        l.segs = [_PxSeg(float(m.start()), float(m.end()), m.group(), False) for m in _re.finditer(r'\S+(?: {1,2}\S+)*', raw)]
        width = max(width, len(raw))
        items.append(('line', l))
    return float(width), items

# ------------------------------------------------------------ layout
def _px_layout(items, page_w, tol):
    """-> rows: {'cells': {col: (text, bold)}, 'merges': [(c1, c2)], 'kind': 'text'|'grid'|'table', 'hdr': bool, 'blank': bool, 'size': float}"""
    rows, pending = [], []
    prev_bottom, prev_size = None, 10.0

    def flush():
        nonlocal prev_bottom, prev_size
        if not pending:
            return
        lines = list(pending); pending.clear()
        multi = [len(l.segs) >= 2 for l in lines]
        groups, cur = [], []
        for i, l in enumerate(lines):
            if multi[i]:
                if cur and l.top - cur[-1].bottom > 1.8 * max(l.size, cur[-1].size):
                    groups.append(('grid', cur)); cur = []
                cur.append(l)
            else:
                if cur:
                    groups.append(('grid', cur)); cur = []
                groups.append(('text', [l]))
        if cur:
            groups.append(('grid', cur))
        for kind, grp in groups:
            if kind == 'text':
                l = grp[0]
                blank = prev_bottom is not None and (l.top - prev_bottom) > 0.7 * max(l.size, prev_size)
                rows.append({'cells': {0: (l.segs[0].text, l.segs[0].bold)}, 'merges': [], 'kind': 'text', 'hdr': False, 'blank': blank, 'size': l.size})
                prev_bottom, prev_size = l.bottom, l.size
                continue
            ivs = sorted((s.x0, s.x1) for l in grp for s in l.segs if (s.x1 - s.x0) <= 0.6 * page_w)
            spans = []
            for a, b in ivs:
                if spans and a <= spans[-1][1] + tol:
                    spans[-1][1] = max(spans[-1][1], b)
                else:
                    spans.append([a, b])
            if not spans:
                spans = [[min(s.x0 for l in grp for s in l.segs), max(s.x1 for l in grp for s in l.segs)]]

            def span_of(s):
                cx = (s.x0 + s.x1) / 2.0
                k = next((k for k, sp in enumerate(spans) if sp[0] - tol <= cx <= sp[1] + tol), None)
                if k is None:
                    k = next((k for k, sp in enumerate(spans) if sp[1] >= s.x0 - tol), len(spans) - 1)
                return k
            # A header that does not sit exactly above its numbers (e.g. 'Amount' left of right-aligned figures)
            # makes two spans that never appear in the same row: they are one logical column.
            while len(grp) >= 3 and len(spans) > 1:
                used_by_row = [set(span_of(s) for s in l.segs if (s.x1 - s.x0) <= 0.6 * page_w) for l in grp]
                pair = next((k for k in range(len(spans) - 1)
                             if any(k in u for u in used_by_row) and any(k + 1 in u for u in used_by_row)
                             and not any(k in u and k + 1 in u for u in used_by_row)), None)
                if pair is None:
                    break
                spans[pair] = [spans[pair][0], spans[pair + 1][1]]
                del spans[pair + 1]
            for gi, l in enumerate(grp):
                cells, merges, used = {}, [], set()
                for s in l.segs:
                    idx = span_of(s)
                    while idx in used:
                        idx += 1
                    used.add(idx)
                    cells[idx] = (s.text, s.bold)
                    last = max([k for k, sp in enumerate(spans) if sp[0] < s.x1 - tol and sp[1] > s.x0 + tol] or [idx])
                    if last > idx and all(k not in used for k in range(idx + 1, last + 1)):
                        merges.append((idx, last)); used.update(range(idx + 1, last + 1))
                hdr = all(b for _, b in cells.values()) and len(cells) >= 2
                blank = (gi == 0 and prev_bottom is not None and (l.top - prev_bottom) > 0.7 * max(l.size, prev_size)) or \
                        (gi > 0 and (l.top - grp[gi - 1].bottom) > 0.9 * max(l.size, grp[gi - 1].size))
                rows.append({'cells': cells, 'merges': merges, 'kind': 'grid', 'hdr': hdr, 'blank': blank, 'size': l.size})
                prev_bottom, prev_size = l.bottom, l.size

    for it in items:
        if it[0] == 'line':
            pending.append(it[1])
        else:
            flush()
            top, bottom, tbl = it[1], it[2], it[3]
            blank = prev_bottom is not None and (top - prev_bottom) > 0.7 * prev_size
            for ri, r in enumerate(tbl):
                rows.append({'cells': {j: (c, ri == 0) for j, c in enumerate(r) if c != ''}, 'merges': [], 'kind': 'table',
                             'hdr': ri == 0, 'blank': blank and ri == 0, 'size': 10.0})
            prev_bottom, prev_size = bottom, 10.0
    flush()
    return rows

# --------------------------------------------------------------- writing
def _px_write(ws, rows, numbers, start_row=1):
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    thin = Side(style='thin', color='BFC5D2')
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    fill_hdr = PatternFill('solid', fgColor='EDE9FE')
    sizes = [r['size'] for r in rows if r['kind'] != 'table'] or [10.0]
    body = _stats.median(sizes)
    widths, r = {}, start_row
    grid_rows = [x for x in rows if x['kind'] in ('grid', 'table')]
    for row in rows:
        if row['blank']:
            r += 1
        ncell = len(row['cells'])
        for col, (text, bold) in row['cells'].items():
            val, fmt = _px_value(text, numbers)
            c = ws.cell(row=r, column=col + 1, value=val)
            if fmt:
                c.number_format = fmt
            big = row['kind'] == 'text' and row['size'] >= body * 1.3
            if bold or row['hdr'] or big:
                c.font = Font(bold=True, size=14 if big else 11)
            if row['kind'] == 'table' or (row['kind'] == 'grid' and ncell >= 2):
                c.border = border
                c.alignment = Alignment(vertical='top', wrap_text=False)
            if row['hdr'] and row['kind'] in ('table', 'grid'):
                c.fill = fill_hdr
            if row['kind'] != 'text':
                widths[col] = max(widths.get(col, 0), len(str(text)))
        for c1, c2 in row['merges']:
            ws.merge_cells(start_row=r, start_column=c1 + 1, end_row=r, end_column=c2 + 1)
        r += 1
    for col, n in widths.items():
        ws.column_dimensions[get_column_letter(col + 1)].width = max(9, min(55, n * 1.12 + 2))
    if 0 not in widths:
        longest = max([len(str(v[0])) for x in rows for v in x['cells'].values()] or [20])
        ws.column_dimensions['A'].width = max(24, min(100, longest * 1.05 + 2))
    return r

# --------------------------------------------------------------- entry point
def _px_pages_plumber(path, max_pages):
    import pdfplumber
    out = []
    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages[:max_pages]):
            try:
                out.append(_px_page_plumber(page))
            except Exception:
                import traceback; traceback.print_exc()
                out.append((1.0, []))
    return out

def _px_pages_gs(path, timeout):
    import os as _o, tempfile as _t
    tmp = _o.path.join(_t.mkdtemp(), 'x.txt')
    _subprocess.run(['gs', '-sDEVICE=txtwrite', '-dNOPAUSE', '-dBATCH', '-dQUIET', '-dMaxBitmap=500000000',
                     '-sOutputFile=' + tmp, path], check=True, timeout=timeout, capture_output=True)
    with open(tmp, 'r', encoding='utf-8', errors='ignore') as f:
        text = f.read()
    try:
        _o.remove(tmp)
    except Exception:
        pass
    pages = text.split('\f') if '\f' in text else [text]
    return [_px_page_text(p) for p in pages if p.strip()]

def pdf_to_excel_file(input_path, output_path, sheets='page', numbers=True, max_pages=200, timeout=120):
    from openpyxl import Workbook
    pages, engine = None, 'text'
    try:
        pages = _px_pages_plumber(input_path, max_pages)
        engine = 'layout'
    except ImportError:
        pages = None
    except Exception:
        import traceback; traceback.print_exc()
        pages = None
    if pages is None or not any(items for _, items in pages):
        try:
            pages = _px_pages_gs(input_path, timeout)
            engine = 'text'
        except Exception:
            if pages is None:
                raise ValueError('Could not read this PDF. It may be damaged or password protected.')
    pages = [(w, items) for w, items in pages]
    if not any(items for _, items in pages):
        raise ValueError('No text found in this PDF. It looks like a scanned image - text cannot be extracted from scans.')
    tol = 1.5 if engine == 'layout' else 0.0
    wb = Workbook(); wb.remove(wb.active)
    n_tables = 0
    if sheets == 'single' and len(pages) > 1:
        ws = wb.create_sheet('All Pages'); r = 1
        seen_headers = set()
        from openpyxl.styles import Font
        for n, (w, items) in enumerate(pages, start=1):
            if not items:
                continue
            ws.cell(row=r, column=1, value='Page %d' % n).font = Font(bold=True, color='6D28D9')
            rows = _px_layout(items, w, tol)
            n_tables += sum(1 for it in items if it[0] == 'table')
            clean = []
            for row in rows:
                if row['kind'] == 'table' and row['hdr']:
                    sig = tuple(v[0] for _, v in sorted(row['cells'].items()))
                    if sig in seen_headers:
                        continue
                    seen_headers.add(sig)
                clean.append(row)
            r = _px_write(ws, clean, numbers, start_row=r + 1) + 1
    else:
        for n, (w, items) in enumerate(pages, start=1):
            if not items:
                continue
            ws = wb.create_sheet('Page %d' % n)
            n_tables += sum(1 for it in items if it[0] == 'table')
            _px_write(ws, _px_layout(items, w, tol), numbers)
    wb.save(output_path)
    return {'pages': len(pages), 'sheets': len(wb.worksheets), 'engine': engine, 'tables': n_tables}


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
        if not valid:
            return msg, 400
        input_path = os.path.join(temp_dir, 'input.pdf')
        output_path = os.path.join(temp_dir, 'output.xlsx')
        file.save(input_path)
        try:
            info = pdf_to_excel_file(
                input_path, output_path,
                sheets='single' if (request.form.get('sheets', 'page') or 'page').lower() == 'single' else 'page',
                numbers=_flag(request.form.get('numbers'), True),
                timeout=PROCESSING_TIMEOUT,
            )
        except ValueError as e:
            return str(e), 400
        base = re.sub(r'[\\/\*\?\:"<>|]', '_', file.filename.rsplit('.', 1)[0])[:80] or 'converted'
        response = send_file(output_path, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                             as_attachment=True, download_name=f'{base}.xlsx')
        response.headers['X-Pages'] = str(info['pages'])
        response.headers['X-Tables'] = str(info['tables'])
        response.headers['X-Engine'] = info['engine']
        response.headers['Access-Control-Expose-Headers'] = 'X-Pages, X-Tables, X-Engine'
        return response
    except Exception as e:
        import traceback
        traceback.print_exc()
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
        cmd = ['gs', '-sDEVICE=pdfwrite', '-dNOPAUSE', '-dBATCH', '-dQUIET', '-dCompatibilityLevel=1.4', '-dMaxBitmap=500000000', f'-sOutputFile={output_path}'] + pdf_paths
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
        if not valid: 
            return msg, 400
            
        mode = request.form.get('mode', 'custom')
        ranges_input = request.form.get('ranges', '').strip()
        fixed_size = request.form.get('fixed_size', '1')

        input_path = os.path.join(temp_dir, 'input.pdf')
        file.save(input_path)

        from PyPDF2 import PdfReader, PdfWriter
        import io
        import zipfile

        try:
            reader = PdfReader(input_path)
            total_pages = len(reader.pages)
        except Exception as e:
            return 'Error: PDF file is corrupted or password protected.', 400

        if total_pages == 0:
            return 'PDF has no pages', 400

        if mode == 'custom':
            if not ranges_input:
                return 'Please select at least one page.', 400

            pages_to_extract = set()
            parts = ranges_input.split(',')
            for part in parts:
                part = part.strip()
                if '-' in part:
                    try:
                        start, end = map(int, part.split('-'))
                        if start > end: start, end = end, start
                        start = max(1, start)
                        end = min(total_pages, end)
                        for p in range(start, end + 1):
                            pages_to_extract.add(p - 1)
                    except ValueError:
                        continue
                elif part.isdigit():
                    p = int(part)
                    if 1 <= p <= total_pages:
                        pages_to_extract.add(p - 1)

            if not pages_to_extract:
                return 'No valid pages found.', 400

            writer = PdfWriter()
            for p_idx in sorted(pages_to_extract):
                writer.add_page(reader.pages[p_idx])

            output_path = os.path.join(temp_dir, 'extracted.pdf')
            with open(output_path, 'wb') as f:
                writer.write(f)

            return send_file(output_path, mimetype='application/pdf', as_attachment=True, download_name='extracted-pages.pdf')

        elif mode == 'fixed':
            try:
                chunk_size = int(fixed_size)
                if chunk_size < 1: chunk_size = 1
            except:
                chunk_size = 1

            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
                for i in range(0, total_pages, chunk_size):
                    writer = PdfWriter()
                    end = min(i + chunk_size, total_pages)
                    for p_idx in range(i, end):
                        writer.add_page(reader.pages[p_idx])
                    
                    part_filename = f'part_{i//chunk_size + 1:02d}_pages_{i+1}_to_{end}.pdf'
                    part_path = os.path.join(temp_dir, part_filename)
                    with open(part_path, 'wb') as f:
                        writer.write(f)
                    zf.write(part_path, part_filename)

            zip_buffer.seek(0)
            return send_file(zip_buffer, mimetype='application/zip', as_attachment=True, download_name='split_pdfs.zip')
        
        return 'Invalid mode.', 400

    except Exception as e:
        import traceback
        traceback.print_exc()
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
        valid, msg = validate_file(
            file,
            allowed_ext=['.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tiff', '.tif'],
            max_size=15 * 1024 * 1024
        )
        if not valid:
            return msg, 400

        style = (request.form.get('style', 'pencil') or 'pencil').lower()
        valid_styles = ['pencil', 'charcoal', 'ink', 'colored', 'edge', 'crosshatch']
        if style not in valid_styles:
            style = 'pencil'

        try:
            intensity = int(request.form.get('intensity', '50'))
        except:
            intensity = 50
        intensity = max(1, min(100, intensity))

        out_fmt = (request.form.get('format', 'png') or 'png').lower()
        if out_fmt == 'jpeg':
            out_fmt = 'jpg'
        if out_fmt not in ['png', 'jpg', 'webp']:
            out_fmt = 'png'

        input_path = os.path.join(temp_dir, 'input.img')
        file.save(input_path)

        import cv2
        import numpy as np

        try:
            buf = np.fromfile(input_path, dtype=np.uint8)
            img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
        except Exception as e:
            return f'Cannot read image: {e}', 400

        if img is None:
            return 'Invalid or unsupported image file.', 400

        h, w = img.shape[:2]
        if h * w > 25_000_000:
            return 'Image too large (max 25 megapixels).', 400

        MAX_DIM = 1600
        if max(h, w) > MAX_DIM:
            scale = MAX_DIM / max(h, w)
            img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)

        kernel = int(41 - (intensity * 0.36))
        if kernel < 3: kernel = 3
        if kernel % 2 == 0: kernel += 1

        if style == 'pencil':
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            inv = cv2.bitwise_not(gray)
            blur = cv2.GaussianBlur(inv, (kernel, kernel), 0)
            sketch = cv2.divide(gray, cv2.bitwise_not(blur), scale=256.0)
            sketch = cv2.cvtColor(sketch, cv2.COLOR_GRAY2BGR)

        elif style == 'charcoal':
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            inv = cv2.bitwise_not(gray)
            k2 = min(kernel + 12, 61)
            if k2 % 2 == 0: k2 += 1
            blur = cv2.GaussianBlur(inv, (k2, k2), 0)
            sketch = cv2.divide(gray, cv2.bitwise_not(blur), scale=256.0)
            sketch = cv2.convertScaleAbs(sketch, alpha=1.4, beta=-40)
            sketch = cv2.cvtColor(sketch, cv2.COLOR_GRAY2BGR)

        elif style == 'ink':
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            block = 11
            C = max(2, min(15, int(20 - intensity * 0.15)))
            sketch = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, block, C)
            sketch = cv2.cvtColor(sketch, cv2.COLOR_GRAY2BGR)

        elif style == 'colored':
            inv = cv2.bitwise_not(img)
            blur = cv2.GaussianBlur(inv, (kernel, kernel), 0)
            sketch = cv2.divide(img, cv2.bitwise_not(blur), scale=256.0)

        elif style == 'edge':
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            low = max(10, 60 - intensity // 3)
            high = min(250, 120 + intensity)
            edges = cv2.Canny(gray, low, high)
            edges = cv2.dilate(edges, np.ones((2, 2), np.uint8), iterations=1)
            sketch = cv2.bitwise_not(edges)
            sketch = cv2.cvtColor(sketch, cv2.COLOR_GRAY2BGR)

        elif style == 'crosshatch':
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            inv = cv2.bitwise_not(gray)
            k = kernel if kernel >= 5 else 5
            kern_h = cv2.getGaussianKernel(k, 0).T
            kern_h = np.repeat(kern_h, k, axis=0)
            blur_h = cv2.filter2D(inv, -1, kern_h)
            kern_v = cv2.getGaussianKernel(k, 0)
            kern_v = np.repeat(kern_v, k, axis=1)
            blur_v = cv2.filter2D(inv, -1, kern_v)
            s1 = cv2.divide(gray, cv2.bitwise_not(blur_h), scale=256.0)
            s2 = cv2.divide(gray, cv2.bitwise_not(blur_v), scale=256.0)
            sketch = cv2.min(s1, s2)
            sketch = cv2.convertScaleAbs(sketch, alpha=1.15, beta=-15)
            sketch = cv2.cvtColor(sketch, cv2.COLOR_GRAY2BGR)

        else:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            inv = cv2.bitwise_not(gray)
            blur = cv2.GaussianBlur(inv, (kernel, kernel), 0)
            sketch = cv2.divide(gray, cv2.bitwise_not(blur), scale=256.0)
            sketch = cv2.cvtColor(sketch, cv2.COLOR_GRAY2BGR)

        if style not in ['edge', 'ink']:
            sketch = cv2.convertScaleAbs(sketch, alpha=1.08, beta=-4)
            gaussian = cv2.GaussianBlur(sketch, (0, 0), 1.4)
            sketch = cv2.addWeighted(sketch, 1.3, gaussian, -0.3, 0)

        ext_map = {'png': '.png', 'jpg': '.jpg', 'webp': '.webp'}
        mime_map = {'png': 'image/png', 'jpg': 'image/jpeg', 'webp': 'image/webp'}
        ext = ext_map[out_fmt]
        mime = mime_map[out_fmt]
        output_path = os.path.join(temp_dir, f'sketch{ext}')

        if out_fmt == 'jpg':
            cv2.imwrite(output_path, sketch, [cv2.IMWRITE_JPEG_QUALITY, 92])
        elif out_fmt == 'webp':
            cv2.imwrite(output_path, sketch, [cv2.IMWRITE_WEBP_QUALITY, 90])
        else:
            cv2.imwrite(output_path, sketch)

        if not os.path.exists(output_path):
            return 'Sketch creation failed', 500

        response = send_file(
            output_path,
            mimetype=mime,
            as_attachment=True,
            download_name=f'sketch-{style}{ext}'
        )
        response.headers['X-Sketch-Style'] = style
        response.headers['X-Sketch-Intensity'] = str(intensity)
        response.headers['X-Sketch-Format'] = out_fmt
        response.headers['Access-Control-Expose-Headers'] = 'X-Sketch-Style, X-Sketch-Intensity, X-Sketch-Format'
        return response
    except Exception as e:
        import traceback
        traceback.print_exc()
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

# ========== 21. IMAGE TO WORD ==========
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

# ========== 22. IMAGE TO EXCEL ==========
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


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)