import type {
  AgentHistoryResponse,
  Article,
  ArticlePayload,
  Profile,
  ProfileUpdatePayload,
  ProfileWithFollow,
  RegisterPayload,
  Tag,
  TokenResponse,
  User,
} from "../types.ts";
import { clearStoredAuth, getStoredAuth, setStoredAuth } from "./storage.ts";

const API_PREFIX = "/api/v1";

type RequestOptions = {
  auth?: boolean;
  retryOnAuth?: boolean;
};

export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

let refreshPromise: Promise<string | null> | null = null;

async function createApiError(response: Response): Promise<ApiError> {
  const contentType = response.headers.get("content-type") ?? "";
  let message = `Request failed with status ${response.status}`;

  try {
    if (contentType.includes("application/json")) {
      const payload = (await response.json()) as { detail?: string; message?: string };
      message = payload.detail ?? payload.message ?? message;
    } else {
      const text = await response.text();
      if (text.trim()) {
        message = text;
      }
    }
  } catch {
    // Keep fallback message.
  }

  return new ApiError(message, response.status);
}

async function refreshAccessToken(): Promise<string | null> {
  if (refreshPromise) {
    return refreshPromise;
  }

  refreshPromise = (async () => {
    const stored = getStoredAuth();
    if (!stored?.refreshToken) {
      return null;
    }

    const response = await fetch(`${API_PREFIX}/auth/refresh`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        refresh_token: stored.refreshToken,
      }),
    });

    if (!response.ok) {
      clearStoredAuth();
      return null;
    }

    const tokens = (await response.json()) as TokenResponse;
    setStoredAuth({
      accessToken: tokens.access_token,
      refreshToken: tokens.refresh_token,
    });
    return tokens.access_token;
  })().finally(() => {
    refreshPromise = null;
  });

  return refreshPromise;
}

async function authorizedFetch(
  path: string,
  init: RequestInit = {},
  options: RequestOptions = {},
): Promise<Response> {
  const headers = new Headers(init.headers);
  const useAuth = options.auth !== false;
  const retryOnAuth = options.retryOnAuth !== false;

  if (init.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  if (useAuth) {
    const stored = getStoredAuth();
    if (stored?.accessToken) {
      headers.set("Authorization", `Bearer ${stored.accessToken}`);
    }
  }

  const response = await fetch(`${API_PREFIX}${path}`, {
    ...init,
    headers,
  });

  if (response.status === 401 && useAuth && retryOnAuth) {
    const nextAccessToken = await refreshAccessToken();
    if (nextAccessToken) {
      headers.set("Authorization", `Bearer ${nextAccessToken}`);
      return fetch(`${API_PREFIX}${path}`, {
        ...init,
        headers,
      });
    }
  }

  return response;
}

async function requestJson<T>(
  path: string,
  init: RequestInit = {},
  options: RequestOptions = {},
): Promise<T> {
  const response = await authorizedFetch(path, init, options);

  if (!response.ok) {
    throw await createApiError(response);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  const contentType = response.headers.get("content-type") ?? "";
  if (contentType.includes("application/json")) {
    return (await response.json()) as T;
  }

  return undefined as T;
}

function withQuery(path: string, params: Record<string, string | number | undefined>): string {
  const searchParams = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") {
      searchParams.set(key, String(value));
    }
  }

  const queryString = searchParams.toString();
  return queryString ? `${path}?${queryString}` : path;
}

export const authApi = {
  async login(email: string, password: string): Promise<TokenResponse> {
    const body = new URLSearchParams({
      username: email,
      password,
    });

    return requestJson<TokenResponse>(
      "/auth/login",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
        },
        body,
      },
      { auth: false, retryOnAuth: false },
    );
  },
};

export const usersApi = {
  getCurrentUser(): Promise<User> {
    return requestJson<User>("/users/me");
  },

  register(payload: RegisterPayload): Promise<User> {
    return requestJson<User>(
      "/users",
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
      { auth: false, retryOnAuth: false },
    );
  },
};

