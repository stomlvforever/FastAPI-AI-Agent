import { useDeferredValue, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "../auth/useAuth.ts";
import { ArticleCard } from "../components/ArticleCard.tsx";
import { StatusView } from "../components/StatusView.tsx";
import { articlesApi, tagsApi } from "../lib/api.ts";
import { getErrorMessage } from "../lib/format.ts";
import type { Article } from "../types.ts";

type ActiveStream = "discover" | "feed";

export function HomePage() {
  const { isAuthenticated, isRestoring } = useAuth();
  const queryClient = useQueryClient();
  const [activeStream, setActiveStream] = useState<ActiveStream>("discover");
  const [selectedTag, setSelectedTag] = useState("");
  const [searchValue, setSearchValue] = useState("");
  const deferredSearch = useDeferredValue(searchValue);

  const tagsQuery = useQuery({
    queryKey: ["tags"],
    queryFn: tagsApi.list,
  });

  const articlesQuery = useQuery({
    queryKey: ["articles", activeStream, selectedTag || "all"],
    queryFn: () =>
      activeStream === "feed"
        ? articlesApi.feed()
        : articlesApi.list({
            tag: selectedTag || undefined,
            limit: 20,
          }),
    enabled: isAuthenticated,
  });

  const favoriteMutation = useMutation({
    mutationFn: ({ slug, favorited }: { slug: string; favorited: boolean }) =>
      favorited ? articlesApi.unfavorite(slug) : articlesApi.favorite(slug),
    onSuccess: async (article) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["articles"] }),
        queryClient.invalidateQueries({ queryKey: ["article", article.slug] }),
        queryClient.invalidateQueries({ queryKey: ["author-articles"] }),
      ]);
    },
  });

  if (isRestoring) {
    return (
      <StatusView
        title="Reconnecting to your content workspace"
        detail="Your frontend is waiting for the current session to be restored."
      />
    );
  }

  if (!isAuthenticated) {
    return (
      <div className="page-stack">
        <section className="hero-card">
          <span className="eyebrow">Blog shell + Agent entry</span>
          <h1>Turn this FastAPI backend into a clickable editorial frontend.</h1>
          <p className="hero-copy">
            The backend already exposes articles, profiles, follows, favorites, and a dedicated
            Copilot API. This frontend packages those flows into a polished content surface.
          </p>
          <div className="hero-actions">
            <Link className="button button-primary" to="/auth">
              Enter the workspace
            </Link>
            <a className="button button-secondary" href="http://127.0.0.1:8000/docs" target="_blank">
              Open Swagger
            </a>
          </div>
        </section>

        <div className="split-layout">
          <section className="panel">
            <div className="section-heading">
              <span className="eyebrow">What the first version includes</span>
              <h2>Focused on the core content loop</h2>
            </div>
            <div className="feature-grid">
              <div className="feature-card">
                <strong>Article list and detail pages</strong>
                <p>Blog-like cards, detail views, tag chips, and editorial metadata.</p>
              </div>
              <div className="feature-card">
                <strong>Auth-aware interactions</strong>
                <p>Login, registration, save buttons, follow actions, and write flow.</p>
              </div>
              <div className="feature-card">
                <strong>Separate Copilot route</strong>
                <p>The Agent remains isolated from the public-facing article narrative.</p>
              </div>
            </div>
          </section>

          <aside className="panel sidebar-panel">
            <div className="section-heading">
              <span className="eyebrow">Available public tag data</span>
              <h2>Tags already exposed by the API</h2>
            </div>
            <div className="tag-row">
              {tagsQuery.data?.map((tag) => (
                <span className="tag-pill" key={tag.id}>
                  {tag.name}
                </span>
              ))}
              {!tagsQuery.data?.length ? <span className="muted">Tags will appear here.</span> : null}
            </div>
            <p className="panel-note">
              Article listing still requires authentication in the backend, so the homepage acts as
              a landing surface until the user signs in.
            </p>
          </aside>
        </div>
      </div>
    );
  }

  const articles = articlesQuery.data ?? [];
  const query = deferredSearch.trim().toLowerCase();
  const filteredArticles = articles.filter((article) => {
    if (!query) {
      return true;
    }
    return [article.title, article.description ?? "", article.body].some((value) =>
      value.toLowerCase().includes(query),
    );
  });

  const toggleFavorite = (article: Article) => {
    favoriteMutation.mutate({
      slug: article.slug,
      favorited: article.favorited,
    });
  };

  return (
    <div className="page-stack">
      <section className="hero-card">
        <span className="eyebrow">Connected to /api/v1</span>
        <h1>
          {activeStream === "feed" ? "Following feed" : "Discover the latest dispatches"} from
          your FastAPI backend.
        </h1>
        <p className="hero-copy">
          Use the filters to switch between a broad article stream and the accounts you already
          follow. Every card is backed by the existing article endpoints.
        </p>
        <div className="hero-stats">
          <div>
            <strong>{filteredArticles.length}</strong>
            <span>visible articles</span>
          </div>
          <div>
            <strong>{tagsQuery.data?.length ?? 0}</strong>
            <span>loaded tags</span>
          </div>
          <div>
            <strong>{selectedTag || "all"}</strong>
            <span>active tag filter</span>
          </div>
        </div>
      </section>

      <section className="toolbar-panel">
        <div className="tab-strip">
          <button
            className={`tab-button ${activeStream === "discover" ? "is-active" : ""}`}
            onClick={() => setActiveStream("discover")}
            type="button"
          >
            Discover
          </button>
          <button
            className={`tab-button ${activeStream === "feed" ? "is-active" : ""}`}
            onClick={() => setActiveStream("feed")}
            type="button"
          >
            Following feed
          </button>
        </div>
        <label className="input-shell">
          <span>Search loaded content</span>
          <input
            onChange={(event) => setSearchValue(event.target.value)}
            placeholder="Filter by title, summary, or body"
            type="search"
            value={searchValue}
          />
        </label>
      </section>

      <div className="split-layout">
        <aside className="panel sidebar-panel">
          <div className="section-heading">
            <span className="eyebrow">Filter by tag</span>
            <h2>Editorial lanes</h2>
          </div>
          <div className="tag-column">
            <button
              className={`filter-pill ${selectedTag === "" ? "is-active" : ""}`}
              onClick={() => setSelectedTag("")}
              type="button"
            >
              All tags
            </button>
            {tagsQuery.data?.map((tag) => (
              <button
                className={`filter-pill ${selectedTag === tag.name ? "is-active" : ""}`}
                key={tag.id}
                onClick={() => {
                  setActiveStream("discover");
                  setSelectedTag(tag.name);
                }}
                type="button"
              >
                {tag.name}
              </button>
            ))}
          </div>
          <p className="panel-note">
            Feed uses the follow graph. Tag filters switch back to the broader discover stream.
          </p>
        </aside>

        <section className="panel article-list-panel">
          <div className="section-heading">
            <span className="eyebrow">Live article deck</span>
            <h2>{activeStream === "feed" ? "Posts from followed authors" : "Newest content"}</h2>
          </div>

          {articlesQuery.isLoading ? (
            <StatusView
              title="Loading articles"
              detail="The frontend is calling the existing article endpoints now."
            />
          ) : null}

          {articlesQuery.isError ? (
            <StatusView
              title="Article loading failed"
              detail={getErrorMessage(articlesQuery.error)}
              tone="error"
            />
          ) : null}

          {!articlesQuery.isLoading && !articlesQuery.isError && filteredArticles.length === 0 ? (
            <StatusView
              title="No articles matched this view"
              detail="Try another tag, switch streams, or write the first post for this lane."
              action={
                <Link className="button button-primary" to="/editor">
                  Write article
                </Link>
              }
            />
          ) : null}

          <div className="article-stack">
            {filteredArticles.map((article) => (
              <ArticleCard
                article={article}
                key={article.id}
                onFavorite={toggleFavorite}
                pending={
                  favoriteMutation.isPending && favoriteMutation.variables?.slug === article.slug
                }
              />
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
