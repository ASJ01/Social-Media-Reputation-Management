from flask import Flask, render_template, request, jsonify
import requests
import json
from linkedin_api import Linkedin
from pymongo import MongoClient
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'twitter_dataset'))
from twitter_sentiment_analysis import analyze_sentiment
import pandas as pd

app = Flask(__name__)

# LinkedIn API credentials
CLIENT_ID = "86ngkdddkdwle2"
CLIENT_SECRET = "WPL_AP1.M0AzOnMhmhprYA3u.aymY2w=="

@app.route('/')
def index():
    return render_template('index.html')

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
        
        # Store in MongoDB
        client = MongoClient('mongodb+srv://ankushraina24:Ankush2003@testsocialmedia.uuo8yht.mongodb.net/')
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

@app.route('/analyze_sentiment', methods=['POST'])
def analyze_sentiment_posts():
    try:
        linkedin_id = request.form.get('linkedin_id')
        # Connect to MongoDB
        client = MongoClient('mongodb+srv://ankushraina24:Ankush2003@testsocialmedia.uuo8yht.mongodb.net/')
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

if __name__ == '__main__':
    app.run(debug=True) 