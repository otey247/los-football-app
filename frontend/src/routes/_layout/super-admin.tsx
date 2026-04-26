import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute, redirect } from "@tanstack/react-router"
import {
  Edit,
  Eye,
  EyeOff,
  Loader2,
  Plus,
  ShieldCheck,
  Trash2,
} from "lucide-react"
import { useState } from "react"
import { toast } from "sonner"

import { UsersService } from "@/client"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { Textarea } from "@/components/ui/textarea"
import {
  type BlogPost,
  type BlogPostCreate,
  type BlogPostUpdate,
  BlogService,
} from "@/lib/footballApi"

export const Route = createFileRoute("/_layout/super-admin")({
  component: SuperAdmin,
  beforeLoad: async () => {
    const user = await UsersService.readUserMe()
    if (!user.is_superuser) {
      throw redirect({ to: "/" })
    }
  },
  head: () => ({
    meta: [{ title: "Super Admin - Los Football" }],
  }),
})

// ---- Slug helper -----------------------------------------------------------

function toSlug(title: string): string {
  return title
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "")
}

// ---- Post Form Dialog ------------------------------------------------------

interface PostFormDialogProps {
  post?: BlogPost | null
  open: boolean
  onClose: () => void
}

const EMPTY_FORM: BlogPostCreate = {
  title: "",
  slug: "",
  content: "",
  excerpt: "",
  published: false,
}

