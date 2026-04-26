import { useQuery } from "@tanstack/react-query"
import { createFileRoute, Link } from "@tanstack/react-router"
import { ArrowLeft, CalendarDays, Loader2, User } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import { BlogService } from "@/lib/footballApi"

export const Route = createFileRoute("/_layout/blog/$postId")({
  component: BlogPostDetail,
  head: () => ({
    meta: [{ title: "Blog Post - Los Football" }],
  }),
})

function BlogPostDetail() {
  const { postId } = Route.useParams()

  const {
    data: post,
    isLoading,
    isError,
  } = useQuery({
    queryKey: ["blog-post", postId],
    queryFn: () => BlogService.getPost(postId),
    retry: false,
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-16">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (isError || !post) {
    return (
      <div className="flex flex-col items-center justify-center py-16 gap-4">
        <p className="text-muted-foreground">Blog post not found.</p>
        <Button variant="outline" asChild>
          <Link to="/blog">
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back to Blog
          </Link>
        </Button>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-6 max-w-3xl mx-auto">
      <Button variant="ghost" size="sm" className="w-fit -ml-2" asChild>
        <Link to="/blog">
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back to Blog
        </Link>
      </Button>

      <article className="flex flex-col gap-4">
        <header>
          <h1 className="text-3xl font-bold tracking-tight leading-tight">
            {post.title}
          </h1>
          <div className="flex items-center gap-4 mt-3 text-sm text-muted-foreground">
            {post.author_name && (
              <span className="flex items-center gap-1">
                <User className="h-4 w-4" />
                {post.author_name}
              </span>
            )}
            {post.created_at && (
              <span className="flex items-center gap-1">
                <CalendarDays className="h-4 w-4" />
                {new Date(post.created_at).toLocaleDateString("en-US", {
                  year: "numeric",
                  month: "long",
                  day: "numeric",
                })}
              </span>
            )}
          </div>
          {post.excerpt && (
            <p className="mt-3 text-muted-foreground italic border-l-4 border-primary pl-4">
              {post.excerpt}
            </p>
          )}
        </header>

        <Separator />

        <div
          className="prose prose-sm dark:prose-invert max-w-none leading-relaxed"
          // biome-ignore lint/security/noDangerouslySetInnerHtml: blog content is authored by trusted super admin
          dangerouslySetInnerHTML={{
            __html: post.content.replace(/\n/g, "<br />"),
          }}
        />
      </article>
    </div>
  )
}
