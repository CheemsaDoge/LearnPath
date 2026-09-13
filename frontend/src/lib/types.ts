export type NodeType = "root" | "module" | "concept" | "practice";
export type GraphStatus = "generating" | "grounding" | "ready" | "failed";

export interface GraphNode {
  id: string;
  graph_id: string;
  label: string;
  description: string;
  node_type: NodeType;
  layer: number;
  order_index: number;
  parent_id: string | null;
  weight: number;
  difficulty: number;
  est_minutes: number;
  grounding_status: "pending" | "done" | "failed" | "skipped";
  mastery_score: number;
  mastery_stars: number;
  attempts: number;
  source_count: number;
  unlocked: boolean;
}

export interface GraphEdge {
  id: string;
  source_id: string;
  target_id: string;
  relation: "contains" | "prerequisite" | "related";
}

export interface NextAction {
  node_id: string;
  label: string;
  reason: string;
  est_minutes: number;
}

export interface GraphStats {
  total_nodes: number;
  learnable_nodes: number;
  mastered_nodes: number;
  started_nodes: number;
  minutes_total: number;
  minutes_remaining: number;
  completion: number;
}

export interface Graph {
  id: string;
  goal_id: string;
  title: string;
  summary: string;
  learner_profile: string;
  status: GraphStatus;
  error: string;
  progress: { step?: string; done?: number; total?: number };
  created_at: string;
  goal_text: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
  stats: GraphStats | null;
  next_actions: NextAction[];
}

export interface Source {
  id: string;
  url: string;
  kind: "question" | "answer" | "article" | "other";
  title: string;
  snippet: string;
  author: string;
  votes: number;
  origin: string;
  has_content: boolean;
}

export interface Citation {
  index: number;
  title: string;
  url: string;
  kind: string;
  source_id: string;
}

export interface Lesson {
  id: string;
  content_md: string;
  citations: Citation[];
  created_at: string;
}

export interface Evidence {
  id: string;
  kind: "quiz" | "lesson" | "chat" | "feynman";
  score: number;
  detail: Record<string, unknown>;
  created_at: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
}

export interface Card {
  front: string;
  back: string;
  source_index: number;
}

export interface NodeDetail extends GraphNode {
  teaching_strategy: string;
  search_queries: string[];
  sources: Source[];
  lesson: Lesson | null;
  evidence: Evidence[];
  chat: ChatMessage[];
  cards: Card[] | null;
  prerequisites: { id: string; label: string; satisfied: boolean }[];
}

export interface QuizQuestion {
  id: string;
  qtype: "single" | "feynman";
  stem: string;
  options: string[];
  source_index: number;
}

export interface Quiz {
  id: string;
  node_id: string;
  questions: QuizQuestion[];
}

export interface QuestionResult {
  id: string;
  qtype: "single" | "feynman";
  correct: boolean | null;
  score: number;
  your_answer: unknown;
  answer_index: number | null;
  explanation: string;
  feedback: string;
}

export interface QuizResult {
  quiz_id: string;
  node_id: string;
  score: number;
  results: QuestionResult[];
  mastery_score: number;
  mastery_stars: number;
  stars_before: number;
  next_actions: NextAction[];
  summary: string;
}

export interface HotItem {
  id: string;
  title: string;
  heat: string;
  excerpt: string;
  url: string;
  answer_count: number;
  follower_count: number;
}

export interface Health {
  status: string;
  llm_provider: string;
  llm_model: string;
  zhihu_search: string[];
  zhihu_official: boolean;
  reader: string;
}

export interface GoalInput {
  goal: string;
  background?: string;
  time_budget?: string;
  purpose?: string;
}
