import os
import firebase_admin
from firebase_admin import credentials, firestore
import pandas as pd

# Global variable for the database client
db = None

def initialize_firebase():
    """
    Initializes the Firebase client using credentials.
    Tries to load from a secret file on Render, falls back to a local file.
    """
    global db
    try:
        # This path is automatically set by Render for secret files
        creds_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
        
        if creds_path:
            # Running on Render
            cred = credentials.Certificate(creds_path)
            print("Initializing Firebase from Render secret file...")
        else:
            # Running locally, fallback to the local key file
            local_path = 'serviceAccountKey.json' # Or your local key file name
            cred = credentials.Certificate(local_path)
            print(f"Initializing Firebase from local file: {local_path}...")

        firebase_admin.initialize_app(cred)
        db = firestore.client()
        print("Firebase initialized successfully.")
    except Exception as e:
        print(f"Error initializing Firebase: {e}")
        raise

def get_patient_appointments_by_id(patient_id):
    """Fetches all appointments for a given patient ID."""
    if not db: return []
    appointments_ref = db.collection('appointments').where('patientId', '==', patient_id).stream()
    return [appointment.to_dict() for appointment in appointments_ref]

def get_doctor_name(staff_id):
    """Fetches a doctor's name using their staff ID."""
    if not db: return "a doctor"
    try:
        doc_ref = db.collection('staffs').document(staff_id).get()
        if doc_ref.exists:
            return doc_ref.to_dict().get('name', "a doctor")
    except Exception as e:
        print(f"Error fetching doctor name: {e}")
    return "a doctor"

def find_doctor_by_specialty(specialty):
    """
    Finds an available doctor matching a given specialty.
    **THIS IS THE CORRECTED FUNCTION.**
    """
    if not db or not specialty:
        return None, None
    
    try:
        staffs_ref = db.collection('staffs').where('role', '==', 'Doctor').stream()
        doctors_list = [doc.to_dict() for doc in staffs_ref]
        
        if not doctors_list:
            print("No doctors found in the 'staffs' collection.")
            return None, None
            
        doctors_df = pd.DataFrame(doctors_list)
        
        # --- FIX APPLIED HERE ---
        # Instead of a confusing 'if' statement, we filter the DataFrame.
        # We also convert both to lowercase to avoid case-sensitivity issues ('cardiology' vs 'Cardiology').
        matching_doctors = doctors_df[doctors_df['specialization'].str.lower() == specialty.lower()]

        # Now, we check if the filtered list is empty or not.
        if not matching_doctors.empty:
            # If we found one or more doctors, select the first one.
            doctor = matching_doctors.iloc[0]
            doctor_id = doctor.get('staffId') # Use staffId from the DataFrame
            doctor_name = doctor.get('name')
            print(f"Found matching doctor: {doctor_name} for specialty: {specialty}")
            return doctor_id, doctor_name
        else:
            # If no doctor with that specialty is found.
            print(f"No doctor found for specialty: {specialty}")
            return None, None
        # --- END OF FIX ---

    except Exception as e:
        print(f"An error occurred in find_doctor_by_specialty: {e}")
        return None, None


def create_pending_approval(patient_id, doctor_id, symptoms, ai_output):
    """Creates a record in the 'pendingApprovals' collection."""
    if not db: return None
    try:
        doc_ref = db.collection('pendingApprovals').add({
            'patientId': patient_id,
            'staffId': doctor_id,
            'symptoms': symptoms,
            'aiOutput': ai_output,
            'status': 'Pending',
            'timestamp': firestore.SERVER_TIMESTAMP
        })
        print(f"Successfully created pending approval record: {doc_ref[1].id}")
        return doc_ref[1].id
    except Exception as e:
        print(f"Error creating pending approval: {e}")
        return None
