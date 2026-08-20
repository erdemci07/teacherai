import {currentToken} from '../auth/AuthProvider';
import type { VisionAnalysis } from './vision-api';
export interface Expression { type:string; latex:string }
export interface Step { id:string;type:string;title:string;explanation:string;expressions:Expression[];visual_reference:string|null }
export interface LessonPlan { lesson_plan_id:string;source_analysis:VisionAnalysis;learning_objectives:string[];concept_id:string;content:{question_understanding:string;known_values:string[];unknown:string|null;prerequisite_reminder:string|null;key_rule:string|null;strategy:string;strategy_id:string;steps:Step[];common_mistake:string|null;mistake_type:string|null;shortcut:string|null;mini_example:Expression[];teacher_tip:string|null;final_answer:string;final_answer_expressions:Expression[];takeaway:string};provider:string;model:string;lesson_generation_ms:number }
export interface VerificationCheck { id:string;kind:string;status:'passed'|'failed'|'unsupported';statement:string;detail:string|null }
export interface GraphData { expression:string;roots:number[];y_intercept:number|null;critical_points:number[];sample_points:[number,number][] }
export interface VerificationResult { status:'verified'|'partially_verified'|'unsupported'|'failed';confidence:number;checks:VerificationCheck[];final_answer_verified:boolean;contradiction:boolean;warnings:string[];engine:string;engine_version:string;graph:GraphData|null;processing_time_ms:number }
export interface BoardElement { id:string;type:string;text:string|null;latex:string|null;mark:'none'|'check'|'cross'|'warning';source_step_id:string|null;graph:GraphData|null;shape:string|null }
export interface BoardPlan { schema_version:string;board_id:string;lesson_plan_id:string;title:string;elements:BoardElement[] }
export interface GeneratedLesson { lesson:LessonPlan;verification:VerificationResult;board:BoardPlan;correction_attempted:boolean;total_processing_ms:number }
export class LessonApiError extends Error { constructor(public code:string){super(code)} }
const BASE=process.env.NEXT_PUBLIC_API_BASE_URL??process.env.NEXT_PUBLIC_TEACHERAI_API_BASE_URL??'http://localhost:8000/api/v1';
export async function generateLesson(analysis:VisionAnalysis):Promise<GeneratedLesson>{
 const controller=new AbortController();const timer=setTimeout(()=>controller.abort(),90000);
 try{const token=await currentToken();const response=await fetch(`${BASE}/lessons/generate`,{method:'POST',headers:{'Content-Type':'application/json',...(token?{Authorization:`Bearer ${token}`}:{})},body:JSON.stringify({analysis}),signal:controller.signal});const body=await response.json();if(!response.ok)throw new LessonApiError(body.error??'lesson_error');return body.data}
 catch(error){if(error instanceof LessonApiError)throw error;if(error instanceof DOMException&&error.name==='AbortError')throw new LessonApiError('lesson_timeout');throw new LessonApiError('network_error')}finally{clearTimeout(timer)}
}
