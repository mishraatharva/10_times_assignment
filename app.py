#-------------------------------------------------------------------------------- IMPORT STATEMENTS -------------------------------------------------------------------------------#
import requests
from bs4 import BeautifulSoup
from csv import DictWriter
import re
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer
import spacy
import logging
from celery import Celery
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import sessionmaker, relationship, declarative_base
import pandas as pd
import numpy as np
import datetime
from dateutil import parser

#-------------------------------------------------------------------------------- IMPORTANT SETUP -------------------------------------------------------------------------------#

nlp  = spacy.load("en_core_web_sm")
logging.basicConfig(filename='news_classification.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# DATABASE_URL = "mysql+mysqlclient://root:toor@localhost/timesdb"
DATABASE_URL = "mysql+pymysql://root:toor@localhost/timesdb123"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Article(Base):
    __tablename__ = 'articles'

    id = Column(Integer, primary_key=True)
    title = Column(String(1000))
    description = Column(String(1000))
    pubDate = Column(DateTime, default=datetime.datetime.utcnow)
    category = Column(String(255))

dataframe = pd.DataFrame(columns=['title', 'description','pubDate','category'])

#-------------------------------------------------------------------------------- ACHYCRONUS TASK -------------------------------------------------------------------------------#
app = Celery('tasks', broker='redis://localhost:6379/0')
@app.task
def sort_data(cleaned_data):
    logger.info("celery task started")
    categories = []
    global dataframe
    for data in cleaned_data:
        doc = nlp(data['description']) if data['description'] else None
        logger.info(doc)
        if doc:
            for token in doc:
                if token.text in ["terrorism", "protest", "political unrest", "riot"]:
                    categories.append("Terrorism/Protest/Political Unrest/Riot")
                elif token.text.lower() in ["positive", "uplifting"]:
                    categories.append("Positive/Uplifting")
                elif token.text.lower() in ["natural", "disaster"]:
                    categories.append("Natural Disasters")

            if not categories:
                categories.append("Others")
            data['category'] = ', '.join(categories)
            categories = []
            logger.info(data)
        
        random_indices = np.random.choice(1, size=1, replace=False)
        temp_df = pd.DataFrame(data,index=random_indices)
        
        dataframe = pd.concat([dataframe,temp_df], ignore_index=True)
        dataframe = dataframe.sort_values(by=['category'], ascending=False)

#-------------------------------------------------------------------------------- DATA CLEANING -------------------------------------------------------------------------------#

class data_cleaning():
    def __init__(self):
        self.field_names = ['title', 'description','pubDate']
        self.stop_words = set(stopwords.words('english'))
        self.lemmatizer = WordNetLemmatizer()
        
    def clean_text(self,text):
        text = text.lower()
        text = re.sub('"','', text)
        text = re.sub("[^a-zA-Z]", " ", text)
        tokens = [self.lemmatizer.lemmatize(w) for w in text.split() if not w in self.stop_words]
        text = " ".join(tokens).strip()
        return text

    def perform_cleaning(self,datas):
        logger.info("data cleaning started")
        for data in datas:
            data['title'] = self.clean_text(data['title']) if data['title'] is not None else None
            data['description'] = self.clean_text(data['description']) if data['description'] is not None else None
            data['pubDate'] = parser.parse(data['pubDate']) if data['pubDate'] is not None else None
        
        return datas

#-------------------------------------------------------------------------------- DATA CREATION -------------------------------------------------------------------------------#

class data_creation():
    def __init__(self,urls):
        self.urls = urls
        self.data_cleaning = data_cleaning()

    def create_data(self):
        logger.info("data creation started")
        for url in self.urls:
            try:
                response = requests.get(url)
                response.raise_for_status()  # Raise an error for bad responses (4xx, 5xx)
                soup = BeautifulSoup(response.content, 'xml')
                items = soup.find_all('item')
                data = [
                    {
                        'title': item.find('title').text if item.find('title') else None,
                        'description': item.find('description').text if item.find('description') else None,
                        'pubDate': item.find('pubDate').text if item.find('pubDate') else None
                    }
                    for item in items
                ]
                cleaned_data = self.data_cleaning.perform_cleaning(data)
                sort_data(cleaned_data)
            except requests.exceptions.RequestException as e:
                logger.error(f"Failed to retrieve {url}: {e}")

#------------------------------------------------------------------------------ SCRIPT STARTING POINT --------------------------------------------------------------------------#

if __name__ == "__main__":
    urls = ['http://rss.cnn.com/rss/cnn_topstories.rss','http://qz.com/feed', 'http://feeds.foxnews.com/foxnews/politics', 
            'http://feeds.reuters.com/reuters/businessNews', 'http://feeds.feedburner.com/NewshourWorld', 'https://feeds.bbci.co.uk/news/world/asia/india/rss.xml']
    dc_obj = data_creation(urls)
    dc_obj.create_data()
    # dataframe.to_csv("final_data.csv")
    
    Base.metadata.create_all(engine)
    logger.info("required table created.")

    Session = sessionmaker(bind=engine)
    session = Session()


    # df = pd.read_csv(r'U:\assignments\10_times\final_data.csv')
    dataframe.to_sql('articles', con=engine, if_exists='append', index=False)
    logger.info("ALL DATA GET SAVED TO MYSQL_DB IN SORTED ORDER!!")