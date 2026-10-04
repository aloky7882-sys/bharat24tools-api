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
PROCESSING_TIMEOUT = 180
CLEANUP_DELAY = 30

processing_lock = threading.Lock()

# ==================== AUTO CLEANUP WORKER ====================
def auto_cleanup_worker():
    """Background thread — har 60 second mein temp files clean kare"""
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
    <title>Bharat24Tools API v7.0</title>
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
        .badge-new { background: #ffd166; color: #000; padding: 2px 8px; border-radius: 10px; font-size: 0.7rem; font-weight: 700; margin-left: 6px; }
        .footer { text-align: center; margin-top: 20px; color: #a5b4fc; font-size: 0.85rem; }
    </style>
</head>
<body>
    <div class="container">
        <h1>⚡ Bharat24Tools API v7.0</h1>
        <p class="status-badge">Server is running ✅ — 23 Tools Active</p>

        <div class="section-title">📄 PDF Tools (13)</div>
        <div class="endpoint"><code>POST /compress</code><span class="desc">Compress PDF</span></div>
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

        <div class="section-title">🖼 Image Tools (10 NEW) <span class="badge-new">NEW</span></div>
        <div class="endpoint"><code>POST /background-remover</code><span class="desc">AI Background Remover</span><span class="badge-new">NEW</span></div>
        <div class="endpoint"><code>POST /heic-to-jpg</code><span class="desc">HEIC to JPG</span><span class="badge-new">NEW</span></div>
        <div class="endpoint"><code>POST /webp-to-jpg</code><span class="desc">WebP to JPG</span><span class="badge-new">NEW</span></div>
        <div class="endpoint"><code>POST /image-upscaler</code><span class="desc">AI Image Upscaler</span><span class="badge-new">NEW</span></div>
        <div class="endpoint"><code>POST /ocr</code><span class="desc">OCR Multi-Language</span><span class="badge-new">NEW</span></div>
        <div class="endpoint"><code>POST /avif-to-jpg</code><span class="desc">AVIF to JPG</span><span class="badge-new">NEW</span></div>
        <div class="endpoint"><code>POST /image-to-sketch</code><span class="desc">Image to Sketch</span><span class="badge-new">NEW</span></div>
        <div class="endpoint"><code>POST /gif-maker</code><span class="desc">GIF Maker</span><span class="badge-new">NEW</span></div>
        <div class="endpoint"><code>POST /pdf-watermark</code><span class="desc">PDF Watermark</span><span class="badge-new">NEW</span></div>
        <div class="endpoint"><code>POST /pdf-page-delete</code><span class="desc">PDF Page Delete</span><span class="badge-new">NEW</span></div>

        <p class="footer">Version 7.0 — 23 Tools Active | Auto-Cleanup ON</p>
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
        'version': '7.0',
        'tools': 23,
        'ghostscript': True,
        'auto_cleanup': True
    }


# ========== 1. COMPRESS PDF ==========
@app.route('/compress', methods=['POST'])
def compress():
    if not processing_lock.acquire(timeout=180):
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
    if not processing_lock.acquire(timeout=180):
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
    if not processing_lock.acquire(timeout=180):
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
        image_paths = []
        for i, file in enumerate(files):
            valid, msg = validate_file(file, allowed_ext=['.jpg', '.jpeg', '.png'])
            if not valid:
                return f'File {i+1}: {msg}', 400
            path = os.path.join(temp_dir, f'img-{i:03d}{os.path.splitext(file.filename)[1].lower()}')
            file.save(path)
            image_paths.append(path)
        if not image_paths:
            return 'No valid images', 400
        output_path = os.path.join(temp_dir, 'output.pdf')
        cmd = ['gs', '-sDEVICE=pdfwrite', '-dNOPAUSE', '-dBATCH', '-dQUIET',
               '-dPDFFitPage', f'-sOutputFile={output_path}'] + image_paths
        subprocess.run(cmd, check=True, timeout=PROCESSING_TIMEOUT, capture_output=True)
        if not os.path.exists(output_path):
            return 'PDF creation failed', 500
        print(f'✅ JPG to PDF: {len(image_paths)} images', flush=True)
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
    if not processing_lock.acquire(timeout=180):
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
    if not processing_lock.acquire(timeout=180):
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
    if not processing_lock.acquire(timeout=180):
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
        output_path = os.path.join(temp_dir, 'output.pdf')
        file.save(input_path)
        from openpyxl import load_workbook
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib import colors
        wb = load_workbook(input_path, data_only=True)
        sheet = wb.active
        pdf = SimpleDocTemplate(output_path, pagesize=landscape(A4), leftMargin=10*mm, rightMargin=10*mm, topMargin=10*mm, bottomMargin=10*mm)
        styles = getSampleStyleSheet()
        story = [Paragraph(f'<b>{sheet.title}</b>', styles['Heading1']), Spacer(1, 10)]
        table_data = []
        for row in sheet.iter_rows(values_only=True):
            row_data = [str(cell) if cell is not None else '' for cell in row]
            if any(row_data):
                table_data.append(row_data)
        if not table_data:
            return 'Excel file is empty', 400
        table = Table(table_data, repeatRows=1)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#a855f7')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f5ff')]),
        ]))
        story.append(table)
        pdf.build(story)
        print(f'✅ Excel to PDF: {os.path.getsize(output_path)} bytes', flush=True)
        return send_file(output_path, mimetype='application/pdf', as_attachment=True, download_name='converted.pdf')
    except Exception as e:
        print(f'❌ Excel to PDF error: {e}', flush=True)
        return f'Error: {str(e)}', 500
    finally:
        processing_lock.release()
        cleanup_dir(temp_dir)


