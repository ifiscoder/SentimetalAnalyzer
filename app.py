import os
import tweepy as tw
import pandas as pd
import io
import re
import emoji
import nltk
import json
from nltk.corpus import stopwords
from textblob import Word, TextBlob
from cloudant.client import Cloudant
nltk.download('stopwords')
nltk.download('wordnet')
nltk.download('omw-1.4')
stop_words = stopwords.words('english')
from flask import Flask, render_template, request, Response

def clean_tweets(tweet):
    rm_rt = re.sub('RT\s+'," ",tweet)
    rm_at = re.sub('\B@\w+'," ",rm_rt)
    rm_hash = re.sub('\B#\w+'," ",rm_at)
    rm_emo = emoji.demojize(rm_hash)
    return rm_emo

def preprocess_tweets(tweet, custom_stopwords):
    preprocessed_tweet = tweet
    preprocessed_tweet.replace('[^\w\s]','')
    preprocessed_tweet = " ".join(word for word in preprocessed_tweet.split() if word not in stop_words)
    preprocessed_tweet = " ".join(word for word in preprocessed_tweet.split() if word not in custom_stopwords)
    preprocessed_tweet = " ".join(Word(word).lemmatize() for word in preprocessed_tweet.split())
    return(preprocessed_tweet)

def getAnalysis(score):
    if score < 0:
        return 'Negative'
    elif score == 0:
        return 'Neutral'
    else:
        return 'Positive'

# twitter creds
key = 'K6gd1YLuinBhwza3hsd4J0q8x'
secret = '64CLjWg5WlAz2FobRCNDUNhwLly06DeN5reTeI7qG64xtYrbYD'
access_token = '1505776500527988738-PLscmTb4lsnPlb18B84CHemOB3xoYl'
access_token_secret = 'SU7yC9BtKgrivpoCjrmms2zYyI2NBMya02zPKbRotnZNa'

# Authentication
auth = tw.OAuthHandler(key,secret)
auth.set_access_token(access_token,access_token_secret)
api = tw.API(auth, wait_on_rate_limit=True)

def sentiment_analyzer(hashtag, limit):
    query = tw.Cursor(api.search_tweets, q=hashtag).items(limit)
    tweets = [{'Tweets':tweet.text, 'Timestamp':tweet.created_at} for tweet in query]
    df = pd.DataFrame.from_dict(tweets)
    custom_stopwords = ['RT', hashtag]
    cleaned_tweets = df['Tweets'].apply(lambda x:clean_tweets(x))
    df['Cleaned/Preprocessed Tweet'] = cleaned_tweets.apply(lambda x:preprocess_tweets(x,custom_stopwords))
    df['polarity'] = df['Cleaned/Preprocessed Tweet'].apply(lambda x:TextBlob(x).sentiment[0])
    df['subjectivity'] = df['Cleaned/Preprocessed Tweet'].apply(lambda x:TextBlob(x).sentiment[1])
    df['sentiment'] = df['polarity'].apply(getAnalysis)
    return df

app = Flask(__name__,static_url_path='')
port = int(os.getenv('PORT', 8000))

@app.route('/')
def home():
    return render_template("index.html")

@app.route('/result', methods=["POST", "GET"])
def result():
    if request.method == "POST":
        hashtag=request.form['hashtag']
        limit=request.form['limit']
        yes_or_no=request.form['yesno']
        data = sentiment_analyzer(hashtag,int(limit))
        conf = ""
        if yes_or_no == "yes":
            # cloudant creds
            serviceUsername = "apikey-v2-169qb0zw2y9tierpovrxm8i044etwvmm5pwdus2d9k90"
            servicePassword = "b48741742c768b83b0c625b84bbca3d3"
            serviceURL = "https://apikey-v2-169qb0zw2y9tierpovrxm8i044etwvmm5pwdus2d9k90:b48741742c768b83b0c625b84bbca3d3@b545a08b-2796-4479-8e6d-f52bf1054559-bluemix.cloudantnosqldb.appdomain.cloud"

            client = Cloudant(serviceUsername, servicePassword, url=serviceURL)
            client.connect()

            databaseName = 'tweet-hash-analysis'
            myDatabaseDemo = client.create_database(databaseName)
            if myDatabaseDemo.exists():
                print("'{0}' successfully created.\n".format(databaseName))

            df_to_cloud = data.to_json(orient = 'records')
            data_obj = json.loads(df_to_cloud)
            for i in data_obj:
                newDocument = myDatabaseDemo.create_document(i)
            if newDocument.exists():
                print("Document '{0}' successfully created.")
            conf = "Data successfully stored to cloudant."
    return render_template('results.html', conf=conf, title = "Sentiment Results", sentiments = data['sentiment'].value_counts(0), hashtag=""+request.form['hashtag'], limit="No. of records:- "+request.form['limit'], tables=[data.to_html(classes='table table-stripped')],titles=[''])

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=port, debug=True)