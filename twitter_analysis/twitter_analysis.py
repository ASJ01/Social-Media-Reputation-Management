from flask import Flask, render_template, request, jsonify
import tweepy
import os
from dotenv import load_dotenv
from pymongo import MongoClient
from datetime import datetime

app = Flask(__name__)
load_dotenv()

# Twitter API credentials
TWITTER_API_KEY = os.getenv('TWITTER_API_KEY')
TWITTER_API_SECRET = os.getenv('TWITTER_API_SECRET')
TWITTER_BEARER_TOKEN = os.getenv('TWITTER_BEARER_TOKEN')

# MongoDB connection
MONGODB_URI = "mongodb+srv://ankushraina24:Ankush2003@testsocialmedia.uuo8yht.mongodb.net/"
client = MongoClient(MONGODB_URI)
db = client['twitter_metrics']
tweets_collection = db['tweets']

def get_twitter_client():
    client = tweepy.Client(
        bearer_token=TWITTER_BEARER_TOKEN,
        consumer_key=TWITTER_API_KEY,
        consumer_secret=TWITTER_API_SECRET,
        wait_on_rate_limit=True
    )
    return client

@app.route('/')
def home():
    return render_template('index.html')

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

if __name__ == '__main__':
    app.run(debug=True) 