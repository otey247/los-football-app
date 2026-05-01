import { useQuery } from "@tanstack/react-query"
import { createFileRoute, Link, useRouterState } from "@tanstack/react-router"
import { ArrowLeft, BookOpen, CalendarDays, Loader2, User } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import { BlogService } from "@/lib/footballApi"

export const Route = createFileRoute("/_layout/blog")({
  component: BlogList,
  head: () => ({
    meta: [{ title: "Blog - Los Football" }],
  }),
})

function BlogDetail({ postId }: { postId: string }) {
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
            <p className="mt-4 rounded-xl bg-secondary/50 p-4 text-muted-foreground">
              {post.excerpt}
            </p>
          )}
        </header>

        <Separator />

        <div className="prose prose-sm dark:prose-invert max-w-none leading-relaxed whitespace-pre-wrap">
          {post.content}
        </div>
      </article>
    </div>
  )
}

function BlogList() {
  const pathname = useRouterState({
    select: (state) => state.location.pathname,
  })
  const postId = pathname.startsWith("/blog/")
    ? pathname.replace("/blog/", "")
    : ""
  const { data, isLoading, isError } = useQuery({
    queryKey: ["blog-posts"],
    queryFn: () => BlogService.getPosts(),
    enabled: !postId,
  })

  if (postId) {
    return <BlogDetail postId={postId} />
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
          <BookOpen className="h-6 w-6" />
          Blog
        </h1>
        <p className="text-muted-foreground">
          News, analysis, and updates from the Los Football commissioner
        </p>
      </div>

      {isLoading && (
        <div className="flex items-center justify-center py-16">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      )}

      {isError && (
        <div className="text-center py-16 text-muted-foreground">
          <p>Failed to load blog posts. Please try again later.</p>
        </div>
      )}

      {data && data.data.length === 0 && (
        <div className="text-center py-16 text-muted-foreground">
          <BookOpen className="h-12 w-12 mx-auto mb-4 opacity-50" />
          <p className="text-lg font-medium">No posts yet</p>
          <p className="text-sm">Check back soon for updates!</p>
        </div>
      )}

      {data && data.data.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {data.data.map((post) => (
            <Link
              key={post.id}
              to="/blog/$postId"
              params={{ postId: post.id }}
              className="no-underline"
            >
              <Card className="h-full cursor-pointer transition-[background-color,box-shadow,transform] hover:-translate-y-0.5 hover:bg-card group">
                <CardHeader>
                  <CardTitle className="group-hover:text-primary transition-colors line-clamp-2">
                    {post.title}
                  </CardTitle>
                  {post.excerpt && (
                    <CardDescription className="line-clamp-3">
                      {post.excerpt}
                    </CardDescription>
                  )}
                </CardHeader>
                <CardContent>
                  <div className="flex items-center gap-4 text-xs text-muted-foreground">
                    {post.author_name && (
                      <span className="flex items-center gap-1">
                        <User className="h-3 w-3" />
                        {post.author_name}
                      </span>
                    )}
                    {post.created_at && (
                      <span className="flex items-center gap-1">
                        <CalendarDays className="h-3 w-3" />
                        {new Date(post.created_at).toLocaleDateString("en-US", {
                          year: "numeric",
                          month: "long",
                          day: "numeric",
                        })}
                      </span>
                    )}
                  </div>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
