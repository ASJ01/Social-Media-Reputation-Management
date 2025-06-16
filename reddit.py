import os
import random
import string
from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv
import requests

load_dotenv()

app = Flask(__name__, static_folder='static')

# Reddit config
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")
REDDIT_REDIRECT_URI = os.getenv("REDDIT_REDIRECT_URI", "http://localhost:5000/auth/reddit/callback")

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/reddit/auth', methods=['POST'])
def reddit_auth():
    content = request.json.get('content')
    if not content:
        return jsonify({'error': 'Content is required'}), 400

    # Generate a unique state for this request
    state = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
    
    # Store post data in session
    app.config['pending_post'] = {
        'content': content
    }

    # Request authorization
    scope = "submit identity"
    auth_url = (
        f"https://www.reddit.com/api/v1/authorize"
        f"?client_id={REDDIT_CLIENT_ID}"
        f"&response_type=code"
        f"&state={state}"
        f"&redirect_uri={REDDIT_REDIRECT_URI}"
        f"&duration=temporary"
        f"&scope={scope}"
    )

    return jsonify({'authUrl': auth_url})

@app.route('/auth/reddit/callback')
def reddit_callback():
    code = request.args.get('code')
    error = request.args.get('error')

    if error:
        return f"""
            <script>
                window.opener.postMessage({{ error: '{error}' }}, '*');
                window.close();
            </script>
        """

    if not code:
        return "Missing authorization code", 400

    post_data = app.config.get('pending_post')
    if not post_data:
        return "No pending post found", 400

    try:
        # Get access token
        token_response = requests.post(
            "https://www.reddit.com/api/v1/access_token",
            auth=(REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET),
            data={
                'grant_type': 'authorization_code',
                'code': code,
                'redirect_uri': REDDIT_REDIRECT_URI
            },
            headers={
                'User-Agent': 'FlaskRedditBot/0.1'
            }
        ).json()

        access_token = token_response.get('access_token')
        if not access_token:
            raise Exception("No access token received")

        # Submit post
        submit_response = requests.post(
            "https://oauth.reddit.com/api/submit",
            headers={
                'Authorization': f'bearer {access_token}',
                'User-Agent': 'FlaskRedditBot/0.1'
            },
            data={
                'sr': 'test',  # Default subreddit
                'title': 'New Post',  # Default title
                'text': post_data['content'],
                'kind': 'self'
            }
        ).json()

        post_url = f"https://reddit.com{submit_response.get('json', {}).get('data', {}).get('url', '')}"

        # Clear the pending post
        app.config.pop('pending_post', None)

        return f"""
            <script>
                window.opener.postMessage({{ success: true, postUrl: '{post_url}' }}, '*');
                window.close();
            </script>
        """

    except Exception as e:
        return f"""
            <script>
                window.opener.postMessage({{ error: 'server_error', errorDescription: '{str(e)}' }}, '*');
                window.close();
            </script>
        """

if __name__ == '__main__':
    app.run(debug=True)
