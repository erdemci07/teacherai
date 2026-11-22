import type { LessonView } from './education.generated';
import { requestHeaders } from './request-headers';import type{GeneratedLesson}from'./lesson-api';
const BASE=process.env.NEXT_PUBLIC_API_BASE_URL??process.env.NEXT_PUBLIC_TEACHERAI_API_BASE_URL??'http://localhost:8000/api/v1';
async function request<T>(path:string,init:RequestInit={}):Promise<T>{const headers = await requestHeaders();if(!headers.Authorization)throw new Error('authentication_required');const response=await fetch(`${BASE}${path}`,{...init,headers:{'Content-Type':'application/json',...headers,...init.headers}});if(!response.ok)throw new Error('student_api_error');if(response.status===204)return undefined as T;return(await response.json()).data}
export interface LessonHistory{lesson_id:string;created_at:string;topic:string;subtopic:string|null;exam_context:string|null;difficulty:string;question_summary:string;final_answer:string;verification_status:string;lesson_data:Record<string,unknown>}
export interface Dashboard{questions_solved:number;recent_topics:string[];practice_attempts:number;practice_correct:number;frequent_mistakes:Record<string,number>;last_activity:string|null}
export interface Memory{student_id:string;exam_goal:string|null;topic_counts:Record<string,number>;mistake_counts:Record<string,number>;hint_requests:number;simplification_requests:number;practice:{attempts:number;correct:number;first_attempt_correct:number};recent_topics:string[]}
// TA-005B: ProfileInput.grade ile aynı aralık (5–12, isteğe bağlı). Sınıf sorudan tahmin edilmez.
export const GRADE_OPTIONS=[5,6,7,8,9,10,11,12] as const;
export type GradeValue=(typeof GRADE_OPTIONS)[number];
export interface StudentProfile{student_id:string;display_name:string;exam_goal:string|null;grade:GradeValue|null}
export function parseGrade(value:string):GradeValue|null{const n=Number(value);return (GRADE_OPTIONS as readonly number[]).includes(n)?n as GradeValue:null}
export const profileBody=(display_name:string,exam_goal:string|null,grade:GradeValue|null)=>({display_name,exam_goal,grade});
export const saveProfile=(display_name:string,exam_goal:string|null,grade:GradeValue|null=null)=>request<StudentProfile>('/students/me/profile',{method:'PUT',body:JSON.stringify(profileBody(display_name,exam_goal,grade))});
export const getProfile=()=>request<StudentProfile|null>('/students/me/profile',{cache:'no-store'});
export const saveLesson=(result:GeneratedLesson)=>request('/students/me/lessons',{method:'POST',body:JSON.stringify({lesson_id:result.lesson.lesson_plan_id})});
export const getHistory=()=>request<LessonHistory[]>('/students/me/history');export const getDashboard=()=>request<Dashboard>('/students/me/dashboard');export const getMemory=()=>request<Memory>('/students/me/memory');export const resetMemory=()=>request<void>('/students/me/memory',{method:'DELETE'});

export const getLessonView = (id: string) => request<LessonView>('/lessons/' + encodeURIComponent(id) + '/v2', {cache: 'no-store'});
