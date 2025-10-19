import os
import json
import time
import google.generativeai as genai
from openai import OpenAI
from dotenv import load_dotenv
from google.api_core.exceptions import ResourceExhausted

# [configure_llm, get_specialty_for_symptoms, check_for_red_flags, find_best_match functions remain unchanged]
# [For brevity, they are not repeated here, but they are still part of the file]

def _call_llm_with_retry(api_call_fnc):
    """
    Calls the LLM API with exponential backoff for ResourceExhausted errors.
    """
    retries = 3
    delay = 5  # seconds
    for i in range(retries):
        try:
            return api_call_fnc()
        except ResourceExhausted as e:
            if i < retries - 1:
                print(f"Resource exhausted. Retrying in {delay} seconds...")
                time.sleep(delay)
                delay *= 2  # Exponential backoff
            else:
                print("LLM resource exhausted after multiple retries.")
                raise e
    return None # Should not be reached, but as a fallback

def configure_llm():
    """
    Configures and returns the appropriate LLM client based on environment variables.
    """
    load_dotenv()
    use_gemini = os.getenv("USE_GEMINI", "true").lower() == "true"
    use_openai = os.getenv("USE_OPENAI", "false").lower() == "true"

    if use_gemini:
        gemini_api_key = os.getenv("GEMINI_API_KEY")
        if not gemini_api_key:
            raise ValueError("GEMINI_API_KEY not found in .env file.")
        genai.configure(api_key=gemini_api_key)
        model = genai.GenerativeModel(os.getenv("GEMINI_MODEL", "gemini-1.5-flash"))
        print("Using Gemini model.")
        return model, "gemini"
    elif use_openai:
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if not openai_api_key:
            raise ValueError("OPENAI_API_KEY not found in .env file.")
        client = OpenAI(api_key=openai_api_key)
        print("Using OpenAI model.")
        return client, "openai"
    else:
        raise ValueError("No LLM is enabled. Please set USE_GEMINI or USE_OPENAI to true in the .env file.")

def get_specialty_for_symptoms(model, model_type, user_input):
    """
    Determines the most relevant medical specialty for a given set of symptoms.
    """
    prompt = f'''
    You are a medical expert. Based on the following symptoms, what is the most appropriate medical specialty to consult? 
    Choose from common specialties like General Physician, ENT, Dermatologist, Orthopedic, Gynecologist, Cardiologist, etc.
    Return only the name of the specialty.

    Symptoms: "{user_input}"
    Specialty:
    '''
    
    def api_call():
        if model_type == "gemini":
            response = model.generate_content(prompt)
            return response.text.strip()
        elif model_type == "openai":
            response = model.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a medical expert who only responds with the name of a medical specialty."},
                    {"role": "user", "content": prompt}
                ]
            )
            return response.choices[0].message.content.strip()

    return _call_llm_with_retry(api_call)

def check_for_red_flags(model, model_type, user_input):
    """
    Checks if the user input contains any red flag symptoms.
    """
    prompt = f'''
    You are a medical triage expert. Your task is to determine if the user\'s statement contains any critical, life-threatening symptoms.
    These are considered "red flags".

    Red flag symptoms include, but are not limited to:
    - Chest pain or pressure
    - Difficulty breathing or shortness of breath
    - Severe headache, especially if sudden
    - Weakness, numbness, or paralysis, especially on one side of the body
    - Confusion or altered mental state
    - Slurred speech
    - Seizures
    - High fever with a stiff neck
    - Severe abdominal pain
    - Uncontrolled bleeding
    - Thoughts of self-harm or suicide
    - Mention of a serious diagnosis like \'cancer\', \'heart attack\', \'stroke\'

    User input: "{user_input}"

    Based on this input, does it contain any red flag symptoms? Answer with only "true" or "false".
    '''
    
    def api_call():
        if model_type == "gemini":
            response = model.generate_content(prompt)
            return response.text.strip().lower() == "true"
        elif model_type == "openai":
            response = model.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a medical triage expert who only responds with 'true' or 'false'."},
                    {"role": "user", "content": prompt}
                ]
            )
            return response.choices[0].message.content.strip().lower() == "true"

    return _call_llm_with_retry(api_call)

