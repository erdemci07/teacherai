import json
import firebase_admin
from firebase_admin import credentials

def initialize_firebase(project_id:str|None,service_account_json:str|None, name="[DEFAULT]"):
    try:
        return firebase_admin.get_app(name)
    except ValueError:
        pass
    options={"projectId":project_id} if project_id else None
    if service_account_json:
        credential=credentials.Certificate(json.loads(service_account_json))
        return firebase_admin.initialize_app(credential,options,name=name)
    return firebase_admin.initialize_app(options=options,name=name)

class FirestoreConnection:
    def collection(self, name):
        from firebase_admin import firestore
        return firestore.client().collection(name)

    def transaction(self, **kwargs):
        from firebase_admin import firestore
        return firestore.client().transaction(**kwargs)

    def batch(self):
        from firebase_admin import firestore
        return firestore.client().batch()

    def get_all(self, refs):
        from firebase_admin import firestore
        return firestore.client().get_all(refs)
