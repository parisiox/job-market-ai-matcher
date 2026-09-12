
from pathlib import Path
import json
from spacy.lang.en.stop_words import STOP_WORDS as en_stopwords
from spacy.lang.de.stop_words import STOP_WORDS as de_stopwords
import re
from sklearn.feature_extraction.text import TfidfVectorizer


def summarize_data(data):
    try:
        with open(f"{Path(__file__).parent}/{data}", "r", encoding="utf-8") as f:
            postings = json.loads(f.read())
            descriptions = []

            for posting in postings:
                try:
                    if posting["description"] != None:
                        descriptions.append(posting["description"].lower())
                except KeyError:
                    pass
    except json.decoder.JSONDecodeError:
        print("file contains invalid JSON")
        return

    vectorizer = TfidfVectorizer(stop_words=list(en_stopwords | de_stopwords), token_pattern=r"\w{2,}(?:[:-]\w+)?", min_df=3)
    matrix = vectorizer.fit_transform(descriptions)
    terms = vectorizer.get_feature_names_out()
    non_zero_count = matrix.count_nonzero(axis=0)
    word_score_sum = matrix.sum(axis=0)
    average_score_by_posting = word_score_sum / non_zero_count
    average_score_by_posting = average_score_by_posting.A1
    key_words = zip(list(terms), average_score_by_posting)
    key_words_filtered = [(word, float(score)) for word, score in list(key_words) if not word.isdigit()]
    key_words_ordered = sorted(key_words_filtered, key=lambda item: item[1], reverse=True)


    seniority = ["senior", "junior", "lead", "head", "praktikant", "praktikantin", "werkstudent", "werkstudentin", "trainee", "intern", "entry", "principal", "director", "praktikum", "owner"]
    seniority_count = {}
    for i in postings:
        try:
            title_tokens = set(re.findall(r"\w+", i["title"].lower()))
            desc_tokens = set(re.findall(r"\w+", i["description"].lower()))
            for word in seniority:
                if word in title_tokens or word in desc_tokens:
                    seniority_count[word] = seniority_count.get(word, 0) +1
        except KeyError:
            pass
        except AttributeError:
            pass
    seniority_count_ordered = sorted(seniority_count.items(), key=lambda item: item[1], reverse=True)

    lst_salary_max = []
    lst_salary_min = []
    for i in postings:
        try:
            lst_salary_max.append(i["salary_max"])
        except KeyError:
            pass
        try:
            lst_salary_min.append(i["salary_min"])
        except KeyError:
            pass

    try:
        salary_min_mean = sum(lst_salary_min)/len(lst_salary_min)
    except ZeroDivisionError:
        salary_min_mean = "No minimum salary data available"
    try:
        salary_max_mean = sum(lst_salary_max)/len(lst_salary_max)
    except ZeroDivisionError:
        salary_max_mean = "No maximum salary data available"


    final_summary = {
        "description": "This summary is based on a number of job postings and captures the main key words used in said postings (ranked by TF-IDF score, indicating terms that are notably concentrated in a subset of postings rather than common across all of them), the seniority the postings are primarily aiming towards, as well as the minimum and maximum mean salary for all postings where said numbers were provided.",
        "number_of_postings": len(postings),
        "key_words": dict(key_words_ordered[:60]),
        "seniority_count": dict(seniority_count_ordered),
        "salary_min_mean": salary_min_mean,
        "salary_max_mean": salary_max_mean
    }
    with open(f"{Path(__file__).parent}/summary.json", "w", encoding="utf-8") as f:
        json.dump(final_summary, f, indent=4, ensure_ascii=False)


summarize_data("data.json")