/** DTOs mirrored from the Django REST API (see backend apps serializers). */

export type Language = "ru" | "ky";
export type Role = "student" | "parent" | "admin" | "teacher";

export type AvatarKey =
  | "fox"
  | "owl"
  | "cat"
  | "panda"
  | "robot"
  | "rocket"
  | "star"
  | "dino"
  | "whale"
  | "bee";

export interface ApiErrorPayload {
  error: {
    code: string;
    message: string;
    details?: Record<string, unknown> | string[];
    request_id?: string;
    retry_after?: number;
  };
}

export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface AppMeta {
  environment: string;
  demo_mode: boolean;
  ai_provider: string;
  languages: Language[];
  upload: { max_image_mb: number; max_images: number; accepted_types: string[] };
  consent_version: string;
}

export interface Grade {
  id: number;
  number: number;
  name: string;
  stage: "primary" | "middle" | "senior";
}

export interface CurriculumBrief {
  id: number;
  code: string;
  name: string;
  country: string;
}

export interface Curriculum extends CurriculumBrief {
  grades: Grade[];
}

export interface Family {
  id: string;
  name: string;
  code: string;
  display_code: string;
  code_rotated_at: string;
}

export interface StudentProfile {
  id: string;
  nickname: string;
  avatar: AvatarKey;
  grade: Grade;
  curriculum: CurriculumBrief;
  /** One language for everything: interface, explanations and the recognition hint. */
  language: Language;
  onboarding_completed: boolean;
  /** Parental controls (enforced by the backend). */
  share_conversations_with_parent: boolean;
  allow_photo_upload: boolean;
  allow_free_questions: boolean;
  is_active: boolean;
  created_at: string;
}

export interface ParentProfile {
  id: string;
  family: Family;
  country: string;
  notify_weekly_report: boolean;
  notify_email: boolean;
  children_count: number;
}

export interface User {
  id: string;
  role: Role;
  display_name: string;
  email?: string;
  preferred_language: Language;
  student: StudentProfile | null;
  parent: ParentProfile | null;
}

export interface AuthResponse {
  access: string;
  user: User;
}

export interface ChildPublic {
  id: string;
  nickname: string;
  avatar: AvatarKey;
  grade_number: number;
}

export interface ChildLookupResponse {
  family: { display_code: string };
  children: ChildPublic[];
}

export type SubjectStrategy =
  | "math"
  | "native_language"
  | "foreign_language"
  | "literature"
  | "humanities"
  | "science"
  | "informatics"
  | "other";

export interface Subject {
  id: number;
  slug: string;
  name: string;
  icon: string;
  color: "lime" | "teal" | "sage" | "ivory" | string;
  strategy: SubjectStrategy;
  grade_from: number;
  grade_to: number;
  topics_count: number;
}

export type ProgressStatus = "not_started" | "learning" | "completed" | "needs_review" | "mastered";

export interface Topic {
  id: number;
  slug: string;
  name: string;
  description: string;
  order: number;
  difficulty: 1 | 2 | 3;
  progress_status: ProgressStatus;
}

export interface TopicProgress {
  sessions_count: number;
  attempts_count: number;
  correct_count: number;
  hints_count: number;
  last_activity_at: string | null;
}

export interface LastQuiz {
  id: string;
  correct_count: number;
  total_count: number;
  score: number;
  finished_at: string | null;
}

export interface TopicDetail extends Topic {
  subject: Subject;
  section: { id: number; name: string };
  grade: { id: number; number: number };
  progress: TopicProgress | null;
  last_quiz: LastQuiz | null;
  recent_sessions: SessionSummary[];
}

export interface TopicBrief {
  id: number;
  slug: string;
  name: string;
}

export interface Section {
  id: number;
  slug: string;
  name: string;
  order: number;
  topics: Topic[];
}

export interface SubjectDetail extends Subject {
  grade: Grade;
  sections: Section[];
}

export type SessionStatus = "active" | "completed" | "abandoned";
export type SessionOutcome = "" | "independent" | "with_help" | "needs_review" | "not_completed";
export type SessionMode = "homework" | "question" | "explain_topic" | "check_answer" | "exam_prep" | "practice";

export interface SessionSummary {
  id: string;
  title: string;
  mode: SessionMode;
  mode_label: string;
  status: SessionStatus;
  status_label: string;
  outcome: SessionOutcome;
  outcome_label: string;
  subject: Subject | null;
  topic_name: string | null;
  topic_id: number | null;
  assignment_id: string | null;
  assignment_text: string | null;
  hints_used: number;
  attempts_count: number;
  correct_attempts: number;
  is_independent: boolean;
  created_at: string;
  last_activity_at: string;
  ended_at: string | null;
}

export interface SessionState {
  id: string;
  status: SessionStatus;
  status_label: string;
  outcome: SessionOutcome;
  outcome_label: string;
  hints_used: number;
  explanations_count: number;
  attempts_count: number;
  correct_attempts: number;
  solution_revealed: boolean;
  understood_points: string[];
  mistakes_fixed: string[];
  ended_at: string | null;
  last_activity_at: string;
}

