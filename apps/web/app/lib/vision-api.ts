import {currentToken} from '../auth/AuthProvider';
export type Difficulty = 'easy' | 'medium' | 'hard' | 'unknown';

export interface VisualElements {
  has_diagram: boolean;
  has_graph: boolean;
  has_table: boolean;
  has_geometry_figure: boolean;
  description: string | null;
}

export type ImageStatus = 'valid_math_question' | 'not_math_question' | 'unreadable' | 'incomplete_question';

export interface VisionAnalysis {
  image_status: ImageStatus;
  is_valid_question: boolean;
  rejection_reason: string | null;
  request_id: string;
  subject: string;
  exam_context: string | null;
  topic: string;
  subtopic: string | null;
  question_type: string;
  language: string;
  difficulty: Difficulty;
  question_text: string;
  mathematical_expressions: string[];
  answer_choices: string[];
  visual_elements: VisualElements;
  ocr_uncertainties: string[];
  confidence: number;
  provider: string;
  model: string;
  processing_time_ms: number;
  normalized_preview_url: string | null;
  debug: Record<string, string> | null;
}

interface ApiResponse<T> {
  success: boolean;
  data: T;
  request_id?: string;
}

interface ApiErrorResponse {
  success: false;
  error: string;
  detail?: string;
  request_id?: string;
}

export interface NormalizedImagePreview {
  image_id: string;
  format: 'png';
  content_type: 'image/png';
  width: number;
  height: number;
  preview: string;
  expires_at: string;
}

export class VisionApiError extends Error {
  constructor(public readonly code: string, public readonly status?: number) {
    super(code);
    this.name = 'VisionApiError';
  }
}

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ??
  process.env.NEXT_PUBLIC_TEACHERAI_API_BASE_URL ??
  'http://localhost:8000/api/v1';

export function analyzeQuestionImage(
  image: File,
  onUploadComplete: () => void,
  preparedImage?: NormalizedImagePreview | null,
  timeoutMs = 60_000,
): Promise<VisionAnalysis> {
  return new Promise(async (resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open('POST', `${API_BASE_URL}/vision/analyze`);
    request.timeout = timeoutMs;
    const token = await currentToken();
    if (token) request.setRequestHeader('Authorization', `Bearer ${token}`);
    request.responseType = 'json';
    request.upload.addEventListener('load', onUploadComplete);
    request.addEventListener('load', () => {
      const body = request.response as ApiResponse<VisionAnalysis> | ApiErrorResponse | null;
      if (request.status >= 200 && request.status < 300 && body && 'data' in body) {
        resolve(body.data);
        return;
      }
      const code = body && 'error' in body ? body.error : 'unexpected_response';
      reject(new VisionApiError(code, request.status));
    });
    request.addEventListener('error', () => reject(new VisionApiError('network_error')));
    request.addEventListener('timeout', () => reject(new VisionApiError('request_timeout')));

    const form = new FormData();
    if (preparedImage) {
      form.append('prepared_image_id', preparedImage.image_id);
      form.append('prepared_image_data_url', preparedImage.preview);
    } else {
      form.append('image', image);
    }
    request.send(form);
  });
}

export async function prepareImagePreview(image: File, signal?: AbortSignal): Promise<NormalizedImagePreview> {
  const form = new FormData();
  form.append('image', image);
  const headers = new Headers();
  const token = await currentToken();
  if (token) headers.set('Authorization', `Bearer ${token}`);
  const response = await fetch(`${API_BASE_URL}/vision/preview`, { method: 'POST', body: form, headers, signal });
  const body = (await response.json()) as ApiResponse<NormalizedImagePreview> | ApiErrorResponse;
  if (response.ok && 'data' in body) return body.data;
  const code = 'error' in body ? body.error : 'unexpected_response';
  throw new VisionApiError(code, response.status);
}
