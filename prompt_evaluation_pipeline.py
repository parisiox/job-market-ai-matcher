from anthropic import Anthropic
from dotenv import load_dotenv
from pathlib import Path
import json
from statistics import mean

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

def log_prompt(prompt_version, prompt):
    path = f"{Path(__file__).parent}/prompt.json"
    try:
        with open(path, "r", encoding="utf-8") as f:
            logged_prompts = json.load(f)
    except (FileNotFoundError, json.decoder.JSONDecodeError):
        logged_prompts = {}

    logged_prompts[prompt_version] = prompt

    with open(path, "w", encoding="utf-8") as f:
        json.dump(logged_prompts, f, indent=4, ensure_ascii=False)

def generate_test_CVs():
    seniority = [
    {
        "intern/student": "This candidate has NOT yet secured any internship or professional work experience — their only 'work experience' entry, if any, should be an unrelated part-time job (retail, food service, tutoring, etc.), not anything tech-related. They have completed at most 1-2 basic university course projects (not polished, deployed, or particularly ambitious — think a simple CRUD app or a class assignment, not a full-stack platform with a live demo). No professional certifications. Possible international experience such as an exchange semester but not a must. GPA should either be omitted entirely or be unremarkable (around 2.8-3.2). Their skills list should be limited to what a normal curriculum would cover — a couple of core languages and basic web fundamentals, nothing about cloud platforms, DevOps, or advanced frameworks."
    },
    {
        "junior": "This candidate has 1-2 years of professional experience in a single role, without an internship necessarily preceding it. Their work has been solid but unremarkable — routine bug fixes, small feature contributions, no leadership or standout achievements, and any listed accomplishments should be modest and believable (not sweeping percentage improvements). At most one certification, and it may be entirely absent. Education should be a standard, non-honors degree with an unremarkable GPA or none listed. Projects, if any, should be simple and coursework- or hobby-driven rather than professional-grade. International experience is optional but can be present in the form of an exchange semester or another form of international experience."
    },
    {
        "senior": "This candidate has 8+ years of experience but has remained an individual contributor throughout their career — no architecture, team-lead, or mentoring responsibilities, and no dramatic migration or transformation projects to point to. Their experience should reflect steady, competent work within a fairly narrow technology stack rather than broad expertise across many tools and platforms. No certifications, or at most one that may be old/expired. Career progression should be modest (a couple of lateral moves or slow title changes, not a fast climb to 'Lead Architect'). No notable side projects, publications, or public speaking. This is a normal, employable, but unremarkable senior professional — not a standout."
    }
    ]
    job_type = ["IT", "IT-consultant"]
    final_output = []
    CV_generating_messages = []
    for i in seniority:
        for role, description in i.items():
            for job in job_type:

                prompt = f"""
                Generate an evaluation dataset for a prompt evaluation. The dataset will be used to test a prompt asking an AI to match CVs provided, with job descriptions based on how well the CV fits the description.
                The CV you generate should be for a {role} level of seniority in the {job} field. The specific qualifications that person should hold is detailed in {description}.
                Include elements typically found in a CV such as possible education, relavant work experience/internships, projects where applicable, skills that people might have developed on their own, test or certifications as well as international experience.
                The CV should be output in a natural language format only.
                Make sure there is no overlap between the CVs you generate and what you find in the messages list. None of the content in a CV should be the same as in another CV. However, the CV should still be written in English.
                The CV should be generated with and Austrian individual in mind, as the dataset will be used with job descriptions posted in Austria.
                Generate exactly 1 CV.
                """

                add_user_message(CV_generating_messages, prompt)

                CV_generating_answer = chat(CV_generating_messages, model="claude-haiku-4-5-20251001")

                add_assistant_message(CV_generating_messages, CV_generating_answer.content[0].text)

                result = {
                    "seniority": role,
                    "job_type": job,
                    "text": CV_generating_answer.content[0].text,
                    "stop_reason": CV_generating_answer.stop_reason
                }
                
                final_output.append(result)
    with open(f"{Path(__file__).parent}/test_CVs.json", "w", encoding="utf-8") as f:
        json.dump(final_output, f, indent=4, ensure_ascii=False)
    return final_output

prompt_version = "v12"

