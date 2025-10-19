import sys
import os

# Add the 'src' directory to the Python path
sys.path.insert(0, 'src')

from flask import Flask, request, jsonify
from src.main import get_chatbot_response, initialize_clients

app = Flask(__name__)

# Initialize Firebase and Gemini clients
initialize_clients()

@app.route('/chat', methods=['POST'])
def chat():
    """
    Handles the chat requests from the Flutter app.
    Expects a JSON body with 'patient_id' and 'message'.
    """
    data = request.get_json()
    patient_id = data.get('patient_id')
    message = data.get('message')

    if not patient_id or not message:
        return jsonify({'error': 'Missing patient_id or message'}), 400

    # --- ADDED FOR DEBUGGING ---
    # Print the incoming data to the console to verify it's being received correctly.
    print("-" * 30)
    print(f"[API Request] Received Patient ID: {patient_id}")
    print(f"[API Request] Received Message: {message}")
    print("-" * 30)
    # ---------------------------

    # Get the response from the chatbot logic
    response_data = get_chatbot_response(patient_id, message)
    
    # **SAFEGUARD**: Explicitly convert the response to a string to prevent crashes.
    # The main logic for this is in main.py, but this ensures the API never sends a non-string type.
    final_response_text = str(response_data)
    
    return jsonify({'response': final_response_text})

if __name__ == '__main__':
    # Runs the Flask app on your local network
    app.run(host='0.0.0.0', port=5000)
