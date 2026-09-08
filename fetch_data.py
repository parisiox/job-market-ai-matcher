import requests
import os
from pathlib import Path
import json
from dotenv import load_dotenv

load_dotenv()

APP_ID = os.getenv("APP_ID")
APP_KEY = os.getenv("APP_KEY")

categories = ["it-jobs", "consultancy-jobs"]


def fetch_data(country, page_num, app_id, app_key, what=None, what_or=None, where=None, content_type=None, results_per_page=None, part_time=None, category=None):

    url = f"http://api.adzuna.com/v1/api/jobs/{country}/search/{page_num}"
    applications_list = []
    if category is None:
        category = [None]
    for i in category:
        params = {
            "app_id": app_id,
            "app_key": app_key,
            "what": what,
            "what_or": what_or,
            "where": where,
            "content-type": content_type,
            "results_per_page": results_per_page,
            "part_time": part_time,
            "category": i
        }


        try:
            response = requests.get(url, params=params, timeout=20)
            if response.status_code != 200:
                print(f"{response.status_code} bad request")
                continue
            content = response.json()["results"]
            applications_list.extend(content)
            with open(f"{Path(__file__).parent}/data1.json", "w", encoding="utf-8") as f:
                json.dump(applications_list, f, indent=4, ensure_ascii=False)
        
        except requests.exceptions.ConnectionError:
            print("Cannot connect to server")
            
        except requests.exceptions.JSONDecodeError:
            print("returned invalid JSON")
            
        except requests.exceptions.Timeout:
            print("Timeout, no response recieved")

if __name__ == "__main__":
    fetch_data("at", 1, APP_ID, APP_KEY, results_per_page=100, where="Vienna", content_type="application/json", category=categories)