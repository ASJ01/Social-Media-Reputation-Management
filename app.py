from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import subprocess
import os
from dotenv import load_dotenv
import requests
import random
import string
import secrets
import base64
import hashlib
from flask_session import Session
import tweepy
from datetime import datetime
from pymongo import MongoClient
from twitter_dataset.twitter_sentiment_analysis import analyze_sentiment
from linkedin_api import Linkedin
import json

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "fallback_secret_key")

# Configure session
app.config.update(
    SESSION_COOKIE_NAME='session',
    SESSION_COOKIE_SAMESITE=None,
    SESSION_COOKIE_SECURE=False,
    SESSION_COOKIE_HTTPONLY=True,
    PERMANENT_SESSION_LIFETIME=3600,  # 1 hour
    SESSION_TYPE='filesystem'
)
Session(app)

# LinkedIn credentials
LINKEDIN_CLIENT_ID = os.getenv("LINKEDIN_CLIENT_ID")
LINKEDIN_CLIENT_SECRET = os.getenv("LINKEDIN_CLIENT_SECRET")
LINKEDIN_REDIRECT_URI = os.getenv("LINKEDIN_REDIRECT_URI", "http://localhost:5000/auth/linkedin/callback")

# Twitter credentials
TWITTER_CLIENT_ID = os.getenv("TWITTER_CLIENT_ID")
TWITTER_CLIENT_SECRET = os.getenv("TWITTER_CLIENT_SECRET")
TWITTER_REDIRECT_URI = os.getenv("TWITTER_REDIRECT_URI", "http://127.0.0.1:5000/auth/twitter/callback")

# Reddit credentials
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")
REDDIT_REDIRECT_URI = os.getenv("REDDIT_REDIRECT_URI", "http://localhost:5000/auth/reddit/callback")

# Store user credentials (in a real app, use a secure database)
user_credentials = {}

# MongoDB connection
MONGODB_URI = "mongodb+srv://ankushraina24:Ankush2003@testsocialmedia.uuo8yht.mongodb.net/"
client = MongoClient(MONGODB_URI)
db = client['twitter_metrics']
tweets_collection = db['tweets']

# Twitter API credentials
TWITTER_API_KEY = os.getenv('TWITTER_API_KEY')
TWITTER_API_SECRET = os.getenv('TWITTER_API_SECRET')
TWITTER_BEARER_TOKEN = os.getenv('TWITTER_BEARER_TOKEN')

def get_twitter_client():
    client = tweepy.Client(
        bearer_token=TWITTER_BEARER_TOKEN,
        consumer_key=TWITTER_API_KEY,
        consumer_secret=TWITTER_API_SECRET,
        wait_on_rate_limit=True
    )
    return client

# Helper function for PKCE
def generate_code_verifier():
    token = secrets.token_urlsafe(100)
    return token[:128]

def generate_code_challenge(code_verifier):
    code_challenge = hashlib.sha256(code_verifier.encode('ascii')).digest()
    code_challenge = base64.urlsafe_b64encode(code_challenge).decode('ascii')
    return code_challenge.replace('=', '')

@app.route('/')
def landing_page():
    # Render the social media interface landing page
    return render_template('Social media interface/front_index.html')

@app.route('/main')
def main_app_index():
    linkedin_linked = 'linkedin' in user_credentials
    twitter_linked = 'twitter' in user_credentials
    reddit_linked = 'reddit' in user_credentials
    return render_template('index.html', 
                         linkedin_linked=linkedin_linked, 
                         twitter_linked=twitter_linked,
                         reddit_linked=reddit_linked)

