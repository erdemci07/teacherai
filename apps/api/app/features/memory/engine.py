from apps.api.app.features.interactions.schemas import InteractionEvent
from .schemas import EvidenceSignal,StudentMemory,TeachingContext
class MemoryEngine:
    def apply(self,memory:StudentMemory,event:InteractionEvent)->StudentMemory:
        memory.topic_counts[event.topic]=memory.topic_counts.get(event.topic,0)+1
        memory.recent_topics=([event.topic]+[x for x in memory.recent_topics if x!=event.topic])[:5]
        if event.mistake_type and event.mistake_type!="unknown":memory.mistake_counts[event.mistake_type]=memory.mistake_counts.get(event.mistake_type,0)+1
        if event.event=="hint_requested":memory.hint_requests+=1
        if event.event=="simpler_explanation_requested":memory.simplification_requests+=1
        if event.event in ("practice_correct","practice_incorrect"):
            memory.practice.attempts+=1;memory.practice.correct+=int(bool(event.correctness));memory.practice.first_attempt_correct+=int(bool(event.correctness) and event.attempt_count==1)
        memory.last_activity=event.occurred_at
        return memory
    def context(self,memory:StudentMemory,topic:str)->TeachingContext:
        recurring=[EvidenceSignal(signal=k,count=v,confidence=min(.95,.35+.1*v)) for k,v in memory.mistake_counts.items() if v>=2]
        support="high" if memory.hint_requests>=3 else "standard"
        depth="foundation" if memory.simplification_requests>=3 else "standard"
        return TeachingContext(exam_goal=memory.exam_goal,topic_experience=memory.topic_counts.get(topic,0),recurring_mistakes=recurring,support_need=support,preferred_explanation_depth=depth,recent_topics=memory.recent_topics)