def run_prompt(test_CV, postings_dataset_cv_ready):        
    prompt_final_match = f"""
    Your are an expert headhunter with experience in the IT and IT related Jobmarket.
    
    Job postings:
    <postings>
    {postings_dataset_cv_ready}
    </postings>

    CV to match:
    <cv>
    {test_CV}
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

    messages = []
    add_user_message(messages, prompt_final_match)
    add_assistant_message(messages, "```json")
    output = chat(messages, model="claude-sonnet-4-5-20250929", stop_sequences=["```"]).content[0].text
    return json.loads(output), prompt_final_match

def model_grader(test_CV, postings_dataset_cv_ready, output, prompt):
    eval_prompt = f"""
    Your are an expert recruiter and have a lot of experience with IT and IT related recruiting. Your task is to evaluate an AI generated solution.
    Original Task:
    <task>
    {prompt}
    </task>

    Original Datasets:
    <datasets>
    {test_CV}
    {postings_dataset_cv_ready}
    </datasets>

    Solution to evaluate:
    <solution>
    {output}
    </solution>

    You should use the original datasets to evaluate how well the original task was fulfilled by the AI generated solution.
    Follow these steps when evaluating the solution:
    <evaluation_steps>
    1. check the reasoning for each of the top postings for completion and faulty reasoning.
    2. Should any of these top postings be clearly out of place scan the rest of the dataset for possible replacements and provide the redirect_url of the replacement in the reasoning field described below.
    3. Even if the top postings hold up, check the rest of the dataset again for any postings that were possibly missed. Should you find any postings that were clearly missed and would have been in those at the top, also inclde them in the reasoning field.
    4. Also check if the number of postings in the top list is appropriate when looking at all the postings. If there are any postings that should be in the top but are not include that in your reasoning as well.
    5. Based on the above, compile your strengths, weaknesses, reasoning and score for the AI-generated solution using the example output shape outlined below.
    </evaluation_steps>

    Output Format:
    <output_format>
    Your output should be valid JSON with the following fields in that order:
    -"strenghts": An array of 1-3 strengths
    -"weaknesses": An array of 1-3 weaknesses
    -"reasoning": An explenation of the overall assessment
    -"score": A final score from 1-10
    </output_format>

    Respond with JSON only. Keep your answers clear and concise.

    Example output shape:
    <example_output>
    {{
        "strengths": string[],
        "weaknesses": string[],
        "resoning": string,
        "score": number
    }}
    </example_output>
    """

    messages = []
    add_user_message(messages, eval_prompt)
    add_assistant_message(messages, "```json")
    eval_output = chat(messages, model="claude-sonnet-4-5-20250929", stop_sequences=["```"]).content[0].text
    return json.loads(eval_output)


def run_test_case(test_CV, postings_dataset_clean):
    prompt_cv_seniority = f"""
    Your are an expert headhunter with experience in the IT and IT related Jobmarket.
    
    CV to match:
    <cv>
    {test_CV}
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
    messages = []
    add_user_message(messages, prompt_cv_seniority)
    add_assistant_message(messages, "```json")
    try:
        cv_seniority = json.loads(chat(messages, model = "claude-haiku-4-5-20251001", stop_sequences=["```"]).content[0].text)
    except json.decoder.JSONDecodeError:
        return {
            "Error": "Returned invalid JSON for this CV."
        }

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
        return {"Error": f"No postings at an appropriate seniority level ({cv_seniority['cv_seniority']}) were found in the current dataset."}

    output, prompt = run_prompt(test_CV, postings_dataset_cv_ready)

    postings_matching = {}
    for posting in postings_dataset_cv_ready:
        postings_matching[posting["link"]] = posting["title"]
    link_counts = {}
    for i in output:
        link_counts[i["link"]] = link_counts.get(i["link"], 0) + 1
        if i["link"] in postings_matching.keys() and i["title"] == postings_matching[i["link"]]:
            continue
        else:
            return {"Error": f"Posting at position {i["rank"]} has a title and link that do not match, validation faild before reaching the model grader."}
    for link, count in link_counts.items():
        if count > 1:
            return {"Error": f"Duplicate link found: {link}, validation failed before reaching the model grader."}


    model_grade = model_grader(test_CV, postings_dataset_cv_ready, output, prompt)
    score = model_grade["score"]
    reasoning = model_grade["reasoning"]

    return {
        "output": output,
        "test_CV": test_CV,
        "prompt_version": prompt_version,
        "score": score,
        "reasoning": reasoning
    }, prompt
    

def run_eval():
    with open(f"{Path(__file__).parent}/test_CVs.json", "r", encoding="utf-8") as f:
        cvs_dataset = json.load(f)
    with open(f"{Path(__file__).parent}/data.json", "r", encoding="utf-8") as f:
        postings_dataset = json.load(f)
    postings_dataset_clean = []
    for posting in postings_dataset:
        postings_dataset_clean.append({"title": posting["title"], "description": posting["description"], "link": posting["redirect_url"], "id": posting["id"]})

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

    

    results = []
    for test_CV in cvs_dataset:
        try:
            result, prompt = run_test_case(test_CV["text"], postings_dataset_clean)
            if type(result) == str:
                return print(result)
            results.append(result)
        except json.decoder.JSONDecodeError:
            print("Returned Invalid JSON")
            results.append({"JSONDecodeError": "Returned Invalid JSON"})

    scores = []
    for result in results:
        try:
            scores.append(result["score"])
        except KeyError:
            pass
    average_score = mean(scores)
    results.append({"average_score": average_score})
    
    log_prompt(prompt_version, prompt)

    with open(f"{Path(__file__).parent}/eval_{prompt_version}.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=4, ensure_ascii=False)
    
    return results
    

if __name__ == "__main__":
    run_eval()