from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
import tempfile
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from md2pdf import convert_md_to_pdf

app = Flask(__name__)
CORS(app)

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'service': 'DIYDS PDF Generator'})

@app.route('/generate-pdf', methods=['POST'])
def generate_pdf():
    pdf_path = None
    try:
        data = request.get_json()
        if not data or 'markdown' not in data:
            return jsonify({'error': 'Missing markdown field'}), 400

        markdown = data['markdown']
        title = data.get('title', 'guide')

        # Create temp PDF — delete=False so we can send it after creation
        tmp = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False)
        pdf_path = tmp.name
        tmp.close()

        # Generate PDF
        convert_md_to_pdf(markdown, pdf_path)

        # Verify file exists and has content
        if not os.path.exists(pdf_path) or os.path.getsize(pdf_path) == 0:
            return jsonify({'error': 'PDF generation produced empty file'}), 500

        # Safe filename
        filename = ''.join(c for c in title.lower().replace(' ','-') if c.isalnum() or c=='-')
        filename = filename.strip('-') + '.pdf'

        # Read file into memory so we can delete it before sending
        with open(pdf_path, 'rb') as f:
            pdf_data = f.read()
        os.unlink(pdf_path)

        # Return PDF bytes directly
        from flask import Response
        return Response(
            pdf_data,
            mimetype='application/pdf',
            headers={
                'Content-Disposition': f'attachment; filename="{filename}"',
                'Content-Length': str(len(pdf_data))
            }
        )

    except Exception as e:
        try:
            if pdf_path and os.path.exists(pdf_path):
                os.unlink(pdf_path)
        except Exception:
            pass
        print(f"PDF error: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
