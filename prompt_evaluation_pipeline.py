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

prompt_version = "v9"

def run_prompt(test_CV, postings_dataset_clean):        
    prompt = f"""
    Your are an expert headhunter with experience in the IT and IT related Jobmarket.
    
    Job postings:
    <postings>
    {postings_dataset_clean}
    </postings>

    CV to match:
    <cv>
    {test_CV}
    </cv>

    Your should do the following steps as described in order:
    <steps>
    1. Scan all job postings as provided above as well as the CV provided in detail. 
    2. Cross reference with the seniority_schema and in a first pass exclude any postings that do not match the provided CV in seniority at all and finish the remaining instructions with the rest of the postings.
    3. For each job posting generate a short list of key_requirements based on what is described in the postings description. Also generate a "seniority" field for each posting which describes the level of seniority and experience that is asked by the posting, the only possible options that are allowed for this field are entry/junior/mid/senior. Should no specific level of seniority or job experience be described at least mid should be the level of seniority for the posting.
    4. Exclude any and all postings that do not EXACTLY match the seniority requirements for the CV as outlined in the seniority_schema.
    5. Compare the key_requirements list for each posting with the skills and experience described in the CV.
    6. Based on the two steps above create a JSON array "reasoning" with the "key_requirements", detailing the key requirements you decided on for that specific posting, "cv_evidence" which details the contents of the CV that support that the CV fits the job posting, "seniority" as described in step 3, and "verdict", which contains a verdict on wheather or not this job posting fits the CV based on the previouse two values.
    7. Output your final list with the key value pairs: "rank": starting form 1 - the last match you included in descending order based on how good of a match each posting is. "title": The title of the job posting. "link": the redirect_url of the job posting. And finally "reasoning": The second JSON array as described in step 5.
    </steps>

    Seniority Schema for CV:
    <seniority_schema>
    If the CV DOES NOT show any relavant job experience yet or very little of it, ONLY recommend positions that are of the entry or junior seniority and NO OTHERS.
    If the CV shows A FEW years of experience, you should recommend MOSTLY mid positions as well as senior positions but ONLY if the specific job experience needed for that positions match very well with what is offered in the CV.
    If the CV shows MANY years of experience, you should recommend senior positions only that fit the provided CV the most.    
    </seniority_schema>

    Example_output:
    <example_output>
    {{
        "rank": number,
        "title": string,
        "link": string,
        "reasoning": JSON array from step 4
    }}
    </example_output>

    IMPORTANT further instructions to keep in mind throughout the whole operation:
    <further_instructions>
    Do not just trust the title of a job posting regarding fit with a CV. Take it as an indication for a possible fit but always dig deeper in the description as well to confirm.
    After completion check the output again and revalidate to make sure there are not duplicate objects or any malformed JSON.
    The output list does not have to have a certain length if there are only 2 or 3 good or better matches then thats acceptable. The output should be quality over quantity.
    Any matches that are not at least good exclude from the final list
    Return only valid JSON and no extra headers or explenations, except in the reasoning field described above.
    </further_instructions>
    """

    messages = []
    add_user_message(messages, prompt)
    add_assistant_message(messages, "```json")
    output = chat(messages, model="claude-sonnet-4-5-20250929", stop_sequences=["```"]).content[0].text
    with  open(f"{Path(__file__).parent}/prompt.json", "a", encoding="utf-8") as f:
        f.write(json.dumps({"prompt_version": prompt_version, "prompt": prompt}, ensure_ascii=False) + "\n")
    return json.loads(output), prompt

def model_grader(test_CV, postings_dataset_clean, output, prompt):
    eval_prompt = f"""
    Your are an expert recruiter and have a lot of experience with IT and IT related recruiting. Your task is to evaluate an AI generated solution.
    Original Task:
    <task>
    {prompt}
    </task>

    Original Datasets:
    <datasets>
    {test_CV}
    {postings_dataset_clean}
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
    output, prompt = run_prompt(test_CV, postings_dataset_clean)

    model_grade = model_grader(test_CV, postings_dataset_clean, output, prompt)
    score = model_grade["score"]
    reasoning = model_grade["reasoning"]

    return {
        "output": output,
        "test_CV": test_CV,
        "prompt_version": prompt_version,
        "score": score,
        "reasoning": reasoning
    }
    

def run_eval():
    with open(f"{Path(__file__).parent}/test_CVs.json", "r", encoding="utf-8") as f:
        cvs_dataset = json.load(f)
    with open(f"{Path(__file__).parent}/data.json", "r", encoding="utf-8") as f:
        postings_dataset = json.load(f)
    postings_dataset_clean = []
    for posting in postings_dataset:
        postings_dataset_clean.append({"title": posting["title"], "description": posting["description"], "link": posting["redirect_url"]})

    results = []
    for test_CV in cvs_dataset:
        try:
            result = run_test_case(test_CV["text"], postings_dataset_clean)
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
    
    with open(f"{Path(__file__).parent}/eval_{prompt_version}.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=4, ensure_ascii=False)
    
    return results
    

if __name__ == "__main__":
    run_eval()