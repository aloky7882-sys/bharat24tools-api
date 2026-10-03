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
MAX_FILE_SIZE = 15 * 1024 * 1024
MAX_FILES_COUNT = 20
PROCESSING_TIMEOUT = 120
CLEANUP_DELAY = 60

processing_lock = threading.Lock()


# ==================== BACKUP CLEANUP ====================
@app.before_request
def backup_cleanup():
    try:
        now = time.time()
        for folder in glob.glob('/tmp/tmp*'):
            try:
                if os.path.getmtime(folder) < now - 300:
                    shutil.rmtree(folder, ignore_errors=True)
                    print(f'🧹 Backup cleanup: {folder}', flush=True)
            except:
                pass
    except Exception as e:
        print(f'⚠️ Backup error: {e}', flush=True)


# ==================== HOME PAGE ====================
HTML = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Bharat24Tools API v6.0</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * { margin:0; padding:0; box-sizing:border-box; font-family:Arial,sans-serif; }
        body { background: linear-gradient(135deg, #0f0f1e, #533483); min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 20px; color: #fff; }
        .container { background: rgba(30,27,75,0.95); padding: 40px; border-radius: 20px; max-width: 600px; width: 100%; border: 1px solid rgba(168,85,247,0.3); }
        h1 { color: #a855f7; margin-bottom: 10px; text-align: center; font-size: 1.5rem; }
        .status-badge { text-align: center; color: #86efac; margin-bottom: 25px; font-weight: 600; }
        .endpoint { background: rgba(99,102,241,0.1); padding: 12px; border-radius: 8px; margin: 6px 0; font-size: 0.85rem; border-left: 3px solid #a855f7; }
        .endpoint code { color: #86efac; background: rgba(0,0,0,0.3); padding: 2px 6px; border-radius: 4px; font-size: 0.8rem; }
        .endpoint .desc { color: #a5b4fc; margin-left: 8px; }
        .footer { text-align: center; margin-top: 20px; color: #a5b4fc; font-size: 0.85rem; }
    </style>
</head>
<body>
    <div class="container">
        <h1>⚡ Bharat24Tools API v6.0</h1>
        <p class="status-badge">Server is running ✅ — 13 Tools Active (No Ghostscript)</p>
        <div class="endpoint"><code>POST /compress</code><span class="desc">Compress PDF</span></div>
        <div class="endpoint"><code>POST /pdf-to-jpg</code><span class="desc">PDF to Images</span></div>
        <div class="endpoint"><code>POST /jpg-to-pdf</code><span class="desc">Images to PDF ✅ FIXED</span></div>
        <div class="endpoint"><code>POST /pdf-to-word</code><span class="desc">PDF to Word ✅ FIXED</span></div>
        <div class="endpoint"><code>POST /word-to-pdf</code><span class="desc">Word to PDF</span></div>
        <div class="endpoint"><code>POST /excel-to-pdf</code><span class="desc">Excel to PDF</span></div>
        <div class="endpoint"><code>POST /pdf-to-excel</code><span class="desc">PDF to Excel ✅ FIXED</span></div>
        <div class="endpoint"><code>POST /excel-to-image</code><span class="desc">Excel to Image</span></div>
        <div class="endpoint"><code>POST /merge-pdf</code><span class="desc">Merge PDFs ✅ FIXED</span></div>
        <div class="endpoint"><code>POST /split-pdf</code><span class="desc">Split PDF ✅ FIXED</span></div>
        <div class="endpoint"><code>POST /rotate-pdf</code><span class="desc">Rotate PDF ✅ FIXED</span></div>
        <div class="endpoint"><code>POST /protect-pdf</code><span class="desc">Protect PDF ✅ FIXED</span></div>
        <div class="endpoint"><code>POST /unlock-pdf</code><span class="desc">Unlock PDF ✅ FIXED</span></div>
        <div class="endpoint"><code>GET /health</code><span class="desc">Health Check</span></div>
        <p class="footer">Version 6.0 — No Ghostscript Required</p>
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
            print(f'✅ Cleaned: {temp_dir}', flush=True)
        except Exception as e:
            print(f'⚠️ Cleanup failed: {e}', flush=True)
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
        return False, f'File too large. Max {max_size/1024/1024:.1f}MB. Yours: {size/1024/1024:.1f}MB'
    if size == 0:
        return False, 'File is empty'
    return True, 'OK'


# ==================== ROUTES ====================
@app.route('/')
def index():
    return render_template_string(HTML)


@app.route('/health')
def health():
    return {'status': 'ok', 'service': 'bharat24tools-api', 'version': '6.0', 'tools': 13, 'ghostscript': False}


# ========== 1. COMPRESS PDF (PyPDF2 — No Ghostscript) ==========
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

        # PyPDF2 compression (rewrites PDF with compression)
        from PyPDF2 import PdfReader, PdfWriter
        reader = PdfReader(input_path)
        writer = PdfWriter()
        for page in reader.pages:
            page.compress_content_streams()
            writer.add_page(page)
        # Set PDF metadata to reduce size
        writer.add_metadata({
            '/Producer': 'Bharat24Tools',
            '/Creator': 'Bharat24Tools'
        })
        with open(output_path, 'wb') as f:
            writer.write(f)

        output_size = os.path.getsize(output_path)
        saved = ((input_size - output_size) / input_size * 100) if input_size > 0 else 0
        print(f'✅ Compress: {input_size/1024/1024:.2f}MB → {output_size/1024/1024:.2f}MB ({saved:.1f}%)', flush=True)
        return send_file(output_path, mimetype='application/pdf', as_attachment=True, download_name='compressed.pdf')
    except Exception as e:
        print(f'❌ Compress error: {e}', flush=True)
        return f'Error: {str(e)}', 500
    finally:
        processing_lock.release()
        cleanup_dir(temp_dir)


# ========== 2. PDF TO JPG (pdf2image + Pillow) ==========
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

        # Use pdf2image with PIL (needs poppler-utils, which is available on Render)
        from pdf2image import convert_from_path
        images = convert_from_path(input_path, dpi=150, fmt='jpeg')

        if not images:
            return 'No pages converted', 500

        jpg_files = []
        for i, img in enumerate(images):
            path = os.path.join(temp_dir, f'page-{i+1:03d}.jpg')
            img.save(path, 'JPEG', quality=90)
            jpg_files.append(os.path.basename(path))

        print(f'✅ PDF to JPG: {len(jpg_files)} pages', flush=True)

        if len(jpg_files) == 1:
            return send_file(os.path.join(temp_dir, jpg_files[0]), mimetype='image/jpeg', as_attachment=True, download_name='page-1.jpg')

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for jpg in jpg_files:
                zf.write(os.path.join(temp_dir, jpg), jpg)
        zip_buffer.seek(0)
        return send_file(zip_buffer, mimetype='application/zip', as_attachment=True, download_name='pdf-pages.zip')
    except Exception as e:
        print(f'❌ PDF to JPG error: {e}', flush=True)
        return f'Error: {str(e)}', 500
    finally:
        processing_lock.release()
        cleanup_dir(temp_dir)


# ========== 3. JPG TO PDF (Pillow — NO GHOSTSCRIPT) ✅ FIXED ==========
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

        # Load all images with Pillow
        from PIL import Image
        images = []
        for i, file in enumerate(files):
            valid, msg = validate_file(file, allowed_ext=['.jpg', '.jpeg', '.png'])
            if not valid:
                return f'File {i+1}: {msg}', 400
            path = os.path.join(temp_dir, f'img-{i:03d}{os.path.splitext(file.filename)[1].lower()}')
            file.save(path)
            img = Image.open(path)
            # Convert to RGB (removes alpha channel for JPEG)
            if img.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            images.append(img)

        if not images:
            return 'No valid images', 400

        # Save first image as PDF, append rest
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


# ========== 4. PDF TO WORD (pdfplumber — NO GHOSTSCRIPT) ✅ FIXED ==========
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
        file.save(input_path)

        # Use pdfplumber (pure Python, no external deps)
        import pdfplumber
        full_text = ""
        with pdfplumber.open(input_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                full_text += text + "\n"

        if not full_text.strip():
            return 'No text found (maybe scanned image)', 400

        from docx import Document
        from docx.shared import Pt, RGBColor
        doc = Document()
        heading = doc.add_heading('Converted from PDF', 0)
        heading.runs[0].font.color.rgb = RGBColor(0xa8, 0x55, 0xf7)
        for line in full_text.split('\n'):
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


# ========== 5. WORD TO PDF (already fine) ==========
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


# ========== 6. EXCEL TO PDF (already fine) ==========
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


# ========== 7. PDF TO EXCEL (pdfplumber — NO GHOSTSCRIPT) ✅ FIXED ==========
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
        output_path = os.path.join(temp_dir, 'output.xlsx')
        file.save(input_path)

        import pdfplumber
        full_text = ""
        with pdfplumber.open(input_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                full_text += text + "\n"

        if not full_text.strip():
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
        for line in full_text.split('\n'):
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


# ========== 8. EXCEL TO IMAGE (already fine) ==========
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


# ========== 9. MERGE PDF (PyPDF2 — NO GHOSTSCRIPT) ✅ FIXED ==========
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

        from PyPDF2 import PdfReader, PdfWriter
        writer = PdfWriter()

        for i, file in enumerate(files):
            valid, msg = validate_file(file, allowed_ext=['.pdf'])
            if not valid:
                return f'File {i+1}: {msg}', 400
            path = os.path.join(temp_dir, f'input-{i:03d}.pdf')
            file.save(path)
            reader = PdfReader(path)
            for page in reader.pages:
                writer.add_page(page)

        output_path = os.path.join(temp_dir, 'merged.pdf')
        with open(output_path, 'wb') as f:
            writer.write(f)

        if not os.path.exists(output_path):
            return 'Merge failed', 500

        print(f'✅ Merged {len(files)} PDFs → {os.path.getsize(output_path)} bytes', flush=True)
        return send_file(output_path, mimetype='application/pdf', as_attachment=True, download_name='merged.pdf')
    except Exception as e:
        print(f'❌ Merge error: {e}', flush=True)
        return f'Error: {str(e)}', 500
    finally:
        processing_lock.release()
        cleanup_dir(temp_dir)


# ========== 10. SPLIT PDF (PyPDF2 — NO QPDF) ✅ FIXED ==========
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

        from PyPDF2 import PdfReader, PdfWriter
        reader = PdfReader(input_path)
        total_pages = len(reader.pages)

        if total_pages == 0:
            return 'Cannot read PDF', 400

        # If custom range specified, extract those pages
        if pages:
            page_nums = []
            for part in pages.split(','):
                part = part.strip()
                if '-' in part:
                    start, end = part.split('-')
                    page_nums.extend(range(int(start), int(end) + 1))
                else:
                    page_nums.append(int(part))
            # Convert to 0-indexed
            page_nums = [p - 1 for p in page_nums if 1 <= p <= total_pages]
            if not page_nums:
                return 'Invalid page range', 400

            writer = PdfWriter()
            for p in page_nums:
                writer.add_page(reader.pages[p])
            output_path = os.path.join(temp_dir, 'extracted.pdf')
            with open(output_path, 'wb') as f:
                writer.write(f)
            print(f'✅ Extracted {len(page_nums)} pages', flush=True)
            return send_file(output_path, mimetype='application/pdf', as_attachment=True, download_name='extracted.pdf')

        # Otherwise, split all pages
        output_files = []
        for i, page in enumerate(reader.pages):
            writer = PdfWriter()
            writer.add_page(page)
            path = os.path.join(temp_dir, f'page-{i+1:03d}.pdf')
            with open(path, 'wb') as f:
                writer.write(f)
            output_files.append(os.path.basename(path))

        if not output_files:
            return 'Split failed', 500

        print(f'✅ Split: {len(output_files)} pages', flush=True)

        if len(output_files) == 1:
            return send_file(os.path.join(temp_dir, output_files[0]), mimetype='application/pdf', as_attachment=True, download_name='page-1.pdf')

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for pdf in output_files:
                zf.write(os.path.join(temp_dir, pdf), pdf)
        zip_buffer.seek(0)
        return send_file(zip_buffer, mimetype='application/zip', as_attachment=True, download_name='split-pages.zip')
    except Exception as e:
        print(f'❌ Split error: {e}', flush=True)
        return f'Error: {str(e)}', 500
    finally:
        processing_lock.release()
        cleanup_dir(temp_dir)


# ========== 11. ROTATE PDF (PyPDF2 — NO QPDF) ✅ FIXED ==========
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

        from PyPDF2 import PdfReader, PdfWriter
        reader = PdfReader(input_path)
        writer = PdfWriter()

        for page in reader.pages:
            page.rotate(angle)
            writer.add_page(page)

        with open(output_path, 'wb') as f:
            writer.write(f)

        if not os.path.exists(output_path):
            return 'Rotation failed', 500

        print(f'✅ Rotated {angle}° — Output: {os.path.getsize(output_path)} bytes', flush=True)
        return send_file(output_path, mimetype='application/pdf', as_attachment=True, download_name='rotated.pdf')
    except Exception as e:
        print(f'❌ Rotate error: {e}', flush=True)
        return f'Error: {str(e)}', 500
    finally:
        processing_lock.release()
        cleanup_dir(temp_dir)


# ========== 12. PROTECT PDF (PyPDF2 — NO QPDF) ✅ FIXED ==========
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

        from PyPDF2 import PdfReader, PdfWriter
        reader = PdfReader(input_path)
        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page)

        writer.encrypt(user_password=password, owner_password=password, use_128bit=True)

        with open(output_path, 'wb') as f:
            writer.write(f)

        if not os.path.exists(output_path):
            return 'Encryption failed', 500

        print(f'✅ Protected with password', flush=True)
        return send_file(output_path, mimetype='application/pdf', as_attachment=True, download_name='protected.pdf')
    except Exception as e:
        print(f'❌ Protect error: {e}', flush=True)
        return f'Error: {str(e)}', 500
    finally:
        processing_lock.release()
        cleanup_dir(temp_dir)


# ========== 13. UNLOCK PDF (PyPDF2 — NO QPDF) ✅ FIXED ==========
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

        from PyPDF2 import PdfReader, PdfWriter
        reader = PdfReader(input_path)
        if reader.is_encrypted:
            result = reader.decrypt(password)
            if result == 0:
                return 'Wrong password', 400

        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page)

        with open(output_path, 'wb') as f:
            writer.write(f)

        if not os.path.exists(output_path):
            return 'Unlock failed', 500

        print(f'✅ Unlocked PDF', flush=True)
        return send_file(output_path, mimetype='application/pdf', as_attachment=True, download_name='unlocked.pdf')
    except Exception as e:
        print(f'❌ Unlock error: {e}', flush=True)
        return f'Error: {str(e)}', 500
    finally:
        processing_lock.release()
        cleanup_dir(temp_dir)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)