import os
import firebase_admin
from firebase_admin import credentials, firestore
import pandas as pd

# Global variable for the database client
db = None

def initialize_firebase():
    """
    Initializes the Firebase client.
    This new method is more robust and works both on Render and locally.
    """
    global db
    try:
        # Naya, behtar tareeka:
        # Yeh line automatically Render par 'google_credentials.json' dhoondh legi.
        # Agar woh nahi milta, to yeh error dega aur hum local file try karenge.
        cred = credentials.ApplicationDefault()
        print("Initializing Firebase using Application Default Credentials (for Render)...")
        # Project ID environment variable se aayega
        project_id = os.environ.get('FIREBASE_PROJECT_ID')
        firebase_admin.initialize_app(cred, {
            'projectId': project_id, 
        })
        
    except Exception as e:
        print(f"Could not use Application Default Credentials ({e}). Falling back to local key file...")
        try:
            # Local computer ke liye fallback
            local_path = 'serviceAccountKey.json'
            cred = credentials.Certificate(local_path)
            firebase_admin.initialize_app(cred)
            print(f"Initializing Firebase from local file: {local_path}...")
        except Exception as local_e:
            print(f"FATAL: Error initializing Firebase from both sources: {local_e}")
            raise local_e

    db = firestore.client()
    print("Firebase initialized successfully.")


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
    """Finds an available doctor matching a given specialty."""
    if not db or not specialty: return None, None
    try:
        staffs_ref = db.collection('staffs').where('role', '==', 'Doctor').stream()
        doctors_list = [doc.to_dict() for doc in staffs_ref]
        if not doctors_list:
            print("No doctors found in 'staffs' collection.")
            return None, None
        doctors_df = pd.DataFrame(doctors_list)
        matching_doctors = doctors_df[doctors_df['specialization'].str.lower() == specialty.lower()]
        if not matching_doctors.empty:
            doctor = matching_doctors.iloc[0]
            doctor_id = doctor.get('staffId')
            doctor_name = doctor.get('name')
            print(f"Found matching doctor: {doctor_name} for specialty: {specialty}")
            return doctor_id, doctor_name
        else:
            print(f"No doctor found for specialty: {specialty}")
            return None, None
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

