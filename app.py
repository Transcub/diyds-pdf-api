from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
import tempfile
import os
import sys

# Add the directory containing md2pdf to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from md2pdf import convert_md_to_pdf

app = Flask(__name__)
CORS(app)  # Allow requests from your GitHub Pages app

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'service': 'DIYDS PDF Generator'})

@app.route('/generate-pdf', methods=['POST'])
def generate_pdf():
    try:
        data = request.get_json()
        if not data or 'markdown' not in data:
            return jsonify({'error': 'Missing markdown field'}), 400

        markdown = data['markdown']
        title = data.get('title', 'guide')

        # Create temp files for input/output
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(markdown)
            md_path = f.name

        pdf_path = md_path.replace('.md', '.pdf')

        # Generate PDF
        convert_md_to_pdf(markdown, pdf_path)

        # Clean up markdown temp file
        os.unlink(md_path)

        # Create safe filename
        filename = title.lower().replace(' ', '-')
        filename = ''.join(c for c in filename if c.isalnum() or c == '-') + '.pdf'

        return send_file(
            pdf_path,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        return jsonify({'error': str(e)}), 500

    finally:
        # Clean up PDF temp file
        try:
            if 'pdf_path' in locals() and os.path.exists(pdf_path):
                os.unlink(pdf_path)
        except:
            pass

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
