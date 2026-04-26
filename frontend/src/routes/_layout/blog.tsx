import { useQuery } from "@tanstack/react-query"
import { createFileRoute, Link } from "@tanstack/react-router"
import { BookOpen, CalendarDays, Loader2, User } from "lucide-react"

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { BlogService } from "@/lib/footballApi"

export const Route = createFileRoute("/_layout/blog")({
  component: BlogList,
  head: () => ({
    meta: [{ title: "Blog - Los Football" }],
  }),
})

function BlogList() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["blog-posts"],
    queryFn: () => BlogService.getPosts(true),
  })

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
              <Card className="h-full hover:shadow-md transition-shadow cursor-pointer group">
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