export const tagsApi = {
  list(): Promise<Tag[]> {
    return requestJson<Tag[]>("/tags", undefined, { auth: false });
  },
};

export const articlesApi = {
  list(params: { tag?: string; authorId?: number; skip?: number; limit?: number }): Promise<Article[]> {
    return requestJson<Article[]>(
      withQuery("/articles", {
        tag: params.tag,
        author_id: params.authorId,
        skip: params.skip,
        limit: params.limit,
      }),
    );
  },

  get(slug: string): Promise<Article> {
    return requestJson<Article>(`/articles/${slug}`);
  },

  create(payload: ArticlePayload): Promise<Article> {
    return requestJson<Article>("/articles", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  update(slug: string, payload: ArticlePayload): Promise<Article> {
    return requestJson<Article>(`/articles/${slug}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    });
  },

  remove(slug: string): Promise<Article> {
    return requestJson<Article>(`/articles/${slug}`, {
      method: "DELETE",
    });
  },

  favorite(slug: string): Promise<Article> {
    return requestJson<Article>(`/articles/${slug}/favorite`, {
      method: "POST",
    });
  },

  unfavorite(slug: string): Promise<Article> {
    return requestJson<Article>(`/articles/${slug}/favorite`, {
      method: "DELETE",
    });
  },

  feed(): Promise<Article[]> {
    return requestJson<Article[]>("/feed");
  },
};

export const profilesApi = {
  getMine(): Promise<Profile> {
    return requestJson<Profile>("/profile");
  },

  updateMine(payload: ProfileUpdatePayload): Promise<Profile> {
    return requestJson<Profile>("/profile", {
      method: "PUT",
      body: JSON.stringify(payload),
    });
  },

  getById(userId: number): Promise<ProfileWithFollow> {
    return requestJson<ProfileWithFollow>(`/profiles/${userId}`);
  },

  follow(userId: number): Promise<ProfileWithFollow> {
    return requestJson<ProfileWithFollow>(`/profiles/${userId}/follow`, {
      method: "POST",
    });
  },

  unfollow(userId: number): Promise<ProfileWithFollow> {
    return requestJson<ProfileWithFollow>(`/profiles/${userId}/follow`, {
      method: "DELETE",
    });
  },
};

export const agentApi = {
  history(): Promise<AgentHistoryResponse> {
    return requestJson<AgentHistoryResponse>("/agent/history");
  },

  clearHistory(): Promise<{ success: boolean; message: string }> {
    return requestJson<{ success: boolean; message: string }>("/agent/history", {
      method: "DELETE",
    });
  },

  async streamChat(message: string, onChunk: (chunk: string) => void): Promise<string> {
    const response = await authorizedFetch(
      "/agent/chat/stream",
      {
        method: "POST",
        body: JSON.stringify({ message }),
      },
      { auth: true },
    );

    if (!response.ok) {
      throw await createApiError(response);
    }

    if (!response.body) {
      throw new ApiError("Streaming is not available for this response.", 500);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let fullResponse = "";

    const consumeBlock = (block: string) => {
      for (const line of block.split("\n")) {
        if (!line.startsWith("data: ")) {
          continue;
        }

        const payloadText = line.slice(6);
        if (!payloadText.trim()) {
          continue;
        }

        try {
          const payload = JSON.parse(payloadText) as { content?: string };
          const content = payload.content ?? "";
          fullResponse += content;
          onChunk(content);
        } catch {
          // Ignore malformed chunks and continue.
        }
      }
    };

    while (true) {
      const { done, value } = await reader.read();
      buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done });

      const blocks = buffer.split("\n\n");
      buffer = blocks.pop() ?? "";

      for (const block of blocks) {
        consumeBlock(block);
      }

      if (done) {
        break;
      }
    }

    if (buffer.trim()) {
      consumeBlock(buffer);
    }

    return fullResponse;
  },
};
