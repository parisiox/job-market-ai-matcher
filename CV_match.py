from anthropic import Anthropic
from dotenv import load_dotenv
import json
from pathlib import Path
import base64

load_dotenv()
client = Anthropic()
model = "claude-sonnet-4-5-20250929"

def add_user_message(messages, text):
    user_message = {"role": "user", "content": text}
    messages.append(user_message)

def add_assistant_message(messages, text):
    assistant_message = {"role": "assistant", "content": text}
    messages.append(assistant_message)

def chat(messages, stop_sequences=None):
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
        postings_dataset_clean.append({"title": posting["title"], "description": posting["description"], "link": posting["redirect_url"]})
    with open(f"{Path(__file__).parent}/{CV}", "rb") as f:
        cv_data = base64.standard_b64encode(f.read())

    prompt = f"""
    Your are an expert headhunter with experience in the IT and IT related Jobmarket.
    
        Job postings:
        <postings>
        {postings_dataset_clean}
        </postings>
    
        CV to match:
        <cv>
        Found in the document_block
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
        "text": prompt
    }
    messages = []
    add_user_message(messages, [document_block, text_block])
    add_assistant_message(messages, "```json")
    try:
        output = json.loads(chat(messages, stop_sequences=["```"]).content[0].text)
        with open(f"{Path(__file__).parent}/cv_match_result.json", "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
    except json.decoder.JSONDecodeError:
        return print("Returned Invalid JSON")
    

if __name__ == "__main__":
    cv_match("Your_CV.pdf")
