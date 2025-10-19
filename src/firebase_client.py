
import os
import firebase_admin
from firebase_admin import credentials, firestore
from dotenv import load_dotenv

db = None

def initialize_firebase():
    """
    Initializes the Firebase Admin SDK. Skips initialization if already done.
    """
    global db
    if not firebase_admin._apps:
        load_dotenv()
        service_account_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")
        
        if not service_account_path:
            raise ValueError("FIREBASE_SERVICE_ACCOUNT_JSON path not found in .env file.")
            
        if not os.path.exists(service_account_path):
            raise FileNotFoundError(f"Firebase service account key not found at path: {service_account_path}")

        cred = credentials.Certificate(service_account_path)
        firebase_admin.initialize_app(cred)
        print("Firebase initialized successfully.")
    db = firestore.client()

def find_doctor_by_specialty(specialty):
    """
    Finds a doctor in the 'users' collection with a given specialty.
    Returns the doctor's ID and fullname.
    """
    if not specialty or not db:
        return None, None
    
    try:
        # Query the 'users' collection for a doctor with the given specialization
        users_ref = db.collection('users')
        # Assuming doctors are identified by a role or some other field.
        # For now, we will just search for the specialization.
        query = users_ref.where('specialization', '==', specialty).limit(1)
        docs = query.stream()

        for doc in docs:
            # Return the first doctor found
            return doc.id, doc.to_dict().get("fullname")
        
        return None, None # No doctor found for the specialty
    except Exception as e:
        print(f"An error occurred while finding a doctor: {e}")
        return None, None

def create_pending_approval(patient_id, doctor_id, symptoms, ai_output):
    """
    Creates a new record in the 'pending_approval' collection.
    """
    if not db:
        return None
    
    try:
        approval_ref = db.collection('pending_approval').document()
        approval_data = {
            'patientId': patient_id,
            'doctorId': doctor_id,
            'symptoms': symptoms,
            'aiOutput': ai_output,
            'status': 'pending',
            'timestamp': firestore.SERVER_TIMESTAMP
        }
        approval_ref.set(approval_data)
        print(f"Successfully created pending approval record: {approval_ref.id}")
        return approval_ref.id
    except Exception as e:
        print(f"An error occurred while creating pending approval: {e}")
        return None

def get_doctor_name(staff_id):
    """
    Finds the doctor's name using a 3-step lookup from the staffId.
    """
    # [This function remains unchanged]
    if not staff_id or not db:
        return None

    try:
        staff_ref = db.collection('staff').document(staff_id)
        staff_doc = staff_ref.get()
        if not staff_doc.exists:
            return None

        staff_data = staff_doc.to_dict()
        doctor_id = staff_data.get('assignedDoctorId')
        if not doctor_id:
            return None

        doctor_ref = db.collection('users').document(doctor_id)
        doctor_doc = doctor_ref.get()
        if not doctor_doc.exists:
            return None

        doctor_data = doctor_doc.to_dict()
        return doctor_data.get('fullname')

    except Exception as e:
        print(f"An error occurred while fetching doctor name: {e}")
        return None

def get_patient_appointments_by_id(patient_id):
    """
    Searches for all appointments for a specific patient using their ID.
    """
    # [This function remains unchanged]
    if not db:
        initialize_firebase()
        
    appointments_ref = db.collection('appointment_data')
    query = appointments_ref.where('patientId', '==', patient_id)
    
    try:
        docs = query.stream()
        results = []
        for doc in docs:
            doc_data = doc.to_dict()
            doc_data['doc_id'] = doc.id
            results.append(doc_data)
        return results
    except Exception as e:
        print(f"An error occurred while searching appointments: {e}")
        return []
