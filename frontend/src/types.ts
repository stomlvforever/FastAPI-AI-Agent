export type TokenResponse = {
  access_token: string;
  refresh_token: string;
  token_type: string;
};

export type User = {
  id: number;
  email: string;
  full_name: string | null;
  is_active: boolean;
  role: string;
  created_at: string;
};

export type Tag = {
  id: number;
  name: string;
};

export type Article = {
  id: number;
  title: string;
  slug: string;
  description: string | null;
  body: string;
  author_id: number;
  created_at: string;
  updated_at: string;
  tags: Tag[];
  favorites_count: number;
  favorited: boolean;
};

export type ArticlePayload = {
  title: string;
  description?: string | null;
  body: string;
  tag_names: string[];
};

export type Profile = {
  id: number;
  email: string;
  full_name: string | null;
  bio: string | null;
  image: string | null;
  role: string;
  created_at: string;
};

export type ProfileWithFollow = Profile & {
  following: boolean;
};

export type ProfileUpdatePayload = {
  full_name?: string;
  bio?: string;
  image?: string;
};

export type RegisterPayload = {
  email: string;
  password: string;
  full_name?: string;
};

export type AgentHistoryItem = {
  role: string;
  content: string;
  timestamp?: string | null;
};

export type AgentHistoryResponse = {
  messages: AgentHistoryItem[];
  total: number;
};
