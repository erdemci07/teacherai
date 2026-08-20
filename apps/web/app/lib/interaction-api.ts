import{currentToken}from'../auth/AuthProvider';
import type {BoardPlan,LessonPlan} from './lesson-api';
export type InteractionAction='understood'|'simplify'|'alternative'|'hint'|'similar_example'|'practice';
export interface InteractionEvent{event_id:string;event:string;occurred_at:string;student_id:null;lesson_id:string;topic:string;subtopic:string|null;skill:string;difficulty:string;action:string;mistake_type:string|null;correctness:boolean|null;attempt_count:number|null;explanation_mode:string|null}
export interface PracticeQuestion{practice_question_id:string;question:string;question_expression:string;topic:string;subtopic:string|null;skill_id:string;difficulty:string}
export interface InteractionResponse{interaction_id:string;action:InteractionAction;message:string;board:BoardPlan|null;practice:PracticeQuestion|null;event:InteractionEvent;next_hint_level:number|null;verification_status:string|null}
export interface PracticeFeedback{correct:boolean;message:string;attempt_number:number;mistake_type:string;can_show_solution:boolean;event:InteractionEvent}
export class InteractionApiError extends Error{constructor(public code:string){super(code)}}
const BASE=process.env.NEXT_PUBLIC_API_BASE_URL??process.env.NEXT_PUBLIC_TEACHERAI_API_BASE_URL??'http://localhost:8000/api/v1';
async function post<T>(path:string,payload:unknown):Promise<T>{const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),75000);try{const token=await currentToken();const response=await fetch(`${BASE}${path}`,{method:'POST',headers:{'Content-Type':'application/json',...(token?{Authorization:`Bearer ${token}`}:{})},body:JSON.stringify(payload),signal:controller.signal});const body=await response.json();if(!response.ok)throw new InteractionApiError(body.error??'interaction_error');return body.data}catch(error){if(error instanceof InteractionApiError)throw error;throw new InteractionApiError('interaction_provider_unavailable')}finally{clearTimeout(timer)}}
export function interact(lesson:LessonPlan,action:InteractionAction,hintLevel=1){return post<InteractionResponse>(`/lessons/${lesson.lesson_plan_id}/interact`,{action,lesson,hint_level:hintLevel})}
export function submitPractice(lessonId:string,practiceId:string,answer:string){return post<PracticeFeedback>(`/lessons/${lessonId}/practice/${practiceId}/answer`,{answer})}
