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

prompt_version = "v4"

def run_prompt(test_CV, posting_dataset_clean):        
    prompt = f"""
    Your are an expert headhunter with experience in the IT and IT related Jobmarket.

    Job postings:
    <postings>
    {posting_dataset_clean}
    </postings>

    CV to match:
    <cv>
    {test_CV}
    </cv>

    Your should do the following steps as described in order:
    <steps>
    1. Scan all job postings as provided above as well as the CV provided in detail.
    2. Match each job posting to the whole CV and evaluate wheather it would be a good fit or not.
    3. Filter out up to 5 of the best fitting descriptions to the CV, depending on how many very good matches you find.
    4. Do one more pass and check if you missed any good matches and if the matches you picked out would still be the same even after a second pass.
    5. Output your list in the format described below including all fields mentioned.
    </stesp>

    Output Format:
    <output_format>
    You should return valid JSON array of up to 5 objects. Each object should cover one posting with the key value pairs: "rank": "1-5 depending if it is the most - least matching of the possible top 5", "title": "the title of the job posting", "link": "the link to the job posting", "reasoning": "your explenation why this posting has this ranking on the list".
    </output_format>

    Example_output:
    <example_output>
    {{
        "rank": number,
        "title": string,
        "link": string,
        "reasoning": string
    }}
    </example_output>

    IMPORTANT further instructions to keep in mind throughout the whole operation:
    <further_instructions>
    Make sure that each and every part of the CV is considered for the jobs you select and that this level of detail is kept up for all ranks not just for 1.
    Be very thorough when going through the job postings as to make sure not to miss any good matches.
    Make sure the seniority of a job posting also fits the CV not just the skills or qualifications.
    Do not just trust the title of a job posting regarding fit with a CV. Take it as an indication for a possible fit but always dig deeper in the description as well to confirm.
    After completion check the output again and revalidate to make sure there are not duplicate objects or any malformed JSON.
    Return only valid JSON and no extra headers or explenations, except in the reasoning field described above.
    </further_instructions>
    """

    messages = []
    add_user_message(messages, prompt)
    add_assistant_message(messages, "```json")
    output = chat(messages, model="claude-sonnet-4-5-20250929", stop_sequences=["```"]).content[0].text
    return json.loads(output), prompt

def model_grader(test_CV, posting_dataset_clean, output, prompt):
    eval_prompt = f"""
    Your are an expert recruiter and have a lot of experience with IT and IT related recruiting. Your task is to evaluate an AI generated solution.
    Original Task:
    <task>
    {prompt}
    </task>

    Original Datasets:
    <datasets>
    {test_CV}
    {posting_dataset_clean}
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


def model_re_grader(result, postings_dataset_clean):
    re_grader_prompt = f"""
    Your are an expert headhunter with experience in the IT and IT related job market.
    You will evaluate an AI generated output together with the results of a grader and generate a new output based on your evaluation.

    AI generated results and grading:
    <ai_grading>
    {result}
    </ai_grading>

    Job postings:
    <job_postings>
    {postings_dataset_clean}
    </job_postings>

    Step by step instructions:
    <instructions>
    1. Go through the graders reasoning and the problems that are highlighted.
    2. Check if the problems highlighted are valid by evaluating both the top job matching results as well as all other job postings for other possible matches.
    3. Based on your reasoning correct any mistakes that were made in the original AI generated output.
    4. Should you find it necessary add some postings to the top list ONLY if genuinely strong matches are not included yet but make sure there are no more than 5.
    5. Return an array of JSON objects in the format detailed below
    </instructions>

    Output Format:
    <output_format>
    You should return valid JSON array of up to 5 objects. Each object should cover one posting with the key value pairs: "rank": "1-5 depending if it is the most - least matching of the possible top 5", "title": "the title of the job posting", "link": "the link to the job posting", "reasoning": "your explenation why this posting has this ranking on the list".
    </output_format>

    Example_output:
    <example_output>
    {{
        "rank": number,
        "title": string,
        "link": string,
        "reasoning": string
    }}
    </example_output>

    IMPORTANT further instructions to keep in mind throughout the whole operation:
    <further_instructions>
    Be very thorough when going through the job postings as to make sure not to miss any good matches.
    Make sure the seniority of a job posting also fits the CV not just the skills or qualifications.
    Do not just trust the title of a job posting regarding fit with a CV. Take it as an indication for a possible fit but always dig deeper in the description as well to confirm.
    After completion check the output again and revalidate to make sure there are not duplicate objects or any malformed JSON.
    Return only valid JSON and no extra headers or explenations, except in the reasoning field described above.
    </further_instructions>
    """

    messages = []
    add_user_message(messages, re_grader_prompt)
    add_assistant_message(messages, "```json")
    output_re_grader = chat(messages, model="claude-sonnet-4-5-20250929", stop_sequences=["```"]).content[0].text
    return json.loads(output_re_grader)


def run_test_case(test_CV, postings_dataset_clean):
    output, prompt = run_prompt(test_CV, postings_dataset_clean)

    model_grade = model_grader(test_CV, postings_dataset_clean, output, prompt)
    score = model_grade["score"]
    reasoning = model_grade["reasoning"]

    result = {
        "output": output,
        "test_CV": test_CV,
        "prompt_version": prompt_version,
        "score": score,
        "reasoning": reasoning
    }
    output_re_grader = model_re_grader(result, postings_dataset_clean)
    final_grade = model_grader(test_CV, postings_dataset_clean, output_re_grader, prompt)
    score_final = final_grade["score"]
    reasoning_final = final_grade["reasoning"]

    return {
        "output": output_re_grader,
        "test_CV": test_CV,
        "prompt_version": prompt_version,
        "score": score_final,
        "reasoning": reasoning_final
    }

def run_eval():
    with open(f"test_CVs.json", "r", encoding="utf-8") as f:
        cvs_dataset = json.load(f)
    with open(f"data.json", "r", encoding="utf-8") as f:
        postings_dataset = json.load(f)
    postings_dataset_clean = []
    for posting in postings_dataset:
        postings_dataset_clean.append({"title": posting["title"], "description": posting["description"], "link": posting["redirect_url"]})

    results = []

    for test_CV in cvs_dataset:
        result = run_test_case(test_CV["text"], postings_dataset_clean)
        results.append(result)

    average_score = mean([result["score"] for result in results])
    results.append({"average_score": average_score})
    
    with open(f"{Path(__file__).parent}/eval_{prompt_version}.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=4, ensure_ascii=False)
    
    return results

if __name__ == "__main__":
    run_eval()