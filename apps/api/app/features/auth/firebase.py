import json,os
import firebase_admin
from firebase_admin import credentials

def initialize_firebase(project_id:str|None,service_account_json:str|None):
    if firebase_admin._apps:return firebase_admin.get_app()
    options={"projectId":project_id} if project_id else None
    if service_account_json:
        credential=credentials.Certificate(json.loads(service_account_json))
        return firebase_admin.initialize_app(credential,options)
    return firebase_admin.initialize_app(options=options)
