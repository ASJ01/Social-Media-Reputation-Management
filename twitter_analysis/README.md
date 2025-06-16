# Twitter Metrics Dashboard

A Flask-based web application that displays the number of likes and comments on a Twitter user's most recent post.

## Features

- Enter any Twitter username to view metrics
- Displays likes and comments count for the most recent tweet
- Shows the tweet text
- Modern and responsive UI

## Setup

1. Install the required dependencies:
```bash
pip install -r requirements.txt
```

2. Create a `.env` file in the project root with your Twitter API credentials:
```
TWITTER_API_KEY=your_api_key
TWITTER_API_SECRET=your_api_secret
TWITTER_ACCESS_TOKEN=your_access_token
TWITTER_ACCESS_TOKEN_SECRET=your_access_token_secret
```

To get these credentials:
1. Go to the [Twitter Developer Portal](https://developer.twitter.com/en/portal/dashboard)
2. Create a new project and app
3. Generate the necessary API keys and tokens

## Running the Application

1. Make sure you have all the dependencies installed and the `.env` file set up
2. Run the Flask application:
```bash
python app.py
```
3. Open your browser and navigate to `http://localhost:5000`

## Usage

1. Enter a Twitter username in the input field
2. Click "Get Metrics" to fetch the data
3. View the likes and comments count for the most recent tweet
4. The tweet text will be displayed below the metrics 