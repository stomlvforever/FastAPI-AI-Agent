import { useState } from "react";
import type { FormEvent } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { StatusView } from "../components/StatusView.tsx";
import { articlesApi } from "../lib/api.ts";
import { getErrorMessage } from "../lib/format.ts";

type EditorForm = {
  title: string;
  description: string;
  body: string;
  tags: string;
};

function normalizeTags(value: string): string[] {
  return value
    .split(",")
    .map((entry) => entry.trim())
    .filter(Boolean);
}

export function EditorPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { slug } = useParams();
  const isEditing = Boolean(slug);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const articleQuery = useQuery({
    queryKey: ["article", slug],
    queryFn: () => articlesApi.get(slug ?? ""),
    enabled: isEditing,
  });

  const mutation = useMutation({
    mutationFn: async (form: EditorForm) => {
      const payload = {
        title: form.title.trim(),
        description: form.description.trim() || null,
        body: form.body.trim(),
        tag_names: normalizeTags(form.tags),
      };

      return isEditing && slug ? articlesApi.update(slug, payload) : articlesApi.create(payload);
    },
    onSuccess: async (article) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["articles"] }),
        queryClient.invalidateQueries({ queryKey: ["article", article.slug] }),
      ]);
      navigate(`/articles/${article.slug}`);
    },
  });

  const handleSubmit = async (form: EditorForm) => {
    setSubmitError(null);

    try {
      await mutation.mutateAsync(form);
    } catch (error) {
      setSubmitError(getErrorMessage(error));
    }
  };

  if (articleQuery.isLoading) {
    return (
      <StatusView
        title="Preparing editor"
        detail="Loading the current article body before opening edit mode."
      />
    );
  }

  if (articleQuery.isError) {
    return (
      <StatusView
        title="Editor failed to load"
        detail={getErrorMessage(articleQuery.error)}
        tone="error"
      />
    );
  }

  return (
    <div className="page-stack">
      <section className="hero-card">
        <span className="eyebrow">{isEditing ? "Edit mode" : "Compose mode"}</span>
        <h1>{isEditing ? "Refine an existing article" : "Write a new article"}</h1>
        <p className="hero-copy">
          This editor maps directly to the backend payload: title, description, body, and tag
          names. Publishing goes straight to the existing article endpoints.
        </p>
      </section>

      <section className="panel form-panel">
        <EditorFormCard
          initialForm={
            articleQuery.data
              ? {
                  title: articleQuery.data.title,
                  description: articleQuery.data.description ?? "",
                  body: articleQuery.data.body,
                  tags: articleQuery.data.tags.map((tag) => tag.name).join(", "),
                }
              : {
                  title: "",
                  description: "",
                  body: "",
                  tags: "",
                }
          }
          isEditing={isEditing}
          isPending={mutation.isPending}
          key={articleQuery.data?.slug ?? "new-article"}
          onCancel={() => navigate(-1)}
          onSubmit={handleSubmit}
          submitError={submitError}
        />
      </section>
    </div>
  );
}

type EditorFormCardProps = {
  initialForm: EditorForm;
  isEditing: boolean;
  isPending: boolean;
  onCancel: () => void;
  onSubmit: (form: EditorForm) => Promise<void>;
  submitError: string | null;
};

function EditorFormCard({
  initialForm,
  isEditing,
  isPending,
  onCancel,
  onSubmit,
  submitError,
}: EditorFormCardProps) {
  const [form, setForm] = useState<EditorForm>(initialForm);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    await onSubmit(form);
  };

  return (
    <>
      {submitError ? <p className="form-error">{submitError}</p> : null}
      <form className="form-grid" onSubmit={handleSubmit}>
        <label className="input-shell">
          <span>Title</span>
          <input
            onChange={(event) =>
              setForm((current) => ({
                ...current,
                title: event.target.value,
              }))
            }
            placeholder="Give the article a strong headline"
            required
            type="text"
            value={form.title}
          />
        </label>

        <label className="input-shell">
          <span>Description</span>
          <input
            onChange={(event) =>
              setForm((current) => ({
                ...current,
                description: event.target.value,
              }))
            }
            placeholder="A short editorial summary"
            type="text"
            value={form.description}
          />
        </label>

        <label className="input-shell">
          <span>Tags</span>
          <input
            onChange={(event) =>
              setForm((current) => ({
                ...current,
                tags: event.target.value,
              }))
            }
            placeholder="backend, release, ops"
            type="text"
            value={form.tags}
          />
        </label>

        <label className="input-shell textarea-shell">
          <span>Body</span>
          <textarea
            onChange={(event) =>
              setForm((current) => ({
                ...current,
                body: event.target.value,
              }))
            }
            placeholder="Write the full article body here"
            required
            rows={16}
            value={form.body}
          />
        </label>

        <div className="hero-actions">
          <button className="button button-primary" disabled={isPending} type="submit">
            {isPending ? "Saving..." : isEditing ? "Update article" : "Publish article"}
          </button>
          <button className="button button-secondary" onClick={onCancel} type="button">
            Cancel
          </button>
        </div>
      </form>
    </>
  );
}