export type QuickCommand =
  | "start"
  | "simpler"
  | "example"
  | "why"
  | "hint"
  | "repeat"
  | "dont_understand"
  | "similar"
  | "next_step"
  | "";

export type AnswerKind = "number" | "expression" | "text" | "choice" | "none";

export interface TutorStep {
  title: string;
  content: string;
}

export type Verdict = "correct" | "partial" | "incorrect" | "uncertain";

export interface MessagePayload {
  steps?: TutorStep[];
  check_question?: string;
  expected_answer?: string | null;
  answer_kind?: AnswerKind;
  rubric?: string[];
  reveals_solution?: boolean;
  uncertainty_note?: string;
  suggested_commands?: string[];
  off_topic?: boolean;
  verdict?: Verdict;
  confidence?: number;
  method?: string;
  next_hint?: string;
}

export interface AIMessage {
  id: string;
  role: "user" | "assistant" | "system";
  command: string;
  content: string;
  payload: MessagePayload;
  flagged: boolean;
  created_at: string;
}

export interface SolutionStep {
  id: string;
  order: number;
  title: string;
  content: string;
  is_hint: boolean;
  revealed_at: string;
}

export interface Verification {
  method: "sympy" | "numeric" | "exact" | "rubric" | "model" | "demo";
  method_label: string;
  verdict: Verdict;
  verdict_label: string;
  confidence: number;
  feedback: string;
}

export interface AnswerAttempt {
  id: string;
  attempt_number: number;
  answer_text: string;
  hints_before: number;
  is_independent: boolean;
  verification: Verification | null;
  created_at: string;
}

export interface UploadImage {
  id: string;
  order: number;
  width: number;
  height: number;
  available: boolean;
}

export type AssignmentStatus = "recognized" | "confirmed" | "in_progress" | "completed" | "needs_review" | "abandoned";

export interface TaskBrief {
  id: string;
  index_in_upload: number;
  label: string;
  text: string;
  excerpt: string;
  subject: Subject | null;
  topic: TopicBrief | null;
  status: AssignmentStatus;
  status_label: string;
  session_id: string | null;
}

export type UploadStatus = "pending" | "processing" | "recognized" | "unreadable" | "failed";

export interface Upload {
  id: string;
  status: UploadStatus;
  status_label: string;
  source: "camera" | "gallery" | "text";
  typed_text: string;
  error_code: string;
  error_message: string;
  demo_mode: boolean;
  images: UploadImage[];
  tasks: TaskBrief[];
  created_at: string;
  processed_at: string | null;
}

export interface AssignmentDetail {
  id: string;
  label: string;
  recognized_text: string;
  confirmed_text: string;
  text: string;
  text_edited: boolean;
  status: AssignmentStatus;
  status_label: string;
  subject: Subject | null;
  topic: TopicBrief | null;
  grade: Grade;
  detection: Record<string, unknown>;
  language: Language;
  upload_id: string | null;
  images: UploadImage[];
  siblings: TaskBrief[];
  session_id: string | null;
  created_at: string;
  confirmed_at: string | null;
  completed_at: string | null;
}

export interface SessionAssignment {
  id: string;
  label: string;
  text: string;
  status: AssignmentStatus;
  images: UploadImage[];
  upload_id: string | null;
}

export interface SessionDetail extends SessionSummary {
  language: Language;
  state: SessionState;
  messages: AIMessage[];
  steps: SolutionStep[];
  attempts: AnswerAttempt[];
  assignment: SessionAssignment | null;
  siblings: TaskBrief[];
  suggested_commands: string[];
  check_question: string;
  answer_kind: AnswerKind;
  demo_mode: boolean;
}

export interface CheckAnswerResponse {
  attempt: AnswerAttempt;
  message: AIMessage;
  session: SessionState;
  /** Set when a correct intermediate step should auto-continue the walk-through. */
  continue_with: "next_step" | null;
}

export interface Dashboard {
  student: StudentProfile;
  demo_mode: boolean;
  continue_session: SessionSummary | null;
  recent_sessions: SessionSummary[];
  subjects: Subject[];
  stats: {
    sessions_total: number;
    completed_total: number;
    week_sessions: number;
    week_independent: number;
  };
}

// ---------------------------------------------------------------------------
// Parent cabinet
// ---------------------------------------------------------------------------
export interface SubjectBrief {
  id: number;
  slug: string;
  name: string;
  icon: string;
  color: string;
}

export interface DifficultTopic {
  topic_id: number;
  name: string;
  status: ProgressStatus;
  subject: SubjectBrief | null;
  attempts_count?: number;
  hints_count?: number;
  last_activity_at?: string | null;
}

export interface ChildSummary {
  sessions_total: number;
  completed_total: number;
  sessions_week: number;
  completed_week: number;
  independent_week: number;
  with_help_week: number;
  needs_review_week: number;
  independent_total: number;
  quizzes_week: number;
  last_activity_at: string | null;
  difficult_topics: DifficultTopic[];
}

