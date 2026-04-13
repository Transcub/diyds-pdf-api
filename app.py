"""
DIYDS Automation API
Endpoints:
  POST /publish-guide  — full pipeline: Dropbox + Stripe + GitHub
  POST /generate-pdf   — generate PDF from markdown
  GET  /health         — health check
  GET  /token-test     — test all API connections
"""

from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import os, json, base64, time, tempfile, traceback
import requests as req

app = Flask(__name__)
CORS(app)

# ── CREDENTIALS from environment variables ──
DROPBOX_APP_KEY    = os.environ.get('DROPBOX_APP_KEY', '')
DROPBOX_APP_SECRET = os.environ.get('DROPBOX_APP_SECRET', '')
DROPBOX_REFRESH    = os.environ.get('DROPBOX_REFRESH_TOKEN', '')
STRIPE_KEY         = os.environ.get('STRIPE_KEY', '')
GITHUB_TOKEN       = os.environ.get('GITHUB_TOKEN', '')
GITHUB_REPO        = os.environ.get('GITHUB_REPO', 'diyds/doityadamnself.com')
GITHUB_FILE        = os.environ.get('GITHUB_FILE', 'guides.json')
DROPBOX_FOLDER     = os.environ.get('DROPBOX_FOLDER', '/DIYDS Guides')

def get_dropbox_token():
    r = req.post('https://api.dropboxapi.com/oauth2/token', data={
        'grant_type': 'refresh_token',
        'refresh_token': DROPBOX_REFRESH,
        'client_id': DROPBOX_APP_KEY,
        'client_secret': DROPBOX_APP_SECRET,
    })
    r.raise_for_status()
    return r.json()['access_token']

def upload_to_dropbox(file_data, filename):
    token = get_dropbox_token()
    dropbox_path = f'{DROPBOX_FOLDER}/{filename}'
    r = req.post(
        'https://content.dropboxapi.com/2/files/upload',
        headers={
            'Authorization': f'Bearer {token}',
            'Dropbox-API-Arg': json.dumps({'path': dropbox_path, 'mode': 'overwrite', 'autorename': False, 'mute': False}),
            'Content-Type': 'application/octet-stream'
        },
        data=file_data
    )
    r.raise_for_status()
    token2 = get_dropbox_token()
    r2 = req.post(
        'https://api.dropboxapi.com/2/sharing/create_shared_link_with_settings',
        headers={'Authorization': f'Bearer {token2}', 'Content-Type': 'application/json'},
        json={'path': dropbox_path, 'settings': {'requested_visibility': 'public'}}
    )
    if r2.status_code == 409:
        token3 = get_dropbox_token()
        r3 = req.post(
            'https://api.dropboxapi.com/2/sharing/list_shared_links',
            headers={'Authorization': f'Bearer {token3}', 'Content-Type': 'application/json'},
            json={'path': dropbox_path, 'direct_only': True}
        )
        r3.raise_for_status()
        url = r3.json()['links'][0]['url']
    else:
        r2.raise_for_status()
        url = r2.json()['url']
    return url.replace('?dl=0', '?dl=1') if '?dl=' in url else url + '?dl=1'

def create_stripe_payment_link(title, price_dollars, description=''):
    headers = {'Authorization': f'Bearer {STRIPE_KEY}', 'Content-Type': 'application/x-www-form-urlencoded'}
    r = req.post('https://api.stripe.com/v1/products', headers=headers, data={'name': title, 'description': description or title})
    r.raise_for_status()
    product_id = r.json()['id']
    r2 = req.post('https://api.stripe.com/v1/prices', headers=headers, data={'product': product_id, 'unit_amount': int(float(price_dollars)*100), 'currency': 'usd'})
    r2.raise_for_status()
    price_id = r2.json()['id']
    r3 = req.post('https://api.stripe.com/v1/payment_links', headers=headers, data={
        'line_items[0][price]': price_id, 'line_items[0][quantity]': 1,
        'after_completion[type]': 'hosted_confirmation',
        'after_completion[hosted_confirmation][custom_message]': 'Thank you! Check your email for your guide.'
    })
    r3.raise_for_status()
    return r3.json()['url']

def get_github_guides():
    r = req.get(f'https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_FILE}',
                headers={'Authorization': f'token {GITHUB_TOKEN}', 'Accept': 'application/vnd.github.v3+json'})
    r.raise_for_status()
    data = r.json()
    return json.loads(base64.b64decode(data['content']).decode('utf-8')), data['sha']