@app.route('/link_accounts', methods=['GET', 'POST'])
def link_accounts():
    linkedin_linked = 'linkedin' in user_credentials
    twitter_linked = 'twitter' in user_credentials
    reddit_linked = 'reddit' in user_credentials
    linkedin_error = None
    twitter_error = None
    reddit_error = None

    if request.method == 'POST':
        if 'linkedin_link' in request.form:
            # Generate state and store in session
            state = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
            session['linkedin_state'] = state
            
            # LinkedIn OAuth URL
            scopes = "openid profile w_member_social email"
            auth_url = (
                f"https://www.linkedin.com/oauth/v2/authorization"
                f"?response_type=code"
                f"&client_id={LINKEDIN_CLIENT_ID}"
                f"&redirect_uri={LINKEDIN_REDIRECT_URI}"
                f"&scope={scopes}"
                f"&state={state}"
            )
            return redirect(auth_url)
            
        elif 'twitter_link' in request.form:
            # Generate PKCE code verifier and challenge
            code_verifier = generate_code_verifier()
            code_challenge = generate_code_challenge(code_verifier)
            
            # Store in session
            session['twitter_code_verifier'] = code_verifier
            
            # Generate state
            state = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
            session['twitter_state'] = state
            
            # Twitter OAuth 2.0 URL with PKCE
            scopes = ["tweet.read", "tweet.write", "users.read", "offline.access"]
            auth_url = (
                f"https://twitter.com/i/oauth2/authorize?"
                f"response_type=code&"
                f"client_id={TWITTER_CLIENT_ID}&"
                f"redirect_uri={TWITTER_REDIRECT_URI}&"
                f"scope={'%20'.join(scopes)}&"
                f"state={state}&"
                f"code_challenge={code_challenge}&"
                f"code_challenge_method=S256"
            )
            return redirect(auth_url)

        elif 'reddit_link' in request.form:
            state = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
            session['reddit_state'] = state

            scope = "submit identity"
            auth_url = (
                f"https://www.reddit.com/api/v1/authorize"
                f"?client_id={REDDIT_CLIENT_ID}"
                f"&response_type=code"
                f"&state={state}"
                f"&redirect_uri={REDDIT_REDIRECT_URI}"
                f"&duration=permanent"
                f"&scope={scope}"
                f"&prompt=login"
            )
            return redirect(auth_url)

    return render_template('link_accounts.html', 
                         linkedin_linked=linkedin_linked, 
                         twitter_linked=twitter_linked,
                         reddit_linked=reddit_linked,
                         linkedin_error=linkedin_error,
                         twitter_error=twitter_error,
                         reddit_error=reddit_error)

@app.route('/auth/linkedin/callback')
def linkedin_callback():
    code = request.args.get('code')
    state = request.args.get('state')
    error = request.args.get('error')
    error_description = request.args.get('error_description')

    if error:
        return redirect(url_for('link_accounts', error=f"LinkedIn error: {error_description}"))

    if not code or not state or state != session.get('linkedin_state'):
        return redirect(url_for('link_accounts', error="Invalid state or missing code"))

    try:
        # Exchange code for access token
        token_response = requests.post(
            "https://www.linkedin.com/oauth/v2/accessToken",
            data={
                'grant_type': 'authorization_code',
                'code': code,
                'redirect_uri': LINKEDIN_REDIRECT_URI,
                'client_id': LINKEDIN_CLIENT_ID,
                'client_secret': LINKEDIN_CLIENT_SECRET
            },
            headers={'Content-Type': 'application/x-www-form-urlencoded'}
        ).json()

        access_token = token_response.get('access_token')
        if not access_token:
            raise Exception("No access token received")

        # Store the access token
        user_credentials['linkedin'] = {'access_token': access_token}
        return redirect(url_for('link_accounts', success="LinkedIn account linked successfully!"))

    except Exception as e:
        return redirect(url_for('link_accounts', error=f"LinkedIn error: {str(e)}"))

@app.route('/auth/twitter/callback')
def twitter_callback():
    code = request.args.get('code')
    state = request.args.get('state')
    error = request.args.get('error')
    error_description = request.args.get('error_description')

    if error:
        return redirect(url_for('link_accounts', error=f"Twitter error: {error_description}"))

    if not code or not state or state != session.get('twitter_state'):
        return redirect(url_for('link_accounts', error="Invalid state or missing code"))

    try:
        # Exchange code for access token
        token_url = "https://api.twitter.com/2/oauth2/token"
        data = {
            'code': code,
            'grant_type': 'authorization_code',
            'client_id': TWITTER_CLIENT_ID,
            'redirect_uri': TWITTER_REDIRECT_URI,
            'code_verifier': session['twitter_code_verifier']
        }

        # Basic Auth header
        auth_string = f"{TWITTER_CLIENT_ID}:{TWITTER_CLIENT_SECRET}"
        auth_bytes = auth_string.encode('ascii')
        base64_auth = base64.b64encode(auth_bytes).decode('ascii')

        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Authorization': f'Basic {base64_auth}'
        }

        response = requests.post(token_url, data=data, headers=headers)
        response.raise_for_status()
        token_data = response.json()

        access_token = token_data.get('access_token')
        if not access_token:
            raise Exception("No access token received from Twitter")

        # Store the access token
        user_credentials['twitter'] = {'access_token': access_token}
        return redirect(url_for('link_accounts', success="Twitter account linked successfully!"))

    except Exception as e:
        return redirect(url_for('link_accounts', error=f"Twitter error: {str(e)}"))

