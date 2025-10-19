
import firebase_client
import llm_client

# Global variables to hold the initialized clients
model = None
model_type = ''

def initialize_clients():
    """
    Initializes the Firebase and LLM clients and stores them in global variables.
    """
    global model, model_type
    try:
        firebase_client.initialize_firebase()
        model, model_type = llm_client.configure_llm()
        print("Firebase and LLM clients initialized successfully.")
    except (ValueError, FileNotFoundError) as e:
        print(f"Error during initialization: {e}")
        raise

def _format_response_to_string(response_data):
    """
    Formats the response data into a single string.
    """
    if isinstance(response_data, dict):
        # Assuming keys like 'summary' and 'medicine'
        summary = response_data.get('summary', '')
        medicine = response_data.get('medicine', '')
        return f"{summary}\n{medicine}"
    elif isinstance(response_data, str):
        return response_data
    else:
        return str(response_data)

import time
def get_chatbot_response(patient_id, user_input):
    time.sleep(1) # Add a 1-second delay to avoid hitting the API rate limit
    """
    Handles the core chatbot logic for a single user input.

    Args:
        patient_id (str): The ID of the patient.
        user_input (str): The user's message/symptoms.

    Returns:
        str: The chatbot's response message.
    """
    if not model or not model_type:
        return "Error: Clients are not initialized. Please run initialize_clients() first."

    # 1. Red Flag Check
    if llm_client.check_for_red_flags(model, model_type, user_input):
        return ("**EMERGENCY WARNING**...\n" 
                "Based on your symptoms, you may require immediate medical attention.\n" 
                "Please contact your local emergency services or go to the nearest hospital right away.")

    # 2. Fetch patient history
    patient_appointments = firebase_client.get_patient_appointments_by_id(patient_id)

    # 3. Find best match from history
    matched_appointment = llm_client.find_best_match(model, model_type, user_input, patient_appointments)

    # 4. Main Logic Branching
    if matched_appointment:
        # --- IF A MATCH IS FOUND: ROUTE TO DOCTOR ---
        history_doctor_name = None
        staff_id = matched_appointment.get('staffId')
        if staff_id:
            history_doctor_name = firebase_client.get_doctor_name(staff_id)

        specialty = llm_client.get_specialty_for_symptoms(model, model_type, user_input)
        
        routed_doctor_id, routed_doctor_name = None, None
        if specialty:
            routed_doctor_id, routed_doctor_name = firebase_client.find_doctor_by_specialty(specialty)

        final_response = llm_client.generate_combined_response(
            model=model, 
            model_type=model_type, 
            user_input=user_input, 
            matched_appointment=matched_appointment, 
            history_doctor_name=history_doctor_name,
            routed_doctor_name=routed_doctor_name
        )
        
        if routed_doctor_id:
            ai_suggestion_for_db = llm_client.generate_combined_response(model, model_type, user_input, matched_appointment, history_doctor_name, None)
            firebase_client.create_pending_approval(
                patient_id=patient_id,
                doctor_id=routed_doctor_id,
                symptoms=user_input,
                ai_output=_format_response_to_string(ai_suggestion_for_db)
            )
        
        return _format_response_to_string(final_response)

    else:
        # --- IF NO MATCH IS FOUND: TELL USER TO CONSULT DOCTOR ---
        final_response = llm_client.generate_combined_response(
            model=model, 
            model_type=model_type, 
            user_input=user_input, 
            matched_appointment=None, 
            history_doctor_name=None,
            routed_doctor_name=None
        )
        return _format_response_to_string(final_response)

def main():
    """
    Main function to run the chatbot in command-line mode.
    """
    try:
        initialize_clients()
    except Exception:
        return # Exit if initialization fails

    print("\n--- MedBot ---")

    patient_id = input("Please enter your Patient ID to retrieve your records: ")
    if not patient_id.strip():
        print("A valid Patient ID is required. Exiting.")
        return

    print("\nFetching your past medical records...")
    patient_appointments = firebase_client.get_patient_appointments_by_id(patient_id)
    
    patient_name = ""
    if not patient_appointments:
        print("I couldn't find any past records for your Patient ID.")
        patient_name = "User"
    else:
        print(f"Found {len(patient_appointments)} past appointment(s) in your file.")
        patient_name = patient_appointments[0].get("patientName", "User")
    
    print(f"Hello, {patient_name}! How can I help you today?")
    print("You can describe your symptoms in any language. Type 'quit' to exit.")

    while True:
        user_input = input("\nYou: ")
        if user_input.lower() == 'quit':
            print("Goodbye! Stay healthy.")
            break

        if not user_input.strip():
            continue

        print("Chatbot: Analyzing symptoms...")
        response = get_chatbot_response(patient_id, user_input)
        print(f"\nChatbot: {response}")

if __name__ == "__main__":
    main()
