
import pandas as pd
import re
import matplotlib.pyplot as plt
import seaborn as sns
from tabulate import tabulate
import gensim
import numpy as np
from gensim.models.word2vec import Word2Vec
import struct
from collections import Counter, defaultdict
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.naive_bayes import BernoulliNB, MultinomialNB
from sklearn.svm import SVC
from sklearn.pipeline import Pipeline
from sklearn.metrics import accuracy_score
from sklearn.metrics import f1_score
from sklearn.metrics import precision_score
from gensim.models import KeyedVectors
import os
from bs4 import BeautifulSoup
from sklearn.model_selection import train_test_split
from TfidfEmbeddingVectorizer import *
from MeanEmbeddingVectorizer import *

TRAIN_SET_PATH = "r8-train-no-stop.txt"
GLOVE_6B_50D_PATH = "glove.6B.50d.txt"
GLOVE_840B_300D_PATH = "glove.840B.300d.txt"
encoding="utf-8"


def loadDataset(file):
    X, y = [], []
    with open(TRAIN_SET_PATH) as infile:
        for line in infile:
            label, text = line.split("\t")
            X.append((text.split()))
            y.append(label)
    return np.array(X), np.array(y)

def loadDataset_Review(file):
    X, y = [], []
    for index,line in file.iterrows():

        review_text = BeautifulSoup(line["review"], "html.parser").get_text()
        #
        # 2. Remove caractéres não alfa-numéricos
        review_text = re.sub("[^a-zA-Z]", " ", review_text).lower()
        review_text = [w for w in review_text.split() if len(w) > 2]
        label, text = line['sentiment'], review_text
        X.append((text))
        y.append(label)
    return np.array(X), np.array(y)



def loadGloveSmall(GLOVE,X):
    glove_small = {}
    all_words = set(w for words in X for w in words)
    with open(GLOVE, "rb") as infile:
        for line in infile:
            parts = line.split()
            word = parts[0].decode(encoding)
            if (word in all_words):
                nums = np.array(parts[1:], dtype=np.float32)
                glove_small[word] = nums

def loadGloveBig(GLOVE,X,all_words):
    glove_big = {}
    with open(GLOVE, "rb") as infile:
        for line in infile:
            parts = line.split()
            word = parts[0].decode(encoding)
            if word in all_words:
                nums = np.array(parts[1:], dtype=np.float32)
                glove_big[word] = nums


