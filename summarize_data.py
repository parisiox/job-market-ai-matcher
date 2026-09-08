
from pathlib import Path
import json
from spacy.lang.en.stop_words import STOP_WORDS as en_stopwords
from spacy.lang.de.stop_words import STOP_WORDS as de_stopwords
import re


def summarize_data(data):
    try:
        with open(data, "r", encoding="utf-8") as f:
            words = []
            content = json.loads(f.read())
            for i in content:
                try:
                    if i["description"] != None:
                        words.append(i["description"])
                except KeyError:
                    pass
    except json.decoder.JSONDecodeError:
        print("file contains invalid JSON")
        return

    words_seperated = []
    for i in words:
        words_seperated.extend(re.findall(r"\w{2,}(?:[:-]\w+)?", i.lower()))

    words_seperated_de = [i for i in words_seperated if i not in de_stopwords]
    words_seperated_both = [i for i in words_seperated_de if i not in en_stopwords]
    words_no_numbers = []
    for i in words_seperated_both:
        if i.isdigit() == True:
            continue
        else:
            words_no_numbers.append(i)

    key_words = {}
    for word in words_no_numbers:
        key_words[word] = key_words.get(word, 0) + 1
    key_words_ordered = sorted(key_words.items(), key=lambda item: item[1], reverse=True)


    seniority = ["senior", "junior", "lead", "head", "praktikant", "praktikantin", "werkstudent", "werkstudentin", "trainee", "intern", "entry", "associate", "principal", "director", "praktikum", "owner", "berater"]
    seniority_count = {}
    for i in content:
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
    for i in content:
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
        "description": "This summary is based on a number of job postings and captures the main key words used in said postings, the seniority the postings are primarily aiming towards, as well as the minimum and maximum mean salary for all postings where said numbers were provided.",
        "number_of_postings": len(content),
        "key_words": dict(key_words_ordered[:60]),
        "seniority_count": dict(seniority_count_ordered),
        "salary_min_mean": salary_min_mean,
        "salary_max_mean": salary_max_mean
    }
    with open(f"{Path(__file__).parent}/summary.json", "w", encoding="utf-8") as f:
        json.dump(final_summary, f, indent=4, ensure_ascii=False)


summarize_data(f"{Path(__file__).parent}/data.json")