@app.route('/auth/reddit/callback')
def reddit_callback():
    code = request.args.get('code')
    state = request.args.get('state')
    error = request.args.get('error')

    if error:
        return redirect(url_for('link_accounts', error=f"Reddit error: {error}"))

    if not code or not state or state != session.get('reddit_state'):
        return redirect(url_for('link_accounts', error="Invalid state or missing code"))

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

        # Store the access token
        user_credentials['reddit'] = {'access_token': access_token}
        return redirect(url_for('link_accounts', success="Reddit account linked successfully!"))

    except Exception as e:
        return redirect(url_for('link_accounts', error=f"Reddit error: {str(e)}"))

@app.route('/disconnect/reddit')
def disconnect_reddit():
    user_credentials.pop('reddit', None)
    # Optionally redirect to Reddit logout
    return redirect('https://www.reddit.com/logout')

@app.route('/post', methods=['GET', 'POST'])
def post():
    if request.method == 'POST':
        post_content = request.form['post_content']
        linkedin = 'linkedin' in request.form
        twitter = 'twitter' in request.form
        reddit = 'reddit' in request.form
        posting_errors = {}

        if linkedin:
            if 'linkedin' in user_credentials:
                try:
                    # Get user profile
                    profile_response = requests.get(
                        "https://api.linkedin.com/v2/userinfo",
                        headers={
                            'Authorization': f'Bearer {user_credentials["linkedin"]["access_token"]}',
                            'X-Restli-Protocol-Version': '2.0.0'
                        }
                    ).json()

                    user_urn = f"urn:li:person:{profile_response['sub']}"

                    # Post to LinkedIn
                    post_data = {
                        "author": user_urn,
                        "lifecycleState": "PUBLISHED",
                        "specificContent": {
                            "com.linkedin.ugc.ShareContent": {
                                "shareCommentary": {"text": post_content},
                                "shareMediaCategory": "NONE"
                            }
                        },
                        "visibility": {
                            "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
                        }
                    }

                    post_response = requests.post(
                        "https://api.linkedin.com/v2/ugcPosts",
                        headers={
                            'Authorization': f'Bearer {user_credentials["linkedin"]["access_token"]}',
                            'X-Restli-Protocol-Version': '2.0.0',
                            'Content-Type': 'application/json'
                        },
                        json=post_data
                    )
                    post_response.raise_for_status()
                except Exception as e:
                    posting_errors['linkedin'] = f"Error posting to LinkedIn: {str(e)}"
            else:
                posting_errors['linkedin'] = "LinkedIn account not linked"

        if twitter:
            if 'twitter' in user_credentials:
                try:
                    # Post to Twitter
                    tweet_url = "https://api.twitter.com/2/tweets"
                    tweet_data = {
                        "text": post_content
                    }

                    headers = {
                        'Authorization': f'Bearer {user_credentials["twitter"]["access_token"]}',
                        'Content-Type': 'application/json'
                    }

                    tweet_response = requests.post(tweet_url, json=tweet_data, headers=headers)
                    tweet_response.raise_for_status()
                except Exception as e:
                    posting_errors['twitter'] = f"Error posting to Twitter: {str(e)}"
            else:
                posting_errors['twitter'] = "Twitter account not linked"

        if reddit:
            if 'reddit' in user_credentials:
                try:
                    # Submit post to Reddit
                    submit_response = requests.post(
                        "https://oauth.reddit.com/api/submit",
                        headers={
                            'Authorization': f'bearer {user_credentials["reddit"]["access_token"]}',
                            'User-Agent': 'FlaskRedditBot/0.1'
                        },
                        data={
                            'sr': 'test',  # Default subreddit
                            'title': 'New Post',  # Default title
                            'text': post_content,
                            'kind': 'self'
                        }
                    ).json()

                    if 'error' in submit_response:
                        raise Exception(submit_response['error'])
                except Exception as e:
                    posting_errors['reddit'] = f"Error posting to Reddit: {str(e)}"
            else:
                posting_errors['reddit'] = "Reddit account not linked"

        return render_template('post_status.html', 
                             post_content=post_content, 
                             posting_errors=posting_errors,
                             linkedin_success=linkedin and 'linkedin' not in posting_errors,
                             twitter_success=twitter and 'twitter' not in posting_errors,
                             reddit_success=reddit and 'reddit' not in posting_errors)

    return render_template('post.html', 
                         linkedin_linked='linkedin' in user_credentials,
                         twitter_linked='twitter' in user_credentials,
                         reddit_linked='reddit' in user_credentials)

@app.route('/twitter_analysis')
def twitter_analysis():
    return render_template('analysis_index.html')

@app.route('/reddit_analysis')
def reddit_analysis():
    return render_template('reddit_dashboard.html')