export interface ParentOverview {
  children: Array<{ child: StudentProfile; summary: ChildSummary }>;
  unread_notifications: number;
  family_code: string;
}

export interface SubjectBreakdown {
  subject: SubjectBrief;
  sessions: number;
  completed: number;
  independent: number;
  with_help: number;
  needs_review: number;
  hints_avg: number;
  last_activity_at: string | null;
  topics: Partial<Record<ProgressStatus, number>>;
}

export interface WeeklyReport {
  period_start: string;
  period_end: string;
  sessions: number;
  independent: number;
  with_help: number;
  needs_review: number;
  has_data: boolean;
  text: string;
  highlights: string[];
}

export type RecommendationAction =
  | { type: "explain_topic"; topic_id: number; subject_slug: string }
  | { type: "subject"; subject_slug: string }
  | { type: "session"; session_id: string }
  | { type: "photo" };

export interface Recommendation {
  kind: "review_topic" | "review_session" | "too_many_reveals" | "doing_great" | "inactive" | "subject_needs_support";
  title: string;
  text: string;
  action: RecommendationAction | null;
}

export interface ChildProgress {
  child: StudentProfile;
  summary: ChildSummary;
  subjects: SubjectBreakdown[];
  difficult_topics: DifficultTopic[];
  weekly_report: WeeklyReport;
  recommendations: Recommendation[];
  recent_sessions: SessionSummary[];
  recent_quizzes: RecentQuiz[];
}

export interface ParentSessionDetail extends SessionDetail {
  conversation_visible: boolean;
  summary_for_parent: string;
}

export type NotificationKind = "weekly_report" | "difficult_topic" | "session_completed" | "consent" | "system";

export interface ParentNotification {
  id: string;
  kind: NotificationKind;
  kind_label: string;
  title: string;
  body: string;
  data: Record<string, unknown>;
  student_id: string | null;
  student_nickname: string | null;
  read_at: string | null;
  created_at: string;
}

export type ConsentType = "terms" | "privacy" | "child_data" | "ai_processing" | "marketing";

export interface ConsentRecord {
  id: string;
  consent_type: ConsentType;
  consent_type_label: string;
  student_id: string | null;
  version: string;
  granted: boolean;
  granted_at: string;
  revoked_at: string | null;
}

export interface FamilySettings {
  notify_weekly_report: boolean;
  notify_email: boolean;
  country: string;
  /** The parent's single language: interface and reports. */
  preferred_language: Language;
}

export interface PushConfig {
  enabled: boolean;
  public_key: string | null;
  devices: number;
  /** Whether the endpoint whose SHA-256 was passed as `?endpoint_hash=` belongs to the current parent. */
  subscribed: boolean;
}

// ---------------------------------------------------------------------------
// Knowledge map & quizzes
// ---------------------------------------------------------------------------
export interface MapNode {
  topic_id: number;
  slug: string;
  name: string;
  section: { id: number; name: string };
  order: number;
  /** Horizontal position on the route, 0–100. */
  x: number;
  icon: string;
  difficulty: 1 | 2 | 3;
  status: ProgressStatus;
  sessions_count: number;
  last_activity_at: string | null;
  last_quiz: Omit<LastQuiz, "id"> | null;
}

export interface KnowledgeMap {
  subject: SubjectBrief & { strategy: SubjectStrategy };
  grade: { id: number; number: number };
  nodes: MapNode[];
  summary: Record<"total" | ProgressStatus, number>;
  next_topic_id: number | null;
}

export type QuestionType = "single" | "multiple" | "numeric" | "text" | "ordering" | "matching";

export interface QuizQuestion {
  id: number;
  order: number;
  type: QuestionType;
  prompt: string;
  options: Array<{ key: string; text: string }>;
  hint: string;
}

export interface QuizResult {
  correct: boolean;
  explanation: string;
  correct_answer: string;
  /** Option keys of the right answer (choice questions); older rows may lack it. */
  correct_keys?: string[];
  checked_at: string;
}

export interface QuizAttempt {
  id: string;
  status: "in_progress" | "finished" | "abandoned";
  mode: "learning" | "test";
  quiz: { id: number; title: string; source: "anthropic" | "gemini" | "rules" | "manual"; language: Language };
  topic: { id: number; name: string; subject: SubjectBrief };
  questions: QuizQuestion[];
  answers: Record<string, string | string[]>;
  results: Record<string, QuizResult>;
  correct_count: number;
  total_count: number;
  score: number;
  topics_to_review: number[];
  progress_status: ProgressStatus | "";
  started_at: string;
  finished_at: string | null;
}

export interface QuizAnswerResponse {
  question_id: number;
  correct: boolean;
  explanation: string;
  correct_answer: string;
  correct_keys?: string[];
  answered: number;
  total: number;
}

export interface RecentQuiz {
  id: string;
  topic_id: number;
  topic_name: string;
  subject: SubjectBrief;
  correct_count: number;
  total_count: number;
  score: number;
  finished_at: string;
}
