from dataclasses import dataclass,field
from datetime import datetime,timezone,timedelta
from threading import Lock
@dataclass
class PracticeRecord:
    practice_id:str;lesson_id:str;question:str;expected_answer:str;variable:str|None;hint:str;topic:str;subtopic:str|None;skill:str;difficulty:str;attempts:int=0;created_at:datetime=field(default_factory=lambda:datetime.now(timezone.utc))
class InMemoryPracticeStore:
    def __init__(self,ttl_minutes:int=60):self._items={};self._lock=Lock();self._ttl=timedelta(minutes=ttl_minutes)
    def save(self,item:PracticeRecord):
        with self._lock:self._items[item.practice_id]=item
    def get(self,practice_id:str,lesson_id:str)->PracticeRecord|None:
        with self._lock:
            item=self._items.get(practice_id)
            if not item or item.lesson_id!=lesson_id:return None
            if datetime.now(timezone.utc)-item.created_at>self._ttl:self._items.pop(practice_id,None);return None
            return item
    def increment(self,item:PracticeRecord)->int:
        with self._lock:item.attempts+=1;return item.attempts
