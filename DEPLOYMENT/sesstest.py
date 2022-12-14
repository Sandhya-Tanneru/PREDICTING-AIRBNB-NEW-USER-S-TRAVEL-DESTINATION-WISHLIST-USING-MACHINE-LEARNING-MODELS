# -*- coding: utf-8 -*-
"""Deployment.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1eXIN0IWof-OUyC-tS_S6SdfCEErB4Vj0
"""

#Importing necessary Python Libraries.
import sys
import os
cwd = os.getcwd()
sys.path.append(cwd)

import warnings
warnings.filterwarnings("ignore")

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import math
import ast
import pickle
from tqdm import tqdm
from scipy import sparse
from scipy.sparse import hstack
import statistics as st

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn import preprocessing
from sklearn.preprocessing import LabelEncoder
from sklearn.neighbors import KNeighborsClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier
from xgboost import XGBClassifier
import tokenizers

from flask import Flask, jsonify, request
import joblib

"""**USER DEFINED FUNCTIONS**"""

import flask
app = Flask(__name__)

########################################################################################

#Function for creating age-buckets from age feature:

def age_buckets(feature):
  """
  Function that returns 0 for age group (19 - 39)
                        1 for age group (39 - 59)
                        2 for age group above 59
  """
  if feature >=19 and feature <=39:
    return 0
  elif feature >=40 and feature<=59:
    return 1
  else: 
    return 2
            

#Function that converts string to a list:

def string_to_list(feature):
  
  """ Function that converts a string into a list """
  
  if (feature == ''):
    feature = ''
  elif (feature == 0.0):
    feature = 0.0
  else:
    feature = ast.literal_eval(feature)
  return feature


#Functions for Creating New features in Sessions dataset - Action Summary Feature:

def action_summary(feature1,feature2):
  
  """ FUNCTION THAT TAKES ACTION AND SECS_ELAPSED AS INPUTS CORRESPONDING TO EACH USER AND 
      RETURNS A DICTIONARY WITH KEY AS THE ACTION SUBCATEGORIES AND 
      MEDIAN TIME SPENT BY USER IN PERFORMING THE ACTION SUBCATEGORY """
  
  if (feature1 == ''):
    return 0.0

  else:
    input_list = list(zip(feature1,feature2))
    dict_time = dict()  
    for feature,time in input_list:
        dict_time.setdefault(feature, []).append(time)
    for k,v in dict_time.items():
      dict_time[k] = st.median(v)
    return dict_time

# Functions for processing old features in Sessions dataset:

def convert_tostring(lists):

  """ FUNCTION THAT CONVERTS A ELEMENTS IN A LIST INTO A STRING OF VALUES SEPARATED BY COMMA """

  _string = [str(i) for i in lists]
  _string = ','.join(lists)
  return _string

def total_time_secs(lists):

  """ FUNCTION THAT TAKES LIST OF TIME IN SECONDS VALUES AND SUM THEM UP"""
  if (lists == 0.0):
    time_secs = lists
  else:
    lists = [float(i) for i in lists]
    time_secs = sum(lists)
  return time_secs

#Loading the file that contains the fitted TF-IDF vectorizer:
vectorizer_tfidf=joblib.load('vectorizer_tfidf.pkl')


#Storing the tf-idf feature names into a variable:
important_words = vectorizer_tfidf.get_feature_names()


#Removing the redundant words from the activity column and reframing the string with important actions:
def removing_redundant_words(feature):
  """
  Function that removes the redundant actions from the strings in activity column
  
  """
  if (len(feature)==0):
    feature = ''
  else:
    feature = feature.split(',')
    L = []
    for i in important_words:
      for k in feature:
        if (k==i):
          L.append(i)
    feature = ','.join(L)
  return feature


#Functions for Creating New features in Sessions dataset - Useful Activity level:

def useful_activity_rating(feature1,feature2):
  """
  Function that returns useful activity level ie., (No.of Useful actions performed/Total number of actions performed)

  """
  x1 = len(feature1.split(','))
  if (feature2 == 0):
    return 0.000
  else:
    return np.round((x1/feature2),3)

"""**LOADING TRAINED MODELS**"""

#Loading the file that contains standardizer fitted on secs elapsed feature:
scaler_secs = joblib.load('scaler_secs.pkl')

#Loading the file that contains standardizer fitted on time lag in seconds:
scaler_timelag = joblib.load('scaler_timelag.pkl')

#Loading the file that contains Trained XG Boost Model:
model = joblib.load('Final_model.pkl')

#Loading the file that contains Label encoder fitted on country destination feature:
label_enc = joblib.load('label_enc.pkl')