function PostFormDialog({ post, open, onClose }: PostFormDialogProps) {
  const qc = useQueryClient()
  const isEdit = !!post

  const [form, setForm] = useState<BlogPostCreate>(() =>
    post
      ? {
          title: post.title,
          slug: post.slug,
          content: post.content,
          excerpt: post.excerpt ?? "",
          published: post.published,
        }
      : EMPTY_FORM,
  )

  const setField = <K extends keyof BlogPostCreate>(
    key: K,
    value: BlogPostCreate[K],
  ) => setForm((f) => ({ ...f, [key]: value }))

  const handleTitleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const title = e.target.value
    setForm((f) => ({ ...f, title, slug: isEdit ? f.slug : toSlug(title) }))
  }

  const createMutation = useMutation({
    mutationFn: (data: BlogPostCreate) => BlogService.createPost(data),
    onSuccess: () => {
      toast.success("Blog post created!")
      qc.invalidateQueries({ queryKey: ["blog-admin"] })
      qc.invalidateQueries({ queryKey: ["blog-posts"] })
      onClose()
    },
    onError: (err: Error) => toast.error(err.message),
  })

  const updateMutation = useMutation({
    mutationFn: (data: BlogPostUpdate) =>
      BlogService.updatePost(post!.id, data),
    onSuccess: () => {
      toast.success("Blog post updated!")
      qc.invalidateQueries({ queryKey: ["blog-admin"] })
      qc.invalidateQueries({ queryKey: ["blog-posts"] })
      onClose()
    },
    onError: (err: Error) => toast.error(err.message),
  })

  const isPending = createMutation.isPending || updateMutation.isPending

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const payload = {
      ...form,
      excerpt: form.excerpt || null,
    }
    if (isEdit) {
      updateMutation.mutate(payload)
    } else {
      createMutation.mutate(payload)
    }
  }

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="sm:max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>
            {isEdit ? "Edit Blog Post" : "New Blog Post"}
          </DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div className="grid gap-1.5">
            <Label htmlFor="post-title">Title *</Label>
            <Input
              id="post-title"
              value={form.title}
              onChange={handleTitleChange}
              placeholder="My awesome blog post"
              required
            />
          </div>

          <div className="grid gap-1.5">
            <Label htmlFor="post-slug">Slug *</Label>
            <Input
              id="post-slug"
              value={form.slug}
              onChange={(e) => setField("slug", e.target.value)}
              placeholder="my-awesome-blog-post"
              required
            />
          </div>

          <div className="grid gap-1.5">
            <Label htmlFor="post-excerpt">Excerpt</Label>
            <Textarea
              id="post-excerpt"
              value={form.excerpt ?? ""}
              onChange={(e) => setField("excerpt", e.target.value)}
              placeholder="Brief summary shown on the blog list..."
              rows={2}
            />
          </div>

          <div className="grid gap-1.5">
            <Label htmlFor="post-content">Content *</Label>
            <Textarea
              id="post-content"
              value={form.content}
              onChange={(e) => setField("content", e.target.value)}
              placeholder="Write your blog post content here..."
              rows={10}
              required
            />
          </div>

          <div className="flex items-center gap-3">
            <Switch
              id="post-published"
              checked={form.published}
              onCheckedChange={(v) => setField("published", v)}
            />
            <Label htmlFor="post-published">
              {form.published ? "Published" : "Draft"}
            </Label>
          </div>

          <DialogFooter className="gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={onClose}
              disabled={isPending}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={isPending}>
              {isPending && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              {isEdit ? "Save Changes" : "Create Post"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

// ---- Delete Confirm Dialog -------------------------------------------------

interface DeleteDialogProps {
  post: BlogPost | null
  onClose: () => void
  onConfirm: () => void
  isLoading: boolean
}

function DeleteDialog({
  post,
  onClose,
  onConfirm,
  isLoading,
}: DeleteDialogProps) {
  return (
    <Dialog open={!!post} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="sm:max-w-sm">
        <DialogHeader>
          <DialogTitle>Delete Blog Post</DialogTitle>
        </DialogHeader>
        <p className="text-sm text-muted-foreground">
          Are you sure you want to delete{" "}
          <strong>&quot;{post?.title}&quot;</strong>? This action cannot be
          undone.
        </p>
        <DialogFooter className="gap-2">
          <Button variant="outline" onClick={onClose} disabled={isLoading}>
            Cancel
          </Button>
          <Button
            variant="destructive"
            onClick={onConfirm}
            disabled={isLoading}
          >
            {isLoading && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
            Delete
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// ---- Main component --------------------------------------------------------

function SuperAdmin() {
  const qc = useQueryClient()
  const [formPost, setFormPost] = useState<BlogPost | null | undefined>(
    undefined,
  )
  const [deletePost, setDeletePost] = useState<BlogPost | null>(null)

  const {
    data,
    isLoading,
    isError,
    refetch: refetchPosts,
  } = useQuery({
    queryKey: ["blog-admin"],
    queryFn: () => BlogService.getAllPostsAdmin(),
    retry: false,
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => BlogService.deletePost(id),
    onSuccess: () => {
      toast.success("Post deleted")
      qc.invalidateQueries({ queryKey: ["blog-admin"] })
      qc.invalidateQueries({ queryKey: ["blog-posts"] })
      setDeletePost(null)
    },
    onError: (err: Error) => toast.error(err.message),
  })

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
            <ShieldCheck className="h-6 w-6" />
            Super Admin
          </h1>
          <p className="text-muted-foreground">Create and manage blog posts</p>
        </div>
        <Button onClick={() => setFormPost(null)} className="shrink-0">
          <Plus className="h-4 w-4 mr-2" />
          New Post
        </Button>
      </div>

      {isLoading && (
        <div className="flex items-center justify-center py-16">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      )}

      {isError && (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-16 gap-3 text-center">
            <p className="font-medium">Unable to load blog posts</p>
            <p className="text-sm text-muted-foreground">
              Your session may have expired or the backend may be unavailable.
            </p>
            <Button variant="outline" size="sm" onClick={() => refetchPosts()}>
              Retry
            </Button>
          </CardContent>
        </Card>
      )}

      {data && data.data.length === 0 && (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-16 gap-4 text-muted-foreground">
            <p>No blog posts yet. Click "New Post" to create your first one.</p>
          </CardContent>
        </Card>
      )}

      {data && data.data.length > 0 && (
        <div className="flex flex-col gap-3">
          {data.data.map((post) => (
            <Card key={post.id}>
              <CardHeader className="pb-2">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap mb-1">
                      {post.published ? (
                        <Badge className="bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200 border-0 text-xs">
                          <Eye className="h-3 w-3 mr-1" />
                          Published
                        </Badge>
                      ) : (
                        <Badge variant="secondary" className="text-xs">
                          <EyeOff className="h-3 w-3 mr-1" />
                          Draft
                        </Badge>
                      )}
                      <span className="text-xs text-muted-foreground font-mono">
                        /{post.slug}
                      </span>
                    </div>
                    <CardTitle className="text-base line-clamp-1">
                      {post.title}
                    </CardTitle>
                    {post.excerpt && (
                      <CardDescription className="text-xs line-clamp-2 mt-1">
                        {post.excerpt}
                      </CardDescription>
                    )}
                  </div>
                  <div className="flex gap-1 shrink-0">
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8"
                      onClick={() => setFormPost(post)}
                    >
                      <Edit className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8 text-destructive hover:text-destructive"
                      onClick={() => setDeletePost(post)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="pt-0">
                <p className="text-xs text-muted-foreground">
                  {post.created_at &&
                    `Created ${new Date(post.created_at).toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" })}`}
                  {post.updated_at &&
                    post.updated_at !== post.created_at &&
                    ` · Updated ${new Date(post.updated_at).toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" })}`}
                </p>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Form dialog: undefined = closed, null = new post, BlogPost = edit */}
      {formPost !== undefined && (
        <PostFormDialog
          post={formPost}
          open
          onClose={() => setFormPost(undefined)}
        />
      )}

      <DeleteDialog
        post={deletePost}
        onClose={() => setDeletePost(null)}
        onConfirm={() => deletePost && deleteMutation.mutate(deletePost.id)}
        isLoading={deleteMutation.isPending}
      />
    </div>
  )
}
