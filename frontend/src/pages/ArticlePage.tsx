import { Link, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "../auth/useAuth.ts";
import { StatusView } from "../components/StatusView.tsx";
import { articlesApi, profilesApi } from "../lib/api.ts";
import {
  formatDate,
  getErrorMessage,
  getInitials,
  resolveAssetUrl,
} from "../lib/format.ts";

export function ArticlePage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { slug } = useParams();
  const { user } = useAuth();

  const articleQuery = useQuery({
    queryKey: ["article", slug],
    queryFn: () => articlesApi.get(slug ?? ""),
    enabled: Boolean(slug),
  });

  const authorQuery = useQuery({
    queryKey: ["author-profile", articleQuery.data?.author_id],
    queryFn: () => profilesApi.getById(articleQuery.data!.author_id),
    enabled: Boolean(articleQuery.data?.author_id),
  });

  const favoriteMutation = useMutation({
    mutationFn: ({ articleSlug, favorited }: { articleSlug: string; favorited: boolean }) =>
      favorited ? articlesApi.unfavorite(articleSlug) : articlesApi.favorite(articleSlug),
    onSuccess: async (article) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["article", article.slug] }),
        queryClient.invalidateQueries({ queryKey: ["articles"] }),
        queryClient.invalidateQueries({ queryKey: ["author-articles"] }),
      ]);
    },
  });

  const followMutation = useMutation({
    mutationFn: ({ authorId, following }: { authorId: number; following: boolean }) =>
      following ? profilesApi.unfollow(authorId) : profilesApi.follow(authorId),
    onSuccess: async (_, variables) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["author-profile", variables.authorId] }),
        queryClient.invalidateQueries({ queryKey: ["articles"] }),
      ]);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (articleSlug: string) => articlesApi.remove(articleSlug),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["articles"] });
      navigate("/");
    },
  });

  if (!slug) {
    return (
      <StatusView
        title="Missing article slug"
        detail="This route needs an article slug to request the detail endpoint."
      />
    );
  }

  if (articleQuery.isLoading) {
    return (
      <StatusView title="Loading article" detail="Pulling the article detail from the backend." />
    );
  }

  if (articleQuery.isError || !articleQuery.data) {
    return (
      <StatusView
        title="Article unavailable"
        detail={getErrorMessage(articleQuery.error)}
        tone="error"
      />
    );
  }

  const article = articleQuery.data;
  const author = authorQuery.data;
  const authorImage = resolveAssetUrl(author?.image);
  const canEdit = user?.id === article.author_id || user?.role === "admin";
  const isOwnAuthor = user?.id === article.author_id;

  return (
    <div className="page-stack">
      <section className="article-hero">
        <div className="section-heading">
          <span className="eyebrow">Article detail</span>
          <h1>{article.title}</h1>
          <p className="hero-copy">
            {article.description || "This entry is delivered by the existing article detail API."}
          </p>
        </div>

        <div className="hero-actions">
          <button
            className={`button button-secondary ${article.favorited ? "is-accent" : ""}`}
            disabled={favoriteMutation.isPending}
            onClick={() =>
              favoriteMutation.mutate({
                articleSlug: article.slug,
                favorited: article.favorited,
              })
            }
            type="button"
          >
            {article.favorited ? "Saved" : "Save"} {article.favorites_count}
          </button>
          {canEdit ? (
            <Link className="button button-primary" to={`/editor/${article.slug}`}>
              Edit article
            </Link>
          ) : null}
          {canEdit ? (
            <button
              className="button button-ghost is-danger"
              disabled={deleteMutation.isPending}
              onClick={() => deleteMutation.mutate(article.slug)}
              type="button"
            >
              {deleteMutation.isPending ? "Removing..." : "Delete"}
            </button>
          ) : null}
        </div>
      </section>

      <div className="split-layout">
        <article className="panel article-body-panel">
          <div className="article-meta">
            <span>Created {formatDate(article.created_at)}</span>
            <span>Updated {formatDate(article.updated_at)}</span>
            <span>Author #{article.author_id}</span>
          </div>

          <div className="tag-row">
            {article.tags.map((tag) => (
              <span className="tag-pill" key={tag.id}>
                {tag.name}
              </span>
            ))}
          </div>

          <div className="article-body">{article.body}</div>
        </article>

        <aside className="panel sidebar-panel">
          <div className="section-heading">
            <span className="eyebrow">Author card</span>
            <h2>{author?.full_name || author?.email || `Author #${article.author_id}`}</h2>
          </div>

          <div className="author-card">
            {authorImage ? (
              <img alt={author?.full_name || author?.email || "Author avatar"} src={authorImage} />
            ) : (
              <div className="avatar-fallback">
                {getInitials(author?.full_name, author?.email || `author${article.author_id}@local`)}
              </div>
            )}
            <div>
              <p>{author?.bio || "No public bio has been added yet."}</p>
              <p className="muted">Role: {author?.role || "user"}</p>
            </div>
          </div>

          <div className="stack-actions">
            <Link className="button button-secondary" to={`/profiles/${article.author_id}`}>
              Open author page
            </Link>
            {!isOwnAuthor && author ? (
              <button
                className={`button button-primary ${author.following ? "is-soft" : ""}`}
                disabled={followMutation.isPending}
                onClick={() =>
                  followMutation.mutate({
                    authorId: article.author_id,
                    following: author.following,
                  })
                }
                type="button"
              >
                {author.following ? "Unfollow author" : "Follow author"}
              </button>
            ) : null}
            <Link className="button button-ghost" to="/">
              Back to stream
            </Link>
          </div>
        </aside>
      </div>
    </div>
  );
}
