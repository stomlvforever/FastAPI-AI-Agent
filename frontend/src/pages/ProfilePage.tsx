import { useState } from "react";
import type { FormEvent } from "react";
import { Link } from "react-router-dom";
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
import type { Article } from "../types.ts";

type ProfileForm = {
  full_name: string;
  bio: string;
  image: string;
};

export function ProfilePage() {
  const queryClient = useQueryClient();
  const { refreshCurrentUser, user } = useAuth();
  const [submitError, setSubmitError] = useState<string | null>(null);

  const profileQuery = useQuery({
    queryKey: ["my-profile"],
    queryFn: profilesApi.getMine,
  });

  const myArticlesQuery = useQuery({
    queryKey: ["author-articles", user?.id],
    queryFn: () => articlesApi.list({ authorId: user!.id, limit: 20 }),
    enabled: Boolean(user?.id),
  });

  const favoriteMutation = useMutation({
    mutationFn: ({ slug, favorited }: { slug: string; favorited: boolean }) =>
      favorited ? articlesApi.unfavorite(slug) : articlesApi.favorite(slug),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["articles"] }),
        queryClient.invalidateQueries({ queryKey: ["author-articles", user?.id] }),
      ]);
    },
  });

  const profileMutation = useMutation({
    mutationFn: (form: ProfileForm) =>
      profilesApi.updateMine({
        full_name: form.full_name.trim() || undefined,
        bio: form.bio.trim() || undefined,
        image: form.image.trim() || undefined,
      }),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["my-profile"] }),
        refreshCurrentUser(),
      ]);
    },
  });

  const handleSubmit = async (form: ProfileForm) => {
    setSubmitError(null);

    try {
      await profileMutation.mutateAsync(form);
    } catch (error) {
      setSubmitError(getErrorMessage(error));
    }
  };

  if (profileQuery.isLoading) {
    return (
      <StatusView title="Loading profile" detail="Fetching your profile and authored articles." />
    );
  }

  if (profileQuery.isError || !profileQuery.data) {
    return (
      <StatusView
        title="Profile unavailable"
        detail={getErrorMessage(profileQuery.error)}
        tone="error"
      />
    );
  }

  const profile = profileQuery.data;
  const avatarUrl = resolveAssetUrl(profile.image);

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
              <span className="eyebrow">Workspace owner</span>
              <h1>{profile.full_name || profile.email}</h1>
              <p>{profile.bio || "Add a short profile note to humanize the frontend."}</p>
            </div>
          </div>

          <div className="hero-stats">
            <div>
              <strong>{profile.role}</strong>
              <span>account role</span>
            </div>
            <div>
              <strong>{myArticlesQuery.data?.length ?? 0}</strong>
              <span>authored articles</span>
            </div>
            <div>
              <strong>{formatDate(profile.created_at)}</strong>
              <span>joined</span>
            </div>
          </div>
        </div>

        <section className="panel form-panel">
          <div className="section-heading">
            <span className="eyebrow">Update profile</span>
            <h2>Keep the public author card current</h2>
          </div>
          <ProfileFormCard
            initialForm={{
              full_name: profile.full_name ?? "",
              bio: profile.bio ?? "",
              image: profile.image ?? "",
            }}
            isPending={profileMutation.isPending}
            key={profile.id}
            onSubmit={handleSubmit}
            submitError={submitError}
          />
        </section>
      </section>

      <section className="panel article-list-panel">
        <div className="section-heading">
          <span className="eyebrow">Your authored posts</span>
          <h2>Use this page as your editorial control center</h2>
        </div>

        {myArticlesQuery.isLoading ? (
          <StatusView
            title="Loading authored articles"
            detail="Pulling every article associated with your account."
          />
        ) : null}

        {myArticlesQuery.isError ? (
          <StatusView
            title="Unable to load authored articles"
            detail={getErrorMessage(myArticlesQuery.error)}
            tone="error"
          />
        ) : null}

        {!myArticlesQuery.isLoading && !myArticlesQuery.isError && !myArticlesQuery.data?.length ? (
          <StatusView
            title="No articles yet"
            detail="Start with a first article to populate your profile page."
            action={
              <Link className="button button-primary" to="/editor">
                Create article
              </Link>
            }
          />
        ) : null}

        <div className="article-stack">
          {myArticlesQuery.data?.map((article: Article) => (
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

type ProfileFormCardProps = {
  initialForm: ProfileForm;
  isPending: boolean;
  onSubmit: (form: ProfileForm) => Promise<void>;
  submitError: string | null;
};

function ProfileFormCard({
  initialForm,
  isPending,
  onSubmit,
  submitError,
}: ProfileFormCardProps) {
  const [form, setForm] = useState<ProfileForm>(initialForm);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    await onSubmit(form);
  };

  return (
    <>
      {submitError ? <p className="form-error">{submitError}</p> : null}
      <form className="form-grid" onSubmit={handleSubmit}>
        <label className="input-shell">
          <span>Full name</span>
          <input
            onChange={(event) =>
              setForm((current) => ({
                ...current,
                full_name: event.target.value,
              }))
            }
            type="text"
            value={form.full_name}
          />
        </label>
        <label className="input-shell">
          <span>Avatar URL</span>
          <input
            onChange={(event) =>
              setForm((current) => ({
                ...current,
                image: event.target.value,
              }))
            }
            placeholder="/static/avatars/example.png"
            type="text"
            value={form.image}
          />
        </label>
        <label className="input-shell textarea-shell">
          <span>Bio</span>
          <textarea
            onChange={(event) =>
              setForm((current) => ({
                ...current,
                bio: event.target.value,
              }))
            }
            rows={6}
            value={form.bio}
          />
        </label>
        <button className="button button-primary" disabled={isPending} type="submit">
          {isPending ? "Saving profile..." : "Save profile"}
        </button>
      </form>
    </>
  );
}
