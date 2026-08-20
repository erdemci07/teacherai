from firebase_admin import firestore
from apps.api.app.features.interactions.schemas import InteractionEvent
from apps.api.app.features.memory.schemas import StudentMemory
from .schemas import LessonRecord,StudentProfile
class FirestoreStudentRepository:
    def __init__(self):self.db=firestore.client()
    def save_profile(self,p):self.db.collection("student_profiles").document(p.student_id).set(p.model_dump(mode="json"),merge=True);self.db.collection("users").document(p.student_id).set({"student_id":p.student_id,"email":p.email},merge=True)
    def get_profile(self,uid):
        snap=self.db.collection("student_profiles").document(uid).get();return StudentProfile.model_validate(snap.to_dict()) if snap.exists else None
    def save_lesson(self,x):self.db.collection("lessons").document(x.lesson_id).set(x.model_dump(mode="json"))
    def lessons(self,uid,limit=50):return [LessonRecord.model_validate(x.to_dict()) for x in self.db.collection("lessons").where("student_id","==",uid).order_by("created_at",direction=firestore.Query.DESCENDING).limit(limit).stream()]
    def save_event(self,uid,event):self.db.collection("interaction_events").document(event.event_id).set({**event.model_dump(mode="json"),"student_id":uid})
    def save_attempt(self,uid,event,practice_id):self.db.collection("practice_attempts").document(event.event_id).set({**event.model_dump(mode="json"),"student_id":uid,"practice_question_id":practice_id})
    def get_memory(self,uid):
        snap=self.db.collection("student_memories").document(uid).get();return StudentMemory.model_validate(snap.to_dict()) if snap.exists else StudentMemory(student_id=uid)
    def save_memory(self,memory):self.db.collection("student_memories").document(memory.student_id).set(memory.model_dump(mode="json"))
    def reset_memory(self,uid):self.db.collection("student_memories").document(uid).delete()
