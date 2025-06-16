from flask import Flask, redirect, request, session, url_for, render_template
import praw
import os
from dotenv import load_dotenv
from collections import Counter
from datetime import datetime
from pymongo import MongoClient
import sys
sys.path.append('twitter_dataset')
from twitter_dataset.twitter_sentiment_analysis import analyze_sentiment
from bson import ObjectId
import nltk

# Load environment variables
load_dotenv()

# Debug: Print environment variables to verify they are loaded
print("Environment Variables:")
print(f"REDDIT_CLIENT_ID: {os.getenv('REDDIT_CLIENT_ID')}")
print(f"REDDIT_CLIENT_SECRET: {os.getenv('REDDIT_CLIENT_SECRET')}")
print(f"REDDIT_REDIRECT_URI: {os.getenv('REDDIT_REDIRECT_URI')}")

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")

# Reddit API credentials
CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDDIT_REDIRECT_URI")

# Verify credentials are set
if not all([CLIENT_ID, CLIENT_SECRET, REDIRECT_URI]):
    raise ValueError("Missing required Reddit API credentials. Please check your .env file.")

# MongoDB connection
MONGO_URI = "mongodb+srv://ankushraina24:Ankush2003@testsocialmedia.uuo8yht.mongodb.net/"
client = MongoClient(MONGO_URI)
db = client['Reddit_data']  # Replace 'socialmedia' with your actual database name
reddit_collection = db["Reddit-analysic"]

# Step 1: Home Page
@app.route('/')
def index():
    return redirect(url_for('login'))


# Step 2: Redirect to Reddit login
@app.route('/login')
def login():
    reddit = praw.Reddit(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        redirect_uri=REDIRECT_URI,
        user_agent="OAuthRedditAnalytics/0.1"
    )
    auth_url = reddit.auth.url(["identity", "history", "read"], "random_state", "permanent")
    return redirect(auth_url)


# Step 3: Handle Reddit callback
@app.route('/auth/reddit/callback')
def authorized():
    code = request.args.get("code")
    if not code:
        return "Authorization failed", 400

    reddit = praw.Reddit(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        redirect_uri=REDIRECT_URI,
        user_agent="OAuthRedditAnalytics/0.1"
    )

    refresh_token = reddit.auth.authorize(code)
    session['refresh_token'] = refresh_token
    return redirect(url_for('reddiit_dashboard'))


# Step 4: Show Dashboard with Analytics
@app.route('/reddiit_dashboard', methods=['GET'])
def reddiit_dashboard():
    if 'refresh_token' not in session:
        return redirect(url_for('index'))

    reddit = praw.Reddit(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        redirect_uri=REDIRECT_URI,
        user_agent="OAuthRedditAnalytics/0.1",
        refresh_token=session['refresh_token']
    )

    # Get username from query string or use logged-in user
    username = request.args.get('username')
    if username:
        redditor = reddit.redditor(username)
    else:
        redditor = reddit.user.me()
        username = redditor.name

    # Fetch submissions for the user
    submissions = list(redditor.submissions.new(limit=50))  # Fetch more to get top 5

    # Sort by score and get top 6
    top_posts = sorted(submissions, key=lambda s: s.score, reverse=True)[:6]

    posts_with_comments = []
    total_likes = 0
    total_comments = 0
    for post in top_posts:
        post.comments.replace_more(limit=0)
        comments = post.comments.list()[:5]  # Top 5 comments
        post_data = {
            "title": post.title,
            "subreddit": str(post.subreddit),
            "score": post.score,
            "url": post.url,
            "permalink": f"https://reddit.com{post.permalink}",
            "content": post.selftext,
            "created_utc": post.created_utc,
            "comments": [{"body": c.body, "score": c.score} for c in comments]
        }
        posts_with_comments.append(post_data)
        total_likes += post.score
        total_comments += len(comments)

        # Store in MongoDB and get the document ID
        result = reddit_collection.insert_one({
            "user": username,
            "title": post_data["title"],
            "subreddit": post_data["subreddit"],
            "content": post_data["content"],
            "likes": post_data["score"],
            "permalink": post_data["permalink"],
            "comments": post_data["comments"],
            "num_comments": len(post_data["comments"]),
            "created_utc": post_data["created_utc"]
        })
        # Add the MongoDB document ID to the post data
        post_data["_id"] = str(result.inserted_id)

    return render_template("reddiit_dashboard.html", username=username, posts=posts_with_comments, total_likes=total_likes, total_comments=total_comments)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))


@app.template_filter('datetimeformat')
def datetimeformat(value):
    try:
        return datetime.utcfromtimestamp(float(value)).strftime('%Y-%m-%d %H:%M')
    except Exception:
        return value


@app.route('/analyze_sentiment/<post_id>')
def analyze_post_sentiment(post_id):
    if 'refresh_token' not in session:
        return redirect(url_for('index'))

    # Convert post_id to ObjectId
    try:
        obj_id = ObjectId(post_id)
    except Exception:
        return "Invalid post ID", 400

    # Get the post from MongoDB
    post = reddit_collection.find_one({"_id": obj_id})
    if not post:
        return "Post not found", 404

    # Analyze sentiment
    sentiment, probabilities, engagement = analyze_sentiment(
        post['content'],
        post['likes'],
        post['num_comments']
    )

    return render_template(
        "sentiment_results.html",
        post=post,
        sentiment=sentiment,
        probabilities=probabilities,
        engagement=engagement
    )


if __name__ == '__main__':
    app.run(debug=True,port=5001)

# Download NLTK data
nltk.download('punkt')
nltk.download('stopwords')
nltk.download('wordnet')