def find_best_match(model, model_type, user_symptoms, appointments):
    """
    Uses the LLM to find the best matching past appointment.
    """
    if not appointments:
        return None

    prompt_appointments = []
    for app in appointments:
        prompt_appointments.append({
            "doc_id": app.get("doc_id"),
            "appointmentDate": app.get("appointmentDate"),
            "symptomsText": app.get("symptomsText")
        })

    prompt = f'''
    You are a medical data analysis expert. A patient has reported new symptoms, and I need you to find the most relevant past appointment from their history.

    The patient's new symptoms are: "{user_symptoms}"

    Here is a list of their past appointments in JSON format:
    {json.dumps(prompt_appointments, indent=2)}

    Your task is to compare the new symptoms with the 'symptomsText' of each past appointment.
    **Crucial Rule:** Only return a match if the new symptoms are genuinely and semantically similar to the past symptoms. A vague similarity is not enough.
    For example, if the new symptom is "cancer", and the past symptoms are "fever and cough", this is NOT a match.
    If the new symptom is "sore throat and fever" and a past symptom is "throat pain, fever, cough", this IS a good match.

    If you find a genuinely similar appointment, respond with only the JSON object of that single best match.
    If you do NOT find any good match, you MUST respond with an empty JSON object: {{}}.
    '''

    def api_call():
        if model_type == "gemini":
            response = model.generate_content(prompt)
            text_response = response.text.strip().replace("```json", "").replace("```", "").strip()
            try:
                return json.loads(text_response)
            except json.JSONDecodeError:
                return None
        elif model_type == "openai":
            response = model.chat.completions.create(
                model="gpt-3.5-turbo-1106",
                response_format={ "type": "json_object" },
                messages=[
                    {"role": "system", "content": "You are a helpful medical data analyst that only responds with JSON."},
                    {"role": "user", "content": prompt}
                ]
            )
            try:
                return json.loads(response.choices[0].message.content)
            except json.JSONDecodeError:
                return None

    best_match = _call_llm_with_retry(api_call)

    if not best_match or not best_match.get("doc_id"):
        return None

    for app in appointments:
        if app.get("doc_id") == best_match.get("doc_id"):
            return app
    return None

def generate_combined_response(model, model_type, user_input, matched_appointment, history_doctor_name, routed_doctor_name):
    """
    Generates a combined response showing the AI suggestion AND the routing information.
    """
    # Part 1: Generate the AI suggestion text (based on past history)
    ai_suggestion_text = ""
    if not matched_appointment:
        ai_suggestion_text = "After reviewing your past medical records, no appointments with similar symptoms were found."
    else:
        patient_name = matched_appointment.get('patientName', 'there')
        appointment_date = matched_appointment.get('appointmentDate')
        display_history_doctor = history_doctor_name if history_doctor_name else "the doctor"
        symptoms = matched_appointment.get('symptomsText')
        prescriptions = matched_appointment.get('prescriptions', [])

        prescription_list = []
        for p in prescriptions:
            if p.get('name'):
                p_str = f"- {p['name']} {p.get('strength', '')}".strip()
                if p.get('purpose'):
                    p_str += f" (for {p['purpose']})"
                prescription_list.append(p_str)
        
        prescription_str = '\n'.join(prescription_list) if prescription_list else "No specific prescriptions were listed."
        
        ai_suggestion_text = (
            f"Based on your symptoms, I found a past appointment with Dr. {display_history_doctor} on {appointment_date} for similar symptoms ('{symptoms}').\n"
            f"The suggested prescription at that time was:\n{prescription_str}"
        )

    # Part 2: Generate the routing message ONLY if a doctor has been assigned
    routing_message = ""
    if routed_doctor_name:
        routing_message = f"\n\nThis suggestion has now been forwarded to a real doctor, Dr. {routed_doctor_name}, for review. Please wait for the doctor's approval before taking any action."
    
    # Part 3: Generate the final combined prompt
    final_call_to_action = "You must wait for a doctor's final approval." if routed_doctor_name else "Please consult a doctor for an accurate diagnosis."

    prompt = f'''
    You are a helpful medical assistant chatbot.
    A user has described their symptoms as: "{user_input}".

    Here is the AI's analysis based on their past records:
    ---
    {ai_suggestion_text}
    ---
    {routing_message}

    Your task is to combine this information into a single, clear message for the user.
    1. Present the AI's analysis.
    2. If a routing message exists, present it.
    3. Add a strong disclaimer at the end. The disclaimer's message should be: "{final_call_to_action}"

    Generate a friendly, reassuring, and well-structured response.
    '''

    def api_call():
        if model_type == "gemini":
            response = model.generate_content(prompt)
            return response.text.strip()
        elif model_type == "openai":
            response = model.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a helpful medical assistant chatbot."},
                    {"role": "user", "content": prompt}
                ]
            )
            return response.choices[0].message.content.strip()

    return _call_llm_with_retry(api_call)