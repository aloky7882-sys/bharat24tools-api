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

# ==================== CONFIGURATION ====================
MAX_FILE_SIZE = 20 * 1024 * 1024
MAX_FILES_COUNT = 20
PROCESSING_TIMEOUT = 300
CLEANUP_DELAY = 30

processing_lock = threading.Lock()

# ==================== AUTO CLEANUP WORKER ====================
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


# ==================== HOME PAGE ====================
HTML = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Bharat24Tools API v8.6</title>
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
        <h1>⚡ Bharat24Tools API v8.6</h1>
        <p class="status-badge">Server is running ✅ — 24 Tools Active</p>

        <div class="section-title">📄 PDF Tools (13)</div>
        <div class="endpoint"><code>POST /compress</code><span class="desc">Compress PDF</span></div>
        <div class="endpoint"><code>POST /pdf-to-jpg</code><span class="desc">PDF to Images</span></div>
        <div class="endpoint"><code>POST /jpg-to-pdf</code><span class="desc">Images to PDF ✅ FIXED</span></div>
        <div class="endpoint"><code>POST /pdf-to-word</code><span class="desc">PDF to Word</span></div>
        <div class="endpoint"><code>POST /word-to-pdf</code><span class="desc">Word to PDF</span></div>
        <div class="endpoint"><code>POST /excel-to-pdf</code><span class="desc">Excel to PDF ✅ 15MB + Robust</span></div>
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
        <div class="endpoint"><code>POST /avif-to-jpg</code><span class="desc">AVIF to JPG</span></div>
        <div class="endpoint"><code>POST /image-to-sketch</code><span class="desc">Image to Sketch</span></div>
        <div class="endpoint"><code>POST /gif-maker</code><span class="desc">GIF Maker</span></div>
        <div class="endpoint"><code>POST /image-to-word</code><span class="desc">Image to Word ✅ NEW</span></div>
        <div class="endpoint"><code>POST /image-to-excel</code><span class="desc">Image to Excel ✅ NEW</span></div>
        <div class="endpoint"><code>POST /pdf-watermark</code><span class="desc">PDF Watermark</span></div>
        <div class="endpoint"><code>POST /pdf-page-delete</code><span class="desc">PDF Page Delete</span></div>

        <p class="footer">Version 8.6 — 24 Tools Active | Image to Word + Image to Excel Added</p>
    </div>
