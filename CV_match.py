from anthropic import Anthropic
from dotenv import load_dotenv
import json
from pathlib import Path
import base64

load_dotenv()
client = Anthropic()

def add_user_message(messages, text):
    user_message = {"role": "user", "content": text}
    messages.append(user_message)

def add_assistant_message(messages, text):
    assistant_message = {"role": "assistant", "content": text}
    messages.append(assistant_message)

def chat(messages, model, stop_sequences=None):
    message = client.messages.create(
        model=model,
        max_tokens=10000,
        messages=messages,
        stop_sequences=stop_sequences
    )
    return message

def cv_match(CV):
    with open(f"{Path(__file__).parent}/data.json", "r", encoding="utf-8") as f:
        postings_dataset = json.load(f)
    postings_dataset_clean = []
    for posting in postings_dataset:
        postings_dataset_clean.append({"title": posting["title"], "description": posting["description"], "link": posting["redirect_url"], "id": posting["id"]})
    with open(f"{Path(__file__).parent}/{CV}", "rb") as f:
        cv_data = base64.standard_b64encode(f.read())

    prompt_cv_seniority = f"""
    Your are an expert headhunter with experience in the IT and IT related Jobmarket.
    
        CV to match:
        <cv>
        Found in the document_block
        </cv>
    
        Your should do the following steps as described in order:
        <steps>
        1. Analyze the CV and give it a seniority rank based on the amount of professional experience described in it. Only one of the following levels should be attributed to the CV: entry/junior/mid/senior. Clear definitions when each level should be applied can be found in the seniority_schema section.
        2. Return valid JSON in the way outlined in the example output.
        </steps>
    
        Seniority Schema for CV:
        <seniority_schema>
        When estimating total months of experience, only count professional or 
        skilled work: internships, working-student (Werkstudent) roles, and jobs 
        that used domain-relevant skills or qualifications.

        Do NOT count part-time jobs taken primarily for income rather than skill- 
        building — e.g. retail, cashier, food service/restaurant/café work, 
        delivery, warehouse/logistics work, babysitting, or similar. Exclude 
        these from the total even if they overlap in time with other experience 
        being counted.
        If the CV shows job experience between 0 to 6 months classify the CV as an entry level CV.
        If the CV showes between around 6 months to 2 years of job experience gained through possible internships or student jobs, classify the CV as junior level
        If the CV shows between 2 and 5 years of job experience, you should classify the CV as mid level.
        If the CV shows 5+ years of job experience, you should classify it as a senior level CV. 
        </seniority_schema>
    
        Example_output:
        <example_output>
        {{
            "cv_seniority": "mid"
        }}
        </example_output>
    """
    document_block = {
        "type": "document",
        "source": {
            "type": "base64",
            "media_type": "application/pdf",
            "data": cv_data.decode("utf-8")
        }
    }

    text_block = {
        "type": "text",
        "text": prompt_cv_seniority
    }

    messages = []
    add_user_message(messages, [document_block, text_block])
    add_assistant_message(messages, "```json")
    try:
        cv_seniority = json.loads(chat(messages, model = "claude-haiku-4-5-20251001", stop_sequences=["```"]).content[0].text)
    except json.decoder.JSONDecodeError:
        return print("Returned Invalid JSON")

    prompt_dataset_cleaning = f"""
    Your are an expert headhunter with experience in the IT and IT related Jobmarket.
    
    Job postings:
    <postings>
    {postings_dataset_clean}
    </postings>

    Your should do the following steps as described in order:
    <steps>
    1. Analyze each job posting and give it a seniority rank. Each posting should only have one rank attributed to it from the following: entry/junior/mid/senior. The attribution of seniority levels is outlined in more detail in the seniority_schema.
    2. Output a valid Json array with each entry being in the format described in the example_output.
    </steps>

    Seniority Schema for Postings:
    <seniority_schema>
    Classify each posting based on the experience level it requires, using these signals:

    - entry: explicitly states no experience required, welcomes graduates/
    career starters, or is aimed at students (e.g. "Berufseinstieg," 
    "für Absolvent:innen," "Praktikum").
    - junior: explicitly requests ~0-2 years of experience, or uses "Junior" 
    in the title/description.
    - mid: explicitly requests ~2-5 years of experience, or describes working 
    independently without mention of leading others.
    - senior: explicitly requests 5+ years, uses "Senior"/"Lead" in the title, 
    describes responsibilities like mentoring others, owning strategy, or 
    leading a team, or uses experience-implying language without a title 
    (e.g. "experienced," "fundierte/mehrjährige Erfahrung," "nachweisliche 
    Erfahrung in...") even without a specific title or year count.

    Should no indication of seniority be apparent in either the title or the description of each posting, attribute the "mid" seniority level to the posting.
    </seniority_schema>

    Example_output:
    <example_output>
    {{
        "posting_seniority": "mid",
        "id": "id from the respective posting"
    }}
    </example_output>
    """

    messages = []
    add_user_message(messages, prompt_dataset_cleaning)
    add_assistant_message(messages, "```json")
    try:
        output_dataset_cleaning = json.loads(chat(messages, model = "claude-haiku-4-5-20251001", stop_sequences=["```"]).content[0].text)
    except json.decoder.JSONDecodeError:
        return print("Returned Invalid JSON")

    for posting in postings_dataset_clean:
        for value in output_dataset_cleaning:
            if value["id"] == posting["id"]:
                posting["posting_seniority"] = value["posting_seniority"]

    missing = [p for p in postings_dataset_clean if "posting_seniority" not in p]
    for posting in missing:
        print(f"No seniority classification returned for: {posting['title']} (id: {posting['id']}) — excluded from this run.")
    postings_dataset_clean = [p for p in postings_dataset_clean if "posting_seniority" in p]

    postings_dataset_cv_ready = []
    for posting in postings_dataset_clean:
        if cv_seniority["cv_seniority"] == "entry":
            if posting["posting_seniority"] == "entry":
                postings_dataset_cv_ready.append(posting)
            continue
        elif cv_seniority["cv_seniority"] == "junior":
            if posting["posting_seniority"] == "entry" or posting["posting_seniority"] == "junior":
                postings_dataset_cv_ready.append(posting)
        elif cv_seniority["cv_seniority"] == "mid":
            if posting["posting_seniority"] == "junior" or posting["posting_seniority"] == "mid":
                postings_dataset_cv_ready.append(posting)
        else:
            if posting["posting_seniority"] == "mid" or posting["posting_seniority"] == "senior":
                postings_dataset_cv_ready.append(posting)
    if not postings_dataset_cv_ready:
        print(f"No postings at an appropriate seniority level ({cv_seniority['cv_seniority']}) were found in the current dataset.")
        with open(f"{Path(__file__).parent}/cv_match_result.json", "w", encoding="utf-8") as f:
            json.dump([], f, ensure_ascii=False, indent=2)
            return

    prompt_final_match = f"""
    Your are an expert headhunter with experience in the IT and IT related Jobmarket.
    
    Job postings:
    <postings>
    {postings_dataset_cv_ready}
    </postings>

    CV to match:
    <cv>
    Cv found in the document block
    </cv>

    Your should do the following steps as described in order:
    <steps>
    1. Scan all job postings as provided above as well as the CV provided in detail. 
    2. For each job posting generate a short list of key_requirements based on what is described in the postings description and title. 
    3. Compare the key_requirements list for each posting with the skills and experience described in the CV.
    4. Before compiling your final list, go through the complete postings list one more time, in order. For every single posting — including ones you already dismissed — note in one short line whether it is a plausible candidate or not. Do not skip any posting in this pass, even obvious non-matches.
    5. Based on the steps above create a JSON array "reasoning" with the "key_requirements", "cv_evidence", a free-text "verdict" explaining the fit, and a "match_quality" field set to exactly one of: "excellent", "good", "moderate", "poor", "no_match".
    6. Filter this reasoning array: discard every entry whose match_quality is "moderate", "poor", or "no_match". Only entries marked "excellent" or "good" may proceed to the final list — this applies even if it leaves very few or zero results.
    7. Output your final list using ONLY the entries that survived step 6, with: "rank" starting from 1, "title", "link", and "reasoning" (the entry from step 5).
    </steps>

    Example_output:
    <example_output>
    {{
        "rank": number,
        "title": string,
        "link": string,
        "reasoning": {{
            "key_requirements": [...],
            "cv_evidence": [...],
            "verdict": string,
            "match_quality": "excellent" | "good" | "moderate" | "poor" | "no_match"
        }}
    }}
    </example_output>

    IMPORTANT further instructions to keep in mind throughout the whole operation:
    <further_instructions>
    Do not just trust the title of a job posting regarding fit with a CV. Take it as an indication for a possible fit but always dig deeper in the description as well to confirm.
    For each key_requirement, the verdict must state explicitly whether the CV shows direct, hands-on evidence of that specific requirement — not an adjacent skill, not a related but different project. A core requirement with no direct match is a disqualifying gap; unrelated soft skills or tangential experience cannot offset it.
    A posting's match_quality must be consistent with its own verdict text — if the verdict describes a disqualifying gap, match_quality cannot be "excellent" or "good."
    No posting with match_quality "moderate", "poor", or "no_match" may appear in the final output, regardless of rank or how few results remain.
    After completion check the output again and revalidate to make sure there are not duplicate objects or any malformed JSON.
    Should you find no matches return an empty list.
    Return only valid JSON and no extra headers or explenations, except in the reasoning field described above.
    </further_instructions>
    """
    document_block = {
        "type": "document",
        "source": {
            "type": "base64",
            "media_type": "application/pdf",
            "data": cv_data.decode("utf-8")
        }
    }

    text_block = {
        "type": "text",
        "text": prompt_final_match
    }
    messages = []
    add_user_message(messages, [document_block, text_block])
    add_assistant_message(messages, "```json")
    try:
        output = json.loads(chat(messages, model="claude-sonnet-4-5-20250929", stop_sequences=["```"]).content[0].text)
        postings_matching = {}
        for posting in postings_dataset_cv_ready:
            postings_matching[posting["link"]] = posting["title"]
        link_counts = {}
        for i in output:
            link_counts[i["link"]] = link_counts.get(i["link"], 0) + 1
            if i["link"] in postings_matching.keys() and i["title"] == postings_matching[i["link"]]:
                continue
            else:
                return print(f"Posting at position {i["rank"]} has a title and link that do not match.")
        for link, count in link_counts.items():
            if count > 1:
                return print(f"Duplicate link found: {link}, validation failed before reaching the model grader.")
        with open(f"{Path(__file__).parent}/cv_match_result.json", "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
    except json.decoder.JSONDecodeError:
        return print("Returned Invalid JSON")
    

if __name__ == "__main__":
    cv_match("Your_CV.pdf")
