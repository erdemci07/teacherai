from collections import defaultdict
from datetime import date
from threading import Lock
class UsageLimitExceeded(Exception):pass
class UsageTracker:
    def __init__(self,daily_limit:int):self.daily_limit=daily_limit;self._counts=defaultdict(int);self._lock=Lock()
    def record(self,uid:str,operation:str)->int:
        key=(uid,date.today().isoformat(),operation)
        with self._lock:
            self._counts[key]+=1
            if self._counts[key]>self.daily_limit:raise UsageLimitExceeded
            return self._counts[key]