</body>
</html>
'''


# ==================== HELPERS ====================
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


# ==================== ROUTES ====================
@app.route('/')
def index():
    return render_template_string(HTML)


@app.route('/health')
def health():
    return {
        'status': 'ok',
        'service': 'bharat24tools-api',
        'version': '8.6',
        'tools': 24,
        'ghostscript': True,
        'auto_cleanup': True,
        'excel_to_pdf': 'robust-15mb',
        'image_to_word': 'advanced',
        'image_to_excel': 'advanced',
        'background_remover': 'client-side'
    }


# ========== 1. COMPRESS PDF ==========
@app.route('/compress', methods=['POST'])
def compress():
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
        output_path = os.path.join(temp_dir, 'output.pdf')
        file.save(input_path)
        input_size = os.path.getsize(input_path)
        subprocess.run([
            'gs', '-sDEVICE=pdfwrite', '-dCompatibilityLevel=1.4',
            '-dPDFSETTINGS=/screen', '-dNOPAUSE', '-dQUIET', '-dBATCH',
            '-dDetectDuplicateImages=true', '-dCompressFonts=true',
            '-dSubsetFonts=true', '-dDownsampleColorImages=true',
            '-dColorImageResolution=72', '-dDownsampleGrayImages=true',
            '-dGrayImageResolution=72', '-dDownsampleMonoImages=true',
            '-dMonoImageResolution=72',
            f'-sOutputFile={output_path}', input_path
        ], check=True, timeout=PROCESSING_TIMEOUT, capture_output=True)
        output_size = os.path.getsize(output_path)
        saved = ((input_size - output_size) / input_size * 100)
        print(f'✅ Compress: {input_size/1024/1024:.2f}MB → {output_size/1024/1024:.2f}MB ({saved:.1f}%)', flush=True)
        return send_file(output_path, mimetype='application/pdf', as_attachment=True, download_name='compressed.pdf')
    except subprocess.TimeoutExpired:
        return 'Timeout: File too complex', 500
    except Exception as e:
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
        subprocess.run([
            'gs', '-dNOPAUSE', '-dBATCH', '-dQUIET',
            '-sDEVICE=jpeg', '-r150', '-dJPEGQ=90',
            f'-sOutputFile={output_pattern}', input_path
        ], check=True, timeout=PROCESSING_TIMEOUT, capture_output=True)
        jpg_files = sorted([f for f in os.listdir(temp_dir) if f.startswith('page-') and f.endswith('.jpg')])
        if not jpg_files:
            return 'No pages converted', 500
        print(f'✅ PDF to JPG: {len(jpg_files)} pages', flush=True)
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
        images[0].save(
            output_path,
            'PDF',
            save_all=True,
            append_images=images[1:],
            resolution=100.0
        )

        if not os.path.exists(output_path):
            return 'PDF creation failed', 500

        print(f'✅ JPG to PDF: {len(images)} images → {os.path.getsize(output_path)} bytes', flush=True)
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
        subprocess.run([
            'gs', '-sDEVICE=txtwrite', '-dNOPAUSE', '-dBATCH', '-dQUIET',
            f'-sOutputFile={txt_path}', input_path
        ], check=True, timeout=PROCESSING_TIMEOUT, capture_output=True)
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
        print(f'✅ PDF to Word: {os.path.getsize(output_path)} bytes', flush=True)
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
        print(f'✅ Word to PDF: {os.path.getsize(output_path)} bytes', flush=True)
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
        from reportlab.platypus import (
            SimpleDocTemplate, Table, TableStyle, Paragraph,
            Spacer, PageBreak
        )
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
        from datetime import datetime

        def clean_cell(value):
            if value is None:
                return ''
            try:
                s = str(value)
                if s.lower() == 'nan' or s.lower() == 'none':
                    return ''
                return s.strip()
            except:
                return ''

        def detect_column_type(values):
            non_empty = [v for v in values if v and str(v).strip()]
            if not non_empty:
                return 'text'
            num_count = 0
            for v in non_empty:
                clean = str(v).replace(',', '').replace('₹', '').replace('$', '').replace('%', '').strip()
                try:
                    float(clean)
                    num_count += 1
                except:
                    pass
            if num_count / len(non_empty) > 0.7:
                if any('₹' in str(v) or '$' in str(v) for v in non_empty):
                    return 'currency'
                if any('%' in str(v) for v in non_empty):
                    return 'percent'
                return 'number'
            date_pattern = re.compile(r'\d{1,4}[-/\.]\d{1,2}[-/\.]\d{1,4}')
            date_count = sum(1 for v in non_empty if date_pattern.search(str(v)))
            if date_count / len(non_empty) > 0.6:
                return 'date'
            return 'text'

        def calculate_column_widths(table_data, max_cols=15):
            if not table_data:
                return []
            widths = []
            for col_idx in range(min(len(table_data[0]), max_cols)):
                max_len = 0
                for row in table_data[:100]:
                    if col_idx < len(row):
                        cell_len = len(str(row[col_idx]) if row[col_idx] else '')
                        max_len = max(max_len, cell_len)
                if max_len <= 5:
                    w = 20 * mm
                elif max_len <= 10:
                    w = 28 * mm
                elif max_len <= 20:
                    w = 38 * mm
                elif max_len <= 35:
                    w = 50 * mm
                else:
                    w = 65 * mm
                widths.append(w)
            return widths

        def smart_truncate(text, max_len=50):
            text = str(text) if text is not None else ''
            if len(text) > max_len:
                return text[:max_len - 3] + '...'
            return text

        def escape_xml(text):
            return (str(text)
                    .replace('&', '&amp;')
                    .replace('<', '&lt;')
                    .replace('>', '&gt;'))

        wb = None
        load_success = False

        try:
            wb = load_workbook(input_path, data_only=True, read_only=True)
            load_success = True
            print('✅ Loaded read_only=True', flush=True)
        except Exception as e1:
            print(f'⚠️ read_only failed: {e1}', flush=True)

        if not load_success:
            try:
                wb = load_workbook(input_path, data_only=True, read_only=False)
                load_success = True
                print('✅ Loaded normal mode', flush=True)
            except Exception as e2:
                print(f'⚠️ normal failed: {e2}', flush=True)

        if not load_success:
            try:
                wb = load_workbook(input_path, data_only=True, read_only=True,
                                   keep_vba=False, keep_links=False)
                load_success = True
                print('✅ Loaded keep_links=False', flush=True)
            except Exception as e3:
                print(f'❌ All modes failed: {e3}', flush=True)

        if not load_success or wb is None:
            return 'Cannot read this Excel file. Please open it in Excel/LibreOffice and save as new .xlsx file.', 400

        pdf = SimpleDocTemplate(
            output_path,
            pagesize=landscape(A4),
            leftMargin=10*mm,
            rightMargin=10*mm,
            topMargin=25*mm,
            bottomMargin=18*mm,
            title='Excel to PDF - Bharat24Tools',
            author='Bharat24Tools'
        )

        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            'BrandTitle', parent=styles['Heading1'],
            fontSize=18, textColor=colors.HexColor('#a855f7'),
            alignment=TA_LEFT, spaceAfter=4, fontName='Helvetica-Bold'
        )
        subtitle_style = ParagraphStyle(
            'BrandSubtitle', parent=styles['Normal'],
            fontSize=9, textColor=colors.HexColor('#666666'),
            alignment=TA_LEFT, spaceAfter=12, fontName='Helvetica-Oblique'
        )
        sheet_style = ParagraphStyle(
            'SheetTitle', parent=styles['Heading2'],
            fontSize=13, textColor=colors.HexColor('#533483'),
            spaceBefore=8, spaceAfter=8, fontName='Helvetica-Bold'
        )

        story = []
        story.append(Paragraph('⚡ Bharat24Tools', title_style))
        story.append(Paragraph(
            f'Excel to PDF &nbsp;•&nbsp; File: {escape_xml(file.filename)} &nbsp;•&nbsp; '
            f'{datetime.now().strftime("%d %b %Y, %I:%M %p")}',
            subtitle_style
        ))
        story.append(Spacer(1, 6))

        total_rows_converted = 0
        MAX_ROWS_PER_SHEET = 5000
        MAX_COLS = 15
        total_sheets = len(wb.sheetnames)

        for sheet_idx, sheet_name in enumerate(wb.sheetnames):
            try:
                sheet = wb[sheet_name]
            except Exception as e:
                print(f'⚠️ Cannot access {sheet_name}: {e}', flush=True)
                continue

            raw_data = []
            try:
                for row in sheet.iter_rows(values_only=True):
                    if row is None:
                        continue
                    try:
                        cleaned = [clean_cell(c) for c in row[:MAX_COLS]]
                        if any(c for c in cleaned):
                            raw_data.append(cleaned)
                            if len(raw_data) >= MAX_ROWS_PER_SHEET:
                                break
                    except Exception as cell_err:
                        print(f'⚠️ Row error: {cell_err}', flush=True)
                        continue
            except Exception as e:
                print(f'⚠️ Error reading sheet {sheet_name}: {e}', flush=True)
                continue

            if not raw_data or len(raw_data) < 1:
                continue

            header = raw_data[0]
            while len(header) < MAX_COLS:
                header.append('')

            col_types = []
            for col_idx in range(len(header)):
                col_values = [row[col_idx] for row in raw_data[1:51] if col_idx < len(row)]
                col_types.append(detect_column_type(col_values))

            if total_sheets > 1:
                story.append(Paragraph(
                    f'📄 Sheet {sheet_idx + 1}: {escape_xml(sheet_name)}',
                    sheet_style
                ))
            else:
                story.append(Paragraph(
                    f'📄 Sheet: {escape_xml(sheet_name)}',
                    sheet_style
                ))

            display_data = []
            for row in raw_data:
                display_row = [smart_truncate(c, 50) for c in row]
                while len(display_row) < len(header):
                    display_row.append('')
                display_data.append(display_row)

            col_widths = calculate_column_widths(display_data)

            pdf_table = Table(display_data, colWidths=col_widths, repeatRows=1)

            table_styles = [
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#a855f7')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('TOPPADDING', (0, 0), (-1, 0), 7),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 7),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('TOPPADDING', (0, 1), (-1, -1), 5),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 5),
                ('LEFTPADDING', (0, 0), (-1, -1), 5),
                ('RIGHTPADDING', (0, 0), (-1, -1), 5),
                ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#d1d5db')),
                ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#a855f7')),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [
                    colors.white,
                    colors.HexColor('#f8f5ff')
                ]),
            ]

            for col_idx, ctype in enumerate(col_types):
                if ctype in ('number', 'currency', 'percent'):
                    table_styles.append(('ALIGN', (col_idx, 1), (col_idx, -1), 'RIGHT'))
                elif ctype == 'date':
                    table_styles.append(('ALIGN', (col_idx, 1), (col_idx, -1), 'CENTER'))
                else:
                    table_styles.append(('ALIGN', (col_idx, 1), (col_idx, -1), 'LEFT'))

            pdf_table.setStyle(TableStyle(table_styles))
            story.append(pdf_table)
            story.append(Spacer(1, 8))

            data_rows = len(display_data) - 1
            story.append(Paragraph(
                f'<font size="8" color="#666666">'
                f'✓ {data_rows} rows • {len(header)} columns'
                f'</font>',
                styles['Normal']
            ))

            total_rows_converted += data_rows

            if sheet_idx < total_sheets - 1:
                story.append(PageBreak())

        try:
            wb.close()
        except:
            pass

        if total_rows_converted == 0:
            return 'Excel file is empty (no data found)', 400

        story.append(Spacer(1, 12))
        story.append(Paragraph(
            f'<font size="8" color="#a855f7"><b>📊 Summary:</b> '
            f'{total_sheets} sheet(s) • {total_rows_converted} rows converted</font>',
            styles['Normal']
        ))

        def add_page_decorations(canvas, doc):
            canvas.saveState()
            page_num = canvas.getPageNumber()

            canvas.setStrokeColor(colors.HexColor('#a855f7'))
            canvas.setLineWidth(0.5)
            canvas.line(10*mm, 14*mm, doc.pagesize[0] - 10*mm, 14*mm)

            canvas.setFont('Helvetica', 7)
            canvas.setFillColor(colors.HexColor('#999999'))
            canvas.drawString(10*mm, 9*mm, '⚡ Generated by Bharat24Tools — Free Online Tools')
            canvas.drawRightString(doc.pagesize[0] - 10*mm, 9*mm, f'Page {page_num}')

            canvas.setFont('Helvetica-Oblique', 7)
            canvas.setFillColor(colors.HexColor('#a855f7'))
            canvas.drawCentredString(doc.pagesize[0] / 2, 9*mm, 'bharat24tools.in')

            canvas.setFont('Helvetica-Bold', 55)
            canvas.setFillColor(colors.HexColor('#a855f7'), alpha=0.04)
            canvas.translate(doc.pagesize[0] / 2, doc.pagesize[1] / 2)
            canvas.rotate(45)
            canvas.drawCentredString(0, 0, 'BHARAT24TOOLS')
            canvas.restoreState()

        pdf.build(story, onFirstPage=add_page_decorations, onLaterPages=add_page_decorations)

        output_size = os.path.getsize(output_path)
        print(f'✅ Excel to PDF: {total_sheets} sheets, {total_rows_converted} rows, {output_size} bytes', flush=True)

        return send_file(
            output_path,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f'Bharat24Tools_{file.filename.rsplit(".", 1)[0]}.pdf'
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f'❌ Excel to PDF error: {e}', flush=True)
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
        if not valid:
            return msg, 400
        input_path = os.path.join(temp_dir, 'input.pdf')
        txt_path = os.path.join(temp_dir, 'extracted.txt')
        output_path = os.path.join(temp_dir, 'output.xlsx')
        file.save(input_path)
        subprocess.run([
            'gs', '-sDEVICE=txtwrite', '-dNOPAUSE', '-dBATCH', '-dQUIET',
            f'-sOutputFile={txt_path}', input_path
        ], check=True, timeout=PROCESSING_TIMEOUT, capture_output=True)
        if not os.path.exists(txt_path):
            return 'Text extraction failed', 500
        with open(txt_path, 'r', encoding='utf-8', errors='ignore') as f:
            text = f.read()
        if not text.strip():
            return 'No text found in PDF', 400
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment
        wb = Workbook()
        ws = wb.active
        ws.title = 'PDF Content'
        ws['A1'] = 'Extracted from PDF'
        ws['A1'].font = Font(bold=True, size=14, color='FFFFFF')
        ws['A1'].fill = PatternFill('solid', fgColor='A855F7')
        ws['A1'].alignment = Alignment(horizontal='center')
        ws.merge_cells('A1:C1')
        row = 3
        for line in text.split('\n'):
            if line.strip():
                ws.cell(row=row, column=1, value=line.strip())
                ws.cell(row=row, column=1).alignment = Alignment(wrap_text=True, vertical='top')
                row += 1
        ws.column_dimensions['A'].width = 100
        wb.save(output_path)
        print(f'✅ PDF to Excel: {os.path.getsize(output_path)} bytes', flush=True)
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
        if not valid:
            return msg, 400
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
            row_data = [str(c) if c is not None else '' for c in row]
            if any(row_data):
                data.append(row_data)
        if not data:
            return 'Excel file is empty', 400
        data = data[:30]
        cols = len(data[0]) if data else 0
        fig, ax = plt.subplots(figsize=(max(8, cols * 2), max(4, len(data) * 0.5)))
        ax.axis('tight')
        ax.axis('off')
        table = ax.table(cellText=data, loc='center', cellLoc='left')
        table.auto_set_font_size(False)
        table.set_fontsize(9)
        table.scale(1, 1.5)
        for i in range(cols):
            cell = table[(0, i)]
            cell.set_facecolor('#a855f7')
            cell.set_text_props(color='white', weight='bold')
        plt.title('Excel Content — Bharat24Tools', fontsize=14, fontweight='bold', pad=20)
        plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
        plt.close()
        print(f'✅ Excel to Image: {os.path.getsize(output_path)} bytes', flush=True)
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
        if len(files) < 2:
            return 'At least 2 PDFs required', 400
        if len(files) > MAX_FILES_COUNT:
            return f'Max {MAX_FILES_COUNT} files allowed', 400
        pdf_paths = []
        for i, file in enumerate(files):
            valid, msg = validate_file(file, allowed_ext=['.pdf'])
            if not valid:
                return f'File {i+1}: {msg}', 400
            path = os.path.join(temp_dir, f'input-{i:03d}.pdf')
            file.save(path)
            pdf_paths.append(path)
        output_path = os.path.join(temp_dir, 'merged.pdf')
        cmd = ['gs', '-sDEVICE=pdfwrite', '-dNOPAUSE', '-dBATCH', '-dQUIET',
               '-dCompatibilityLevel=1.4',
               f'-sOutputFile={output_path}'] + pdf_paths
        subprocess.run(cmd, check=True, timeout=PROCESSING_TIMEOUT, capture_output=True)
        if not os.path.exists(output_path):
            return 'Merge failed', 500
        print(f'✅ Merged {len(pdf_paths)} PDFs', flush=True)
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
        pages = request.form.get('pages', '').strip()
        input_path = os.path.join(temp_dir, 'input.pdf')
        file.save(input_path)
        try:
            result = subprocess.run(['qpdf', '--show-npages', input_path],
                                    capture_output=True, text=True, timeout=30)
            total_pages = int(result.stdout.strip())
        except:
            total_pages = 0
        if total_pages == 0:
            return 'Cannot read PDF page count', 400
        output_pattern = os.path.join(temp_dir, 'page-%03d.pdf')
        cmd = ['qpdf', '--split-pages', '1', input_path, output_pattern]
        subprocess.run(cmd, check=True, timeout=PROCESSING_TIMEOUT, capture_output=True)
        pdf_files = sorted([f for f in os.listdir(temp_dir) if f.startswith('page-') and f.endswith('.pdf')])
        if not pdf_files:
            return 'Split failed', 500
        print(f'✅ Split: {len(pdf_files)} pages', flush=True)
        if len(pdf_files) == 1:
            return send_file(os.path.join(temp_dir, pdf_files[0]), mimetype='application/pdf', as_attachment=True, download_name='page-1.pdf')
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for pdf in pdf_files:
                zf.write(os.path.join(temp_dir, pdf), pdf)
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
        if not valid:
            return msg, 400
        angle = request.form.get('angle', '90')
        try:
            angle = int(angle)
            if angle not in [90, 180, 270]:
                angle = 90
        except:
            angle = 90
        input_path = os.path.join(temp_dir, 'input.pdf')
        output_path = os.path.join(temp_dir, 'rotated.pdf')
        file.save(input_path)
        try:
            result = subprocess.run(['qpdf', '--show-npages', input_path],
                                    capture_output=True, text=True, timeout=30)
            total_pages = int(result.stdout.strip())
        except:
            total_pages = 0
        if total_pages == 0:
            return 'Cannot read PDF page count', 400
        rotate_spec = f'+{angle}:1-{total_pages}'
        print(f'🔄 Rotating {total_pages} pages by {angle}°', flush=True)
        subprocess.run([
            'qpdf', f'--rotate={rotate_spec}', input_path, output_path
        ], check=True, timeout=PROCESSING_TIMEOUT, capture_output=True)
        if not os.path.exists(output_path):
            return 'Rotation failed', 500
        print(f'✅ Rotated {angle}°', flush=True)
        return send_file(output_path, mimetype='application/pdf', as_attachment=True, download_name='rotated.pdf')
    except subprocess.CalledProcessError as e:
        err_msg = e.stderr.decode()[:300] if e.stderr else 'Unknown qpdf error'
        print(f'❌ Rotate error: {err_msg}', flush=True)
        return f'Rotation failed: {err_msg}', 500
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
        if not valid:
            return msg, 400
        password = request.form.get('password', '').strip()
        if not password or len(password) < 4:
            return 'Password must be at least 4 characters', 400
        input_path = os.path.join(temp_dir, 'input.pdf')
        output_path = os.path.join(temp_dir, 'protected.pdf')
        file.save(input_path)
        subprocess.run([
            'qpdf', '--encrypt', password, password, '256', '--',
            input_path, output_path
        ], check=True, timeout=PROCESSING_TIMEOUT, capture_output=True)
        if not os.path.exists(output_path):
            return 'Encryption failed', 500
        print(f'✅ Protected with password', flush=True)
        return send_file(output_path, mimetype='application/pdf', as_attachment=True, download_name='protected.pdf')
    except subprocess.CalledProcessError as e:
        print(f'❌ Protect error: {e}', flush=True)
        return f'Encryption failed: {e.stderr.decode()[:200] if e.stderr else "Unknown error"}', 500
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
        if not valid:
            return msg, 400
        password = request.form.get('password', '').strip()
        if not password:
            return 'Password required to unlock', 400
        input_path = os.path.join(temp_dir, 'input.pdf')
        output_path = os.path.join(temp_dir, 'unlocked.pdf')
        file.save(input_path)
        subprocess.run([
            'qpdf', f'--password={password}', '--decrypt',
            input_path, output_path
        ], check=True, timeout=PROCESSING_TIMEOUT, capture_output=True)
        if not os.path.exists(output_path):
            return 'Unlock failed - wrong password?', 500
        print(f'✅ Unlocked PDF', flush=True)
        return send_file(output_path, mimetype='application/pdf', as_attachment=True, download_name='unlocked.pdf')
    except subprocess.CalledProcessError as e:
        err_msg = e.stderr.decode()[:200] if e.stderr else "Wrong password?"
        print(f'❌ Unlock error: {err_msg}', flush=True)
        return f'Unlock failed: {err_msg}', 500
    except Exception as e:
        print(f'❌ Unlock error: {e}', flush=True)
        return f'Error: {str(e)}', 500
    finally:
        processing_lock.release()
        cleanup_dir(temp_dir)


# =====================================================================
# ==================== 11 GLOBAL TOOLS ================================
# =====================================================================


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
        if not valid:
            return msg, 400
        input_path = os.path.join(temp_dir, 'input.heic')
        output_path = os.path.join(temp_dir, 'output.jpg')
        file.save(input_path)

        from pillow_heif import register_heif_opener
        from PIL import Image
        register_heif_opener()

        img = Image.open(input_path)
        if img.mode != 'RGB':
            img = img.convert('RGB')
        img.save(output_path, 'JPEG', quality=90)

        print(f'✅ HEIC to JPG: {os.path.getsize(output_path)} bytes', flush=True)
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
        if not valid:
            return msg, 400
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

        print(f'✅ WebP to JPG: {os.path.getsize(output_path)} bytes', flush=True)
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
        if not valid:
            return msg, 400

        scale = int(request.form.get('scale', '2'))
        if scale not in [2, 3, 4]:
            scale = 2

        input_path = os.path.join(temp_dir, 'input.png')
        output_path = os.path.join(temp_dir, 'output.png')
        file.save(input_path)

        from PIL import Image
        img = Image.open(input_path)
        new_size = (img.width * scale, img.height * scale)
        upscaled = img.resize(new_size, Image.LANCZOS)
        upscaled.save(output_path, 'PNG')

        print(f'✅ Upscaled {scale}x: {new_size}', flush=True)
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
        if not valid:
            return msg, 400

        lang = request.form.get('lang', 'eng')
        input_path = os.path.join(temp_dir, 'input.png')
        file.save(input_path)

        import pytesseract
        from PIL import Image

        pytesseract.pytesseract.tesseract_cmd = r'/usr/bin/tesseract'

        img = Image.open(input_path)
        text = pytesseract.image_to_string(img, lang=lang)

        output_path = os.path.join(temp_dir, 'output.txt')
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(text)

        print(f'✅ OCR: {len(text)} chars', flush=True)
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
    return 'Please use client-side version at /avif-to-jpg.html', 400


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
        if not valid:
            return msg, 400
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

        print(f'✅ Sketch created', flush=True)
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
        if len(files) < 2:
            return 'At least 2 images required', 400
        if len(files) > 20:
            return 'Max 20 images', 400

        from PIL import Image
        images = []
        for i, file in enumerate(files):
            valid, msg = validate_file(file, allowed_ext=['.jpg', '.jpeg', '.png', '.webp'])
            if not valid:
                return f'File {i+1}: {msg}', 400
            path = os.path.join(temp_dir, f'img-{i:03d}.png')
            file.save(path)
            img = Image.open(path)
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            img = img.resize((500, 500), Image.LANCZOS)
            images.append(img)

        output_path = os.path.join(temp_dir, 'animation.gif')
        duration = int(request.form.get('duration', '200'))
        images[0].save(
            output_path,
            'GIF',
            save_all=True,
            append_images=images[1:],
            duration=duration,
            loop=0,
            optimize=True
        )

        print(f'✅ GIF created: {len(images)} frames', flush=True)
        return send_file(output_path, mimetype='image/gif', as_attachment=True, download_name='animation.gif')
    except Exception as e:
        print(f'❌ GIF error: {e}', flush=True)
        return f'Error: {str(e)}', 500
    finally:
        processing_lock.release()
        cleanup_dir(temp_dir)


# ========== 21. IMAGE TO WORD (Advanced Server-Based) ==========
@app.route('/image-to-word', methods=['POST'])
def image_to_word():
    if not processing_lock.acquire(timeout=300):
        return 'Server busy. Try again.', 503
    temp_dir = tempfile.mkdtemp()
    try:
        if 'files' not in request.files:
            return 'No files uploaded', 400
        files = request.files.getlist('files')
        if len(files) < 1:
            return 'At least 1 image required', 400
        if len(files) > 30:
            return 'Max 30 images allowed', 400

        output_path = os.path.join(temp_dir, 'output.docx')

        from docx import Document
        from docx.shared import Pt, RGBColor, Cm
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from PIL import Image
        from datetime import datetime

        layout = request.form.get('layout', 'one-per-page')
        add_captions = request.form.get('captions', 'yes') == 'yes'
        auto_resize = request.form.get('resize', 'yes') == 'yes'
        custom_title = request.form.get('title', 'Images — Bharat24Tools')

        doc = Document()
        for section in doc.sections:
            section.top_margin = Cm(1.5)
            section.bottom_margin = Cm(1.5)
            section.left_margin = Cm(1.5)
            section.right_margin = Cm(1.5)

        title = doc.add_heading(custom_title, 0)
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        if title.runs:
            title.runs[0].font.color.rgb = RGBColor(0xa8, 0x55, 0xf7)
            title.runs[0].font.size = Pt(22)

        sub = doc.add_paragraph()
        sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = sub.add_run(f'{len(files)} image(s) • Created with Bharat24Tools • {datetime.now().strftime("%d %b %Y")}')
        run.font.size = Pt(9)
        run.font.color.rgb = RGBColor(0x66, 0x66, 0x66)
        run.italic = True
        doc.add_paragraph()

        page_width_cm = 18

        if layout == 'one-per-page':
            for i, file in enumerate(files):
                valid, msg = validate_file(file, allowed_ext=['.jpg', '.jpeg', '.png', '.webp', '.gif'])
                if not valid:
                    continue
                input_path = os.path.join(temp_dir, f'img-{i:03d}.png')
                file.save(input_path)
                img = Image.open(input_path)
                if img.mode in ('RGBA', 'LA', 'P'):
                    bg = Image.new('RGB', img.size, (255, 255, 255))
                    bg.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                    img = bg
                elif img.mode != 'RGB':
                    img = img.convert('RGB')
                png_path = os.path.join(temp_dir, f'converted-{i:03d}.png')
                img.save(png_path, 'PNG')
                w_cm, h_cm = img.size
                max_w_cm, max_h_cm = page_width_cm, 22
                if auto_resize:
                    ratio = min(max_w_cm / w_cm, max_h_cm / h_cm, 1)
                    final_w, final_h = w_cm * ratio, h_cm * ratio
                else:
                    final_w = min(w_cm, max_w_cm)
                    final_h = h_cm * (final_w / w_cm)
                doc.add_picture(png_path, width=Cm(final_w), height=Cm(final_h))
                doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
                if add_captions:
                    cap = doc.add_paragraph()
                    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    cap_run = cap.add_run(f'Figure {i+1}: {file.filename}')
                    cap_run.font.size = Pt(9)
                    cap_run.italic = True
                    cap_run.font.color.rgb = RGBColor(0x66, 0x66, 0x66)
                if i < len(files) - 1:
                    doc.add_page_break()

        elif layout in ('grid-2', 'grid-3'):
            cols = 2 if layout == 'grid-2' else 3
            cell_width_cm = (page_width_cm - (cols - 1) * 0.5) / cols
            table = doc.add_table(rows=0, cols=cols)
            table.autofit = False
            row_cells = None
            for i, file in enumerate(files):
                valid, msg = validate_file(file, allowed_ext=['.jpg', '.jpeg', '.png', '.webp', '.gif'])
                if not valid:
                    continue
                if i % cols == 0:
                    row_cells = table.add_row().cells
                cell = row_cells[i % cols]
                input_path = os.path.join(temp_dir, f'img-{i:03d}.png')
                file.save(input_path)
                img = Image.open(input_path)
                if img.mode in ('RGBA', 'LA', 'P'):
                    bg = Image.new('RGB', img.size, (255, 255, 255))
                    bg.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                    img = bg
                elif img.mode != 'RGB':
                    img = img.convert('RGB')
                png_path = os.path.join(temp_dir, f'converted-{i:03d}.png')
                img.save(png_path, 'PNG')
                w_cm, h_cm = img.size
                ratio = min(cell_width_cm / w_cm, 1)
                final_w = w_cm * ratio
                p = cell.paragraphs[0]
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p.add_run().add_picture(png_path, width=Cm(final_w))
                if add_captions:
                    cap = cell.add_paragraph()
                    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    cap_run = cap.add_run(file.filename[:30])
                    cap_run.font.size = Pt(8)
                    cap_run.italic = True

        else:
            for i, file in enumerate(files):
                valid, msg = validate_file(file, allowed_ext=['.jpg', '.jpeg', '.png', '.webp', '.gif'])
                if not valid:
                    continue
                input_path = os.path.join(temp_dir, f'img-{i:03d}.png')
                file.save(input_path)
                img = Image.open(input_path)
                if img.mode in ('RGBA', 'LA', 'P'):
                    bg = Image.new('RGB', img.size, (255, 255, 255))
                    bg.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                    img = bg
                elif img.mode != 'RGB':
                    img = img.convert('RGB')
                png_path = os.path.join(temp_dir, f'converted-{i:03d}.png')
                img.save(png_path, 'PNG')
                w_cm, h_cm = img.size
                ratio = min(page_width_cm / w_cm, 1)
                doc.add_picture(png_path, width=Cm(w_cm * ratio), height=Cm(h_cm * ratio))

        doc.save(output_path)
        print(f'✅ Image to Word: {len(files)} images, layout={layout}', flush=True)
        return send_file(
            output_path,
            mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            as_attachment=True,
            download_name='Bharat24Tools_images.docx'
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f'❌ Image to Word error: {e}', flush=True)
        return f'Error: {str(e)}', 500
    finally:
        processing_lock.release()
        cleanup_dir(temp_dir)


# ========== 22. IMAGE TO EXCEL (Advanced Server-Based) ==========
@app.route('/image-to-excel', methods=['POST'])
def image_to_excel():
    if not processing_lock.acquire(timeout=300):
        return 'Server busy. Try again.', 503
    temp_dir = tempfile.mkdtemp()
    try:
        if 'files' not in request.files:
            return 'No files uploaded', 400
        files = request.files.getlist('files')
        if len(files) < 1:
            return 'At least 1 image required', 400
        if len(files) > 50:
            return 'Max 50 images allowed', 400

        output_path = os.path.join(temp_dir, 'output.xlsx')

        from openpyxl import Workbook
        from openpyxl.drawing.image import Image as XLImage
        from openpyxl.styles import Font, PatternFill, Alignment
        from openpyxl.utils import get_column_letter
        from PIL import Image
        from datetime import datetime

        layout = request.form.get('layout', 'one-per-row')
        add_filename = request.form.get('filenames', 'yes') == 'yes'
        cell_size = request.form.get('size', 'medium')
        custom_title = request.form.get('title', 'Images — Bharat24Tools')

        wb = Workbook()
        ws = wb.active
        ws.title = 'Images'

        size_map = {'small': (80, 80, 60), 'medium': (140, 140, 105), 'large': (220, 220, 165)}
        img_px, row_h, col_w = size_map.get(cell_size, size_map['medium'])

        ws['A1'] = custom_title
        ws['A1'].font = Font(bold=True, size=16, color='FFFFFF')
        ws['A1'].fill = PatternFill('solid', fgColor='A855F7')
        ws['A1'].alignment = Alignment(horizontal='center', vertical='center')
        ws.merge_cells('A1:E1')
        ws.row_dimensions[1].height = 35

        ws['A2'] = f'{len(files)} image(s) • Created with Bharat24Tools • {datetime.now().strftime("%d %b %Y")}'
        ws['A2'].font = Font(size=10, italic=True, color='666666')
        ws['A2'].alignment = Alignment(horizontal='center')
        ws.merge_cells('A2:E2')
        ws.row_dimensions[2].height = 22
        ws.row_dimensions[3].height = 8

        row = 4
        if add_filename:
            ws.cell(row=row, column=1, value='#')
            ws.cell(row=row, column=2, value='Image')
            ws.cell(row=row, column=3, value='Filename')
            for col in range(1, 4):
                cell = ws.cell(row=row, column=col)
                cell.font = Font(bold=True, color='FFFFFF')
                cell.fill = PatternFill('solid', fgColor='A855F7')
                cell.alignment = Alignment(horizontal='center', vertical='center')
            ws.row_dimensions[row].height = 25
            row += 1

        if add_filename:
            ws.column_dimensions['A'].width = 6
            ws.column_dimensions['B'].width = col_w / 7
            ws.column_dimensions['C'].width = 35
        else:
            ws.column_dimensions['A'].width = col_w / 7
            ws.column_dimensions['B'].width = 35

        if layout == 'one-per-row':
            for i, file in enumerate(files):
                valid, msg = validate_file(file, allowed_ext=['.jpg', '.jpeg', '.png', '.webp', '.gif'])
                if not valid:
                    continue
                input_path = os.path.join(temp_dir, f'img-{i:03d}.png')
                file.save(input_path)
                img = Image.open(input_path)
                if img.mode in ('RGBA', 'LA', 'P'):
                    bg = Image.new('RGB', img.size, (255, 255, 255))
                    bg.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                    img = bg
                elif img.mode != 'RGB':
                    img = img.convert('RGB')
                img.thumbnail((img_px, img_px), Image.LANCZOS)
                png_path = os.path.join(temp_dir, f'thumb-{i:03d}.png')
                img.save(png_path, 'PNG')
                ws.row_dimensions[row].height = row_h
                if add_filename:
                    ws.cell(row=row, column=1, value=i+1).alignment = Alignment(horizontal='center', vertical='center')
                    xl_img = XLImage(png_path)
                    xl_img.width = img.width
                    xl_img.height = img.height
                    ws.add_image(xl_img, f'B{row}')
                    ws.cell(row=row, column=3, value=file.filename).alignment = Alignment(horizontal='left', vertical='center')
                else:
                    ws.cell(row=row, column=1, value=i+1).alignment = Alignment(horizontal='center', vertical='center')
                    xl_img = XLImage(png_path)
                    xl_img.width = img.width
                    xl_img.height = img.height
                    ws.add_image(xl_img, f'A{row}')
                    ws.cell(row=row, column=2, value=file.filename).alignment = Alignment(horizontal='left', vertical='center')
                row += 1
        else:
            cols = int(layout.split('-')[1])
            for c in range(cols):
                col_letter = get_column_letter(c + 1)
                ws.column_dimensions[col_letter].width = col_w / 7
            img_index = 0
            while img_index < len(files):
                ws.row_dimensions[row].height = row_h
                for c in range(cols):
                    if img_index >= len(files):
                        break
                    file = files[img_index]
                    valid, msg = validate_file(file, allowed_ext=['.jpg', '.jpeg', '.png', '.webp', '.gif'])
                    if not valid:
                        img_index += 1
                        continue
                    input_path = os.path.join(temp_dir, f'img-{img_index:03d}.png')
                    file.save(input_path)
                    img = Image.open(input_path)
                    if img.mode in ('RGBA', 'LA', 'P'):
                        bg = Image.new('RGB', img.size, (255, 255, 255))
                        bg.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                        img = bg
                    elif img.mode != 'RGB':
                        img = img.convert('RGB')
                    img.thumbnail((img_px, img_px), Image.LANCZOS)
                    png_path = os.path.join(temp_dir, f'thumb-{img_index:03d}.png')
                    img.save(png_path, 'PNG')
                    col_letter = get_column_letter(c + 1)
                    xl_img = XLImage(png_path)
                    xl_img.width = img.width
                    xl_img.height = img.height
                    ws.add_image(xl_img, f'{col_letter}{row}')
                    img_index += 1
                row += 1

        ws.freeze_panes = 'A5'
        wb.save(output_path)
        print(f'✅ Image to Excel: {len(files)} images, layout={layout}', flush=True)
        return send_file(
            output_path,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name='Bharat24Tools_images.xlsx'
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f'❌ Image to Excel error: {e}', flush=True)
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
        if not valid:
            return msg, 400

        text = request.form.get('text', 'Bharat24Tools')
        opacity = float(request.form.get('opacity', '0.3'))
        if opacity < 0.1 or opacity > 1.0:
            opacity = 0.3

        input_path = os.path.join(temp_dir, 'input.pdf')
        output_path = os.path.join(temp_dir, 'watermarked.pdf')
        file.save(input_path)

        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter
        from PyPDF2 import PdfReader, PdfWriter

        reader = PdfReader(input_path)
        writer = PdfWriter()

        for page in reader.pages:
            page_width = float(page.mediabox.width)
            page_height = float(page.mediabox.height)

            packet = io.BytesIO()
            can = canvas.Canvas(packet, pagesize=(page_width, page_height))
            can.saveState()
            can.setFont('Helvetica-Bold', 60)
            can.setFillColorRGB(0.66, 0.33, 0.97, alpha=opacity)
            can.translate(page_width / 2, page_height / 2)
            can.rotate(45)
            can.drawCentredString(0, 0, text)
            can.saveState()
            can.restoreState()
            can.save()
            packet.seek(0)

            watermark_page = PdfReader(packet).pages[0]
            page.merge_page(watermark_page)
            writer.add_page(page)

        with open(output_path, 'wb') as f:
            writer.write(f)

        print(f'✅ Watermark added', flush=True)
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
        if not valid:
            return msg, 400

        pages_to_delete = request.form.get('pages', '').strip()
        if not pages_to_delete:
            return 'Page numbers required (e.g., 1,3,5-7)', 400

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
        kept = 0
        for i, page in enumerate(reader.pages):
            page_num = i + 1
            if page_num not in delete_pages:
                writer.add_page(page)
                kept += 1

        with open(output_path, 'wb') as f:
            writer.write(f)

        print(f'✅ Deleted {len(delete_pages)} pages, kept {kept}/{total_pages}', flush=True)
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