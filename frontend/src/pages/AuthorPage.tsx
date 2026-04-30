import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "../auth/useAuth.ts";
import { ArticleCard } from "../components/ArticleCard.tsx";
import { StatusView } from "../components/StatusView.tsx";
import { articlesApi, profilesApi } from "../lib/api.ts";
import {
  formatDate,
  getErrorMessage,
  getInitials,
  resolveAssetUrl,
} from "../lib/format.ts";

export function AuthorPage() {
  const { user } = useAuth();
  const { userId } = useParams();
  const queryClient = useQueryClient();
  const numericUserId = Number(userId);

  const profileQuery = useQuery({
    queryKey: ["author-profile", numericUserId],
    queryFn: () => profilesApi.getById(numericUserId),
    enabled: Number.isFinite(numericUserId),
  });

  const articlesQuery = useQuery({
    queryKey: ["author-articles", numericUserId],
    queryFn: () => articlesApi.list({ authorId: numericUserId, limit: 20 }),
    enabled: Number.isFinite(numericUserId),
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

  const favoriteMutation = useMutation({
    mutationFn: ({ slug, favorited }: { slug: string; favorited: boolean }) =>
      favorited ? articlesApi.unfavorite(slug) : articlesApi.favorite(slug),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["articles"] }),
        queryClient.invalidateQueries({ queryKey: ["author-articles", numericUserId] }),
      ]);
    },
  });

  if (!Number.isFinite(numericUserId)) {
    return (
      <StatusView
        title="Invalid author id"
        detail="The author route expects a numeric user id from the backend."
      />
    );
  }

  if (profileQuery.isLoading) {
    return (
      <StatusView
        title="Loading author page"
        detail="Fetching the profile and related articles for this author."
      />
    );
  }

  if (profileQuery.isError || !profileQuery.data) {
    return (
      <StatusView
        title="Author page unavailable"
        detail={getErrorMessage(profileQuery.error)}
        tone="error"
      />
    );
  }

  const profile = profileQuery.data;
  const avatarUrl = resolveAssetUrl(profile.image);
  const isOwnProfile = user?.id === profile.id;

  return (
    <div className="page-stack">
      <section className="split-layout profile-hero">
        <div className="panel profile-card">
          <div className="profile-badge">
            {avatarUrl ? (
              <img alt={profile.full_name || profile.email} src={avatarUrl} />
            ) : (
              <div className="avatar-fallback">{getInitials(profile.full_name, profile.email)}</div>
            )}
            <div>
              <span className="eyebrow">Author profile</span>
              <h1>{profile.full_name || profile.email}</h1>
              <p>{profile.bio || "No public author description yet."}</p>
            </div>
          </div>

          <div className="hero-stats">
            <div>
              <strong>{articlesQuery.data?.length ?? 0}</strong>
              <span>published posts</span>
            </div>
            <div>
              <strong>{profile.role}</strong>
              <span>role</span>
            </div>
            <div>
              <strong>{formatDate(profile.created_at)}</strong>
              <span>joined</span>
            </div>
          </div>
        </div>

        <aside className="panel sidebar-panel">
          <div className="section-heading">
            <span className="eyebrow">Relationship controls</span>
            <h2>Social actions stay separate from the article flow</h2>
          </div>
          {!isOwnProfile ? (
            <button
              className={`button button-primary ${profile.following ? "is-soft" : ""}`}
              disabled={followMutation.isPending}
              onClick={() =>
                followMutation.mutate({
                  authorId: profile.id,
                  following: profile.following,
                })
              }
              type="button"
            >
              {profile.following ? "Unfollow author" : "Follow author"}
            </button>
          ) : (
            <Link className="button button-primary" to="/profile">
              Open my profile
            </Link>
          )}
          <p className="panel-note">
            This page is a natural place for author biographies, article archives, and future
            follower counts.
          </p>
        </aside>
      </section>

      <section className="panel article-list-panel">
        <div className="section-heading">
          <span className="eyebrow">Author archive</span>
          <h2>Posts written by this account</h2>
        </div>

        {articlesQuery.isLoading ? (
          <StatusView title="Loading archive" detail="Fetching articles by author id." />
        ) : null}

        {articlesQuery.isError ? (
          <StatusView
            title="Archive unavailable"
            detail={getErrorMessage(articlesQuery.error)}
            tone="error"
          />
        ) : null}

        {!articlesQuery.isLoading && !articlesQuery.isError && !articlesQuery.data?.length ? (
          <StatusView
            title="No authored posts yet"
            detail="The author profile is connected, but there are no published articles to show."
          />
        ) : null}

        <div className="article-stack">
          {articlesQuery.data?.map((article) => (
            <ArticleCard
              article={article}
              key={article.id}
              onFavorite={(targetArticle) =>
                favoriteMutation.mutate({
                  slug: targetArticle.slug,
                  favorited: targetArticle.favorited,
                })
              }
              pending={
                favoriteMutation.isPending && favoriteMutation.variables?.slug === article.slug
              }
            />
          ))}
        </div>
      </section>
    </div>
  );
}
