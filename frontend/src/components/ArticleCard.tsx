import { Link } from "react-router-dom";
import { estimateReadingMinutes, formatDate } from "../lib/format.ts";
import type { Article } from "../types.ts";

type ArticleCardProps = {
  article: Article;
  onFavorite?: (article: Article) => void;
  pending?: boolean;
};

export function ArticleCard({ article, onFavorite, pending = false }: ArticleCardProps) {
  return (
    <article className="article-card">
      <div className="article-card-topline">
        <span className="eyebrow">Author #{article.author_id}</span>
        <span className="reading-mark">{estimateReadingMinutes(article.body)} min read</span>
      </div>

      <div className="article-card-heading">
        <div>
          <Link className="article-title-link" to={`/articles/${article.slug}`}>
            <h3>{article.title}</h3>
          </Link>
          <p>{article.description || "A narrative post backed by the article API."}</p>
        </div>

        {onFavorite ? (
          <button
            className={`button button-secondary ${article.favorited ? "is-accent" : ""}`}
            disabled={pending}
            onClick={() => onFavorite(article)}
            type="button"
          >
            {article.favorited ? "Saved" : "Save"} {article.favorites_count}
          </button>
        ) : null}
      </div>

      <div className="tag-row">
        {article.tags.length > 0 ? (
          article.tags.map((tag) => (
            <span className="tag-pill" key={tag.id}>
              {tag.name}
            </span>
          ))
        ) : (
          <span className="muted">No tags yet</span>
        )}
      </div>

      <div className="article-card-footer">
        <div className="article-meta">
          <span>Created {formatDate(article.created_at)}</span>
          <span>Updated {formatDate(article.updated_at)}</span>
        </div>
        <Link className="button button-ghost" to={`/profiles/${article.author_id}`}>
          View author
        </Link>
      </div>
    </article>
  );
}