def main():
    train = pd.read_csv(os.path.join(os.path.dirname(__file__),'labeledTrainData.tsv'),
                        header=0,delimiter="\t", quoting=3)

    X_w2v, y_w2v = loadDataset_Review(train)

    train, test = train_test_split(train, train_size=0.7, random_state=42)

    X,y = loadDataset_Review(train)

    X_test,y_test = loadDataset_Review(test)

    #X,y = loadDataset(TRAIN_SET_PATH)
    print(X_w2v)


    print("Total de exemplos carregados %s" % len(y))
    all_words = set(w for words in X_w2v for w in words)
    print(len(all_words))
    #glove_small = loadGloveSmall(GLOVE_6B_50D_PATH,X)
    #glove_big = loadGloveBig(GLOVE_840B_300D_PATH,X,all_words)

    # train word2vec on all the texts - both training and test set
    # we're not using test labels, just texts so this is fine
    #model = Word2Vec(X, size=100, window=5, min_count=5, workers=2)

    # Configura valores para o word2vec
    num_features = 100  # Word vector dimensionality
    min_word_count = 40  # Minimum word count
    num_workers = 4  # Number of threads to run in parallel
    context = 10  # Context window size
    downsampling = 1e-3  # Downsample setting for frequent words

    model = gensim.models.Word2Vec(X_w2v, workers=num_workers, \
                     size=num_features, min_count=min_word_count, \
                     window=context, sample=downsampling, seed=1)

    w2v = dict(zip(model.wv.index2word, model.wv.syn0))

    model_name = "100features_40minwords_10context"
    model.save(model_name)



    #model = KeyedVectors.load_word2vec_format('GoogleNews-vectors-negative300.bin', binary=True)
    #w2v = {w: vec for w, vec in zip(model.wv.index2word, model.wv.syn0)}

    # start with the classics - naive bayes of the multinomial and bernoulli varieties
    # with either pure counts or tfidf features
    mult_nb = Pipeline(
        [("count_vectorizer", CountVectorizer(analyzer=lambda x: x)), ("multinomial nb", MultinomialNB())])
    bern_nb = Pipeline([("count_vectorizer", CountVectorizer(analyzer=lambda x: x)), ("bernoulli nb", BernoulliNB())])
    mult_nb_tfidf = Pipeline(
        [("tfidf_vectorizer", TfidfVectorizer(analyzer=lambda x: x)), ("multinomial nb", MultinomialNB())])
    bern_nb_tfidf = Pipeline(
        [("tfidf_vectorizer", TfidfVectorizer(analyzer=lambda x: x)), ("bernoulli nb", BernoulliNB())])
    # SVM - which is supposed to be more or less state of the art
    # http://www.cs.cornell.edu/people/tj/publications/joachims_98a.pdf
    svc = Pipeline([("count_vectorizer", CountVectorizer(analyzer=lambda x: x)), ("linear svc", SVC(kernel="linear"))])
    svc_tfidf = Pipeline(
        [("tfidf_vectorizer", TfidfVectorizer(analyzer=lambda x: x)), ("linear svc", SVC(kernel="linear"))])

    # Extra Trees classifier is almost universally great, let's stack it with our embeddings
    etree_glove_small = Pipeline([("glove vectorizer", MeanEmbeddingVectorizer(w2v)),
                                  ("extra trees", ExtraTreesClassifier(n_estimators=200))])
    etree_glove_small_tfidf = Pipeline([("glove vectorizer", TfidfEmbeddingVectorizer(w2v)),
                                        ("extra trees", ExtraTreesClassifier(n_estimators=200))])
    etree_glove_big = Pipeline([("glove vectorizer", MeanEmbeddingVectorizer(w2v)),
                                ("extra trees", ExtraTreesClassifier(n_estimators=200))])
    etree_glove_big_tfidf = Pipeline([("glove vectorizer", TfidfEmbeddingVectorizer(w2v)),
                                      ("extra trees", ExtraTreesClassifier(n_estimators=200))])

    etree_w2v = Pipeline([("word2vec vectorizer", MeanEmbeddingVectorizer(w2v)),
                          ("extra trees", ExtraTreesClassifier(n_estimators=200))])
    etree_w2v_tfidf = Pipeline([("word2vec vectorizer", TfidfEmbeddingVectorizer(w2v)),
                                ("extra trees", ExtraTreesClassifier(n_estimators=200))])

    all_models = [
        ("mult_nb", mult_nb),
        ("mult_nb_tfidf", mult_nb_tfidf),
        ("bern_nb", bern_nb),
        ("bern_nb_tfidf", bern_nb_tfidf),
        ("svc", svc),
        ("svc_tfidf", svc_tfidf),
        ("w2v", etree_w2v),
        ("w2v_tfidf", etree_w2v_tfidf),
        ("glove_small", etree_glove_small),
        ("glove_small_tfidf", etree_glove_small_tfidf),
        ("glove_big", etree_glove_big),
        ("glove_big_tfidf", etree_glove_big_tfidf),

    ]
    unsorted_scores = []
    for name, model in all_models:
        print("Training with ", name)
        unsorted_scores.append((name,accuracy_score(y_test, model.fit(X,y).predict(X_test))))


    #unsorted_scores = [(name, accuracy_score(list(test['sentiment']), model.fit(X,y))) for name, model in all_models]

    #unsorted_scores = [(name, cross_val_score(model, X, y, cv=5).mean()) for name, model in all_models]
    scores = sorted(unsorted_scores, key=lambda x: -x[1])

    print(tabulate(scores, floatfmt=".4f", headers=("model", 'Accuracy')))

    plt.figure(figsize=(15, 6))
    sns.barplot(x=[name for name, _ in scores], y=[score for _, score in scores])




if __name__ == "__main__":
    main()