def update_github_guides(guides, sha, message):
    content = base64.b64encode(json.dumps(guides, indent=2).encode()).decode()
    r = req.put(f'https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_FILE}',
                headers={'Authorization': f'token {GITHUB_TOKEN}', 'Accept': 'application/vnd.github.v3+json'},
                json={'message': message, 'content': content, 'sha': sha})
    r.raise_for_status()

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'service': 'DIYDS Automation API'})

@app.route('/token-test', methods=['GET'])
def token_test():
    results = {}
    try:
        get_dropbox_token()
        results['dropbox'] = 'ok'
    except Exception as e:
        results['dropbox'] = str(e)
    try:
        guides, _ = get_github_guides()
        results['github'] = f'ok — {len(guides)} guides'
    except Exception as e:
        results['github'] = str(e)
    try:
        r = req.get('https://api.stripe.com/v1/products?limit=1', headers={'Authorization': f'Bearer {STRIPE_KEY}'})
        results['stripe'] = f'ok — status {r.status_code}'
    except Exception as e:
        results['stripe'] = str(e)
    return jsonify(results)

@app.route('/generate-pdf', methods=['POST'])
def generate_pdf():
    pdf_path = None
    try:
        data = request.get_json()
        if not data or 'markdown' not in data:
            return jsonify({'error': 'Missing markdown field'}), 400
        import sys
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from md2pdf import convert_md_to_pdf
        tmp = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False)
        pdf_path = tmp.name
        tmp.close()
        convert_md_to_pdf(data['markdown'], pdf_path)
        if not os.path.exists(pdf_path) or os.path.getsize(pdf_path) == 0:
            return jsonify({'error': 'PDF generation produced empty file'}), 500
        filename = ''.join(c for c in data.get('title','guide').lower().replace(' ','-') if c.isalnum() or c=='-').strip('-') + '.pdf'
        with open(pdf_path, 'rb') as f:
            pdf_data = f.read()
        os.unlink(pdf_path)
        return Response(pdf_data, mimetype='application/pdf',
                       headers={'Content-Disposition': f'attachment; filename="{filename}"', 'Content-Length': str(len(pdf_data))})
    except Exception as e:
        if pdf_path and os.path.exists(pdf_path):
            os.unlink(pdf_path)
        return jsonify({'error': str(e)}), 500

@app.route('/publish-guide', methods=['POST'])
def publish_guide():
    try:
        title       = request.form.get('title', '')
        description = request.form.get('description', '')
        category    = request.form.get('category', 'money-credit')
        price       = request.form.get('price', '2.99')
        tags        = [t.strip() for t in request.form.get('tags', '').split(',') if t.strip()]

        if not title:
            return jsonify({'error': 'Missing title'}), 400

        pdf_file = request.files.get('pdf')
        if not pdf_file:
            return jsonify({'error': 'Missing PDF file'}), 400

        # Upload main PDF
        dropbox_url = upload_to_dropbox(pdf_file.read(), pdf_file.filename or f"{title.lower().replace(' ','-')}.pdf")

        # Upload extra files
        extra_urls = []
        for ef in request.files.getlist('extra_files'):
            ef_url = upload_to_dropbox(ef.read(), ef.filename)
            extra_urls.append({'filename': ef.filename, 'url': ef_url})

        # Create Stripe link
        stripe_url = create_stripe_payment_link(title, price, description)

        # Update GitHub
        guides, sha = get_github_guides()
        new_guide = {
            'id': int(time.time() * 1000),
            'title': title, 'desc': description, 'category': category,
            'price': str(price), 'stripe': stripe_url, 'pdf': dropbox_url,
            'tags': tags, 'status': 'active',
            'created': time.strftime('%Y-%m-%dT%H:%M:%S.000Z', time.gmtime()),
        }
        if extra_urls:
            new_guide['extraFiles'] = extra_urls
        guides.append(new_guide)
        update_github_guides(guides, sha, f'Add guide: {title}')

        return jsonify({'success': True, 'title': title, 'stripe': stripe_url, 'pdf': dropbox_url,
                       'extra_files': extra_urls, 'message': f'"{title}" is now live on doityadamnself.com!'})
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
