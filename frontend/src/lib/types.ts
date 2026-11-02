import { z } from 'zod';

export type Language = 'en-HK' | 'zh-HK';
export const citationSchema = z.object({
  chunk_id: z.string(),
  source: z.string(),
  text: z.string(),
});
export const coachTurnSchema = z.object({
  interviewer_text: z.string(),
  question_type: z.enum(['opening', 'behavioral', 'technical', 'follow_up', 'closing']),
  targeted_competencies: z.array(z.string()),
  adaptive_follow_up_reason: z.string().nullable(),
  citations: z.array(citationSchema),
});
export const answerSchema = z.object({
  transcript: z.string(),
  language: z.enum(['en-HK', 'zh-HK']),
  elapsed_seconds: z.number(),
  corrected: z.boolean(),
  turn_id: z.string().nullish(),
  speech_metrics: z
    .object({ pause_count: z.number().nullish(), silence_seconds: z.number().nullish() })
    .nullish(),
});
export const profileSchema = z.object({
  id: z.string(),
  title: z.string(),
  competencies: z.array(z.string()),
  warnings: z.array(z.string()),
  sources: z.array(citationSchema),
});
export const sessionSchema = z.object({
  id: z.string(),
  job_profile_id: z.string(),
  role_title: z.string(),
  language: z.enum(['en-HK', 'zh-HK']),
  difficulty: z.string(),
  question_count: z.number(),
  state: z.string(),
  current_question: z.number(),
  turns: z.array(
    z.object({
      id: z.string(),
      question: coachTurnSchema,
      answer: answerSchema.nullable(),
      created_at: z.string(),
    }),
  ),
  created_at: z.string(),
  provider: z.string(),
});
export const reportSchema = z.object({
  session_id: z.string(),
  role_title: z.string(),
  language: z.string(),
  summary: z.string(),
  star: z.array(
    z.object({
      element: z.enum(['Situation', 'Task', 'Action', 'Result']),
      present: z.boolean(),
      evidence: z.string(),
      coaching: z.string(),
    }),
  ),
  competencies: z.array(
    z.object({
      name: z.string(),
      evidence: z.string(),
      feedback: z.string(),
      citations: z.array(citationSchema),
    }),
  ),
  strengths: z.array(z.string()),
  prioritized_improvement: z.string(),
  retry_exercise: z.string(),
  speech_metrics: z.object({
    word_count: z.number(),
    duration_seconds: z.number(),
    words_per_minute: z.number().nullable(),
    filler_count: z.number(),
    pause_count: z.number().nullable(),
    silence_seconds: z.number().nullable(),
    answer_count: z.number(),
  }),
  citations: z.array(citationSchema),
  limitations: z.array(z.string()),
});
export type Citation = z.infer<typeof citationSchema>;
export type Profile = z.infer<typeof profileSchema>;
export type Answer = z.infer<typeof answerSchema>;
export type Session = z.infer<typeof sessionSchema>;
export type Report = z.infer<typeof reportSchema>;
export type ControlAction = 'pause' | 'resume' | 'skip' | 'retry' | 'end' | 'cancel';
export type Health = {
  status: string;
  database: string;
  llm: string;
  speech: string;
  retrieval: string;
  provider: string;
};
export type Methodology = {
  status: string;
  provider: string;
  training: Record<string, unknown>;
  evaluations: Record<string, unknown>[];
  limitations: string[];
};