@app.route('/get_metrics', methods=['POST'])
def get_metrics():
    username = request.form.get('username')
    if not username:
        return jsonify({'error': 'Username is required'}), 400

    try:
        client = get_twitter_client()
        
        # Get user ID from username
        user = client.get_user(username=username)
        if not user.data:
            return jsonify({'error': 'User not found'}), 404
            
        user_id = user.data.id
        
        # Get user's tweets - using minimum required max_results of 5
        tweets = client.get_users_tweets(
            id=user_id,
            max_results=5,
            tweet_fields=['public_metrics', 'created_at']
        )
        
        if not tweets.data:
            return jsonify({'error': 'No tweets found for this user'}), 404

        # Get metrics for all tweets
        all_tweets_metrics = []
        for tweet in tweets.data:
            metrics = {
                'username': username,
                'tweet_id': str(tweet.id),
                'text': tweet.text,
                'likes': tweet.public_metrics['like_count'],
                'comments': tweet.public_metrics['reply_count'],
                'created_at': tweet.created_at,
                'fetched_at': datetime.utcnow()
            }
            all_tweets_metrics.append(metrics)
            
            # Store in MongoDB
            tweets_collection.update_one(
                {'tweet_id': str(tweet.id)},
                {'$set': metrics},
                upsert=True
            )
        
        return jsonify({'tweets': all_tweets_metrics})
    except tweepy.TweepyException as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'Database error: {str(e)}'}), 500

@app.route('/analyze_sentiment', methods=['POST'])
def analyze_tweet_sentiment():
    try:
        data = request.get_json()
        text = data.get('text')
        likes = data.get('likes', 0)
        comments = data.get('comments', 0)
        
        sentiment, probabilities, engagement = analyze_sentiment(text, likes, comments)
        
        return jsonify({
            'sentiment': sentiment,
            'probabilities': {
                'negative': float(probabilities[0]),
                'positive': float(probabilities[1]),
                'neutral': float(probabilities[2]),
                'irrelevant': float(probabilities[3])
            },
            'engagement_score': float(engagement)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/fetch_posts', methods=['POST'])
def fetch_posts():
    try:
        linkedin_id = request.form.get('linkedin_id')

        # Initialize LinkedIn API client
        api = Linkedin("7889915624", "ankush@123")

        # Fetch profile posts
        posts = api.get_profile_posts(linkedin_id)
        top_posts = posts[:5]

        # Print the structure of the first post for debugging
        if top_posts:
            print(json.dumps(top_posts[0], indent=2))

        # Process and format the posts
        formatted_posts = []
        for post in top_posts:
            # Extract post content
            text = post.get('commentary', {}).get('text', {}).get('text', '')
            # Extract likes and comments
            likes = post.get('socialDetail', {}).get('totalSocialActivityCounts', {}).get('numLikes', 0)
            comments = post.get('socialDetail', {}).get('totalSocialActivityCounts', {}).get('numComments', 0)
            # Extract timestamp if available (not present in your sample, so leave blank or handle if found)
            timestamp = ''
            formatted_post = {
                'linkedin_id': linkedin_id,
                'text': text,
                'timestamp': timestamp,
                'likes': likes,
                'comments': comments
            }
            formatted_post.pop('_id', None)
            formatted_posts.append(formatted_post)

        # Store in MongoDB using the existing client
        db = client['testsocialmedia']
        collection = db['linkedin_posts']
        # Optionally, remove old posts for this user before inserting new ones
        collection.delete_many({'linkedin_id': linkedin_id})
        collection.insert_many(formatted_posts)

        # Remove _id from any posts in formatted_posts (if present)
        for post in formatted_posts:
            post.pop('_id', None)

        return jsonify({'success': True, 'posts': formatted_posts})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/analyze_sentiment_linkedin', methods=['POST'])
def analyze_sentiment_linkedin_posts():
    try:
        linkedin_id = request.form.get('linkedin_id')
        # Connect to MongoDB using the existing client
        db = client['testsocialmedia']
        collection = db['linkedin_posts']
        posts = list(collection.find({'linkedin_id': linkedin_id}))
        for post in posts:
            post.pop('_id', None)
        results = []
        for post in posts:
            text = post.get('text', '')
            likes = post.get('likes', 0)
            comments = post.get('comments', 0)
            sentiment, probabilities, engagement = analyze_sentiment(text, likes, comments)
            results.append({
                'text': text,
                'timestamp': post.get('timestamp', ''),
                'likes': likes,
                'comments': comments,
                'sentiment': sentiment,
                'confidence': {
                    'Negative': float(probabilities[0]),
                    'Positive': float(probabilities[1]),
                    'Neutral': float(probabilities[2]),
                    'Irrelevant': float(probabilities[3])
                },
                'engagement': engagement
            })
        return jsonify({'success': True, 'posts': results})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/linkedin_analysis')
def linkedin_analysis():
    return render_template('linkedin_analysis.html')

if __name__ == '__main__':
    app.run(debug=True)