"""**LOADING SAMPLES TEST SET OF SIZE 150 FROM 62096 AND CLEANED SESSIONS DATA AS WELL**"""

test_samples = joblib.load('test_sample.pkl')
sessions_dataset = joblib.load('session_details.pkl')
session_ids = sessions_dataset.user_id.tolist()

"""**VALUES FROM THE TRAIN SET FOR TREATING NULL VALUES AND PROCESSING THE DATA IN TEST SET**"""

age_median = 34
train_first_affiliate_tracked_mode = 'untracked'
No_browsers = joblib.load('first_browser.pkl')
features = joblib.load('ohe_list.pkl')
cat_vars = joblib.load('categorical_vars.pkl')

# https://www.tutorialspoint.com/flask

@app.route('/')
def hello_world():
    return 'Hello World!'


@app.route('/index')
def index():
    return flask.render_template('index.html')


@app.route('/predict', methods=['POST'])
def predict():
    results = dict()
    to_predict_list = request.form.to_dict()
    User_ids = to_predict_list['id'].split(',')
    for user in User_ids:
      X = test_samples.loc[test_samples.id == user].squeeze()
      X.drop(['date_first_booking','language'],inplace=True)
    
      if (X.first_browser in No_browsers):
        X.first_browser
      else:
        X.first_browser = 'Others'
      
      if ((X.age > 1900) & (X.age <2014)):
        X.age = 2014 - X.age
      elif ((X.age < 19) & (X.age >105)):
        X.age = age_median
      elif (math.isnan(X.age)):
        X.age = age_median
      
      if not (isinstance(X.first_affiliate_tracked,str)):
        X.first_affiliate_tracked = train_first_affiliate_tracked_mode
      
      X.date_account_created = pd.to_datetime(X.date_account_created)
      X.timestamp_first_active = pd.to_datetime(X.timestamp_first_active, format='%Y%m%d%H%M%S')

      month_account_created = X.date_account_created.month
      DayOfWeek_account_created = X.date_account_created.weekday()
      year_account_created = X.date_account_created.year
      time_lag = (X.timestamp_first_active - X.date_account_created).total_seconds()
      age_bucket = age_buckets(X.age)

      if (X.id in session_ids):
        ind = sessions_dataset[sessions_dataset.user_id == X.id].index[0]
        R = sessions_dataset.loc[ind]
        activity = string_to_list(R.activity)
        secs_elapsed = string_to_list(R.secs_elapsed)
      else:
        activity = ''
        secs_elapsed = 0.0
      
      test_action_summary = action_summary(activity,secs_elapsed)
      test_actions_count = len(activity)
      activity = removing_redundant_words(convert_tostring(activity))
      secs_elapsed = total_time_secs(secs_elapsed)
      test_session_useful_activity_rating = np.array(useful_activity_rating(activity,test_actions_count)).reshape(-1,1)
      test_session_age = np.array(X.age).reshape(-1,1)
      test_session_flow = np.array(X.signup_flow).reshape(-1,1)
      test_session_create_day = np.array(DayOfWeek_account_created).reshape(-1,1)
      test_session_create_month = np.array(month_account_created).reshape(-1,1)
      test_session_create_year = np.array(year_account_created).reshape(-1,1)
      test_session_age_bucket = np.array(age_bucket).reshape(-1,1)
      test_session_actions_count = np.array(test_actions_count).reshape(-1,1)
      
        
      ohe_df = pd.DataFrame(columns = features)
      ohe_df.loc[0] = np.zeros(len(features))
      for feature in cat_vars:
        V = pd.get_dummies(X[feature], prefix = feature).columns[0]
        if (V in features):
          ohe_df[pd.get_dummies(X[feature], prefix = feature).columns[0]] = 1.0
      
      
      test_vectorizer_tfidf = vectorizer_tfidf.transform([activity]).toarray()
      
      

      test_session_secs = scaler_secs.transform(np.array(secs_elapsed).reshape(-1,1))
      
      
      test_session_time_lag = scaler_timelag.transform(np.array(time_lag).reshape(-1,1))
        
      X_te = sparse.csr_matrix(np.hstack((ohe_df.to_numpy(),test_vectorizer_tfidf,test_session_secs,test_session_time_lag,test_session_age, test_session_flow,test_session_create_day,\
                                          test_session_create_month,test_session_create_year,test_session_useful_activity_rating,test_session_age_bucket,test_session_actions_count)))

      probabilities = model.predict_proba(X_te)

      for i in range(len(probabilities)):
        y_labels = label_enc.inverse_transform(np.argsort(probabilities[i])[::-1])[:5].tolist()
      
      results[user] = y_labels

    return jsonify(results)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)