# ========== 7. PDF TO EXCEL ==========
@app.route('/pdf-to-excel', methods=['POST'])
def pdf_to_excel():
    if not processing_lock.acquire(timeout=180):
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
    if not processing_lock.acquire(timeout=180):
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
    if not processing_lock.acquire(timeout=180):
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
    if not processing_lock.acquire(timeout=180):
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
    if not processing_lock.acquire(timeout=180):
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
    if not processing_lock.acquire(timeout=180):
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
    if not processing_lock.acquire(timeout=180):
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
# ==================== 10 NEW GLOBAL TOOLS ============================
# =====================================================================


# ========== 14. BACKGROUND REMOVER (AI - rembg) ==========
@app.route('/background-remover', methods=['POST'])
def background_remover():
    if not processing_lock.acquire(timeout=240):
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

        from rembg import remove
        from PIL import Image

        input_img = Image.open(input_path)
        output_img = remove(input_img)
        output_img.save(output_path, 'PNG')

        print(f'✅ Background removed: {os.path.getsize(output_path)} bytes', flush=True)
        return send_file(output_path, mimetype='image/png', as_attachment=True, download_name='background-removed.png')
    except Exception as e:
        print(f'❌ BG Remover error: {e}', flush=True)
        return f'Error: {str(e)}', 500
    finally:
        processing_lock.release()
        cleanup_dir(temp_dir)


# ========== 15. HEIC TO JPG ==========
@app.route('/heic-to-jpg', methods=['POST'])
def heic_to_jpg():
    if not processing_lock.acquire(timeout=180):
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


# ========== 16. WEBP TO JPG ==========
@app.route('/webp-to-jpg', methods=['POST'])
def webp_to_jpg():
    if not processing_lock.acquire(timeout=180):
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


# ========== 17. IMAGE UPSCALER ==========
@app.route('/image-upscaler', methods=['POST'])
def image_upscaler():
    if not processing_lock.acquire(timeout=240):
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

        from PIL import Image, ImageFilter, ImageEnhance
        img = Image.open(input_path)
        new_size = (img.width * scale, img.height * scale)
        upscaled = img.resize(new_size, Image.LANCZOS)
        # Sharpen
        upscaled = upscaled.filter(ImageFilter.UnsharpMask(radius=2, percent=150, threshold=3))
        # Enhance
        enhancer = ImageEnhance.Contrast(upscaled)
        upscaled = enhancer.enhance(1.1)
        upscaled = upscaled.filter(ImageFilter.SMOOTH_MORE)
        upscaled.save(output_path, 'PNG')

        print(f'✅ Upscaled {scale}x: {new_size}', flush=True)
        return send_file(output_path, mimetype='image/png', as_attachment=True, download_name='upscaled.png')
    except Exception as e:
        print(f'❌ Upscaler error: {e}', flush=True)
        return f'Error: {str(e)}', 500
    finally:
        processing_lock.release()
        cleanup_dir(temp_dir)


# ========== 18. OCR MULTILINGUAL ==========
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


# ========== 19. AVIF TO JPG ==========
@app.route('/avif-to-jpg', methods=['POST'])
def avif_to_jpg():
    if not processing_lock.acquire(timeout=180):
        return 'Server busy. Try again.', 503
    temp_dir = tempfile.mkdtemp()
    try:
        if 'file' not in request.files:
            return 'No file uploaded', 400
        file = request.files['file']
        valid, msg = validate_file(file, allowed_ext=['.avif'])
        if not valid:
            return msg, 400
        input_path = os.path.join(temp_dir, 'input.avif')
        output_path = os.path.join(temp_dir, 'output.jpg')
        file.save(input_path)

        try:
            import pillow_avif
        except:
            pass
        from PIL import Image
        img = Image.open(input_path)
        if img.mode != 'RGB':
            img = img.convert('RGB')
        img.save(output_path, 'JPEG', quality=92)

        print(f'✅ AVIF to JPG', flush=True)
        return send_file(output_path, mimetype='image/jpeg', as_attachment=True, download_name='converted.jpg')
    except Exception as e:
        print(f'❌ AVIF error: {e}', flush=True)
        return f'Error: {str(e)}', 500
    finally:
        processing_lock.release()
        cleanup_dir(temp_dir)


# ========== 20. IMAGE TO SKETCH ==========
@app.route('/image-to-sketch', methods=['POST'])
def image_to_sketch():
    if not processing_lock.acquire(timeout=180):
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


# ========== 21. GIF MAKER ==========
@app.route('/gif-maker', methods=['POST'])
def gif_maker():
    if not processing_lock.acquire(timeout=240):
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
            # Resize all to same size
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


# ========== 22. PDF WATERMARK ==========
@app.route('/pdf-watermark', methods=['POST'])
def pdf_watermark():
    if not processing_lock.acquire(timeout=180):
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

            # Create watermark
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


# ========== 23. PDF PAGE DELETE ==========
@app.route('/pdf-page-delete', methods=['POST'])
def pdf_page_delete():
    if not processing_lock.acquire(timeout=180):
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

        # Parse page numbers
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