from flask import Flask, request, send_file, render_template_string
from flask_cors import CORS
import os
import subprocess
import tempfile

app = Flask(__name__)
CORS(app)

HTML = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>PDF Compress - Bharat24Tools API</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * { margin:0; padding:0; box-sizing:border-box; font-family:Arial,sans-serif; }
        body { background: linear-gradient(135deg, #0f0f1e, #533483); min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 20px; color: #fff; }
        .container { background: rgba(30,27,75,0.95); padding: 40px; border-radius: 20px; max-width: 500px; width: 100%; text-align: center; border: 1px solid rgba(168,85,247,0.3); }
        h1 { color: #a855f7; margin-bottom: 10px; font-size: 1.5rem; }
        p { color: #a5b4fc; margin-bottom: 20px; font-size: 0.9rem; }
        input, button { width: 100%; padding: 14px; margin: 10px 0; border-radius: 10px; border: none; font-size: 16px; }
        input { background: #1a1a2e; color: #fff; }
        button { background: linear-gradient(135deg, #a855f7, #ec4899); color: #fff; font-weight: bold; cursor: pointer; }
        button:disabled { opacity: 0.6; }
        #status { margin-top: 15px; padding: 12px; border-radius: 8px; font-weight: 600; font-size: 0.9rem; display: none; }
        .success { background: rgba(34,197,94,0.2); color: #86efac; display: block; }
        .error { background: rgba(239,68,68,0.2); color: #fca5a5; display: block; }
        .info { background: rgba(99,102,241,0.2); color: #a5b4fc; display: block; }
    </style>
</head>
<body>
    <div class="container">
        <h1>📉 Compress PDF</h1>
        <p>Bharat24Tools API is running ✅</p>
        <input type="file" id="fileInput" accept=".pdf">
        <button id="btn">Compress & Download</button>
        <div id="status"></div>
    </div>
    <script>
        const btn = document.getElementById('btn');
        const fileInput = document.getElementById('fileInput');
        const status = document.getElementById('status');
        btn.onclick = async () => {
            const file = fileInput.files[0];
            if (!file) { status.className = 'error'; status.textContent = '❌ Please select a PDF'; return; }
            btn.disabled = true;
            status.className = 'info';
            status.textContent = '⏳ Compressing...';
            const formData = new FormData();
            formData.append('file', file);
            try {
                const res = await fetch('/compress', { method: 'POST', body: formData });
                if (!res.ok) throw new Error('Server error');
                const blob = await res.blob();
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = 'compressed.pdf';
                a.click();
                status.className = 'success';
                status.textContent = '🎉 Downloaded!';
            } catch (err) {
                status.className = 'error';
                status.textContent = '❌ ' + err.message;
            }
            btn.disabled = false;
        };
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(HTML)

@app.route('/health')
def health():
    return {'status': 'ok', 'service': 'bharat24tools-api'}

@app.route('/compress', methods=['POST'])
def compress():
    if 'file' not in request.files:
        return 'No file uploaded', 400
    file = request.files['file']
    if file.filename == '':
        return 'Empty filename', 400
    if not file.filename.lower().endswith('.pdf'):
        return 'Only PDF files allowed', 400
    
    temp_dir = tempfile.mkdtemp()
    input_path = os.path.join(temp_dir, 'input.pdf')
    output_path = os.path.join(temp_dir, 'output.pdf')
    
    try:
        file.save(input_path)
        input_size = os.path.getsize(input_path)
        
        subprocess.run([
            'gs', '-sDEVICE=pdfwrite', '-dCompatibilityLevel=1.4',
            '-dPDFSETTINGS=/ebook', '-dNOPAUSE', '-dQUIET', '-dBATCH',
            '-dDetectDuplicateImages=true', '-dCompressFonts=true',
            f'-sOutputFile={output_path}', input_path
        ], check=True, timeout=120, capture_output=True)
        
        if not os.path.exists(output_path):
            return 'Compression failed', 500
        
        output_size = os.path.getsize(output_path)
        if output_size >= input_size:
            return send_file(input_path, mimetype='application/pdf', as_attachment=True, download_name='compressed.pdf')
        return send_file(output_path, mimetype='application/pdf', as_attachment=True, download_name='compressed.pdf')
    except subprocess.TimeoutExpired:
        return 'Timeout - file too large', 500
    except subprocess.CalledProcessError as e:
        return f'Error: {e.stderr.decode()[:200]}', 500
    except Exception as e:
        return f'Error: {str(e)}', 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)