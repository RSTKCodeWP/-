import { redirect } from "next/navigation";

/**
 * Agent management moved into the unified Dashboard drone view. This route
 * stays as a redirect so existing bookmarks and deep links land on the
 * Dashboard instead of 404ing.
 */
export default function CommandRoute() {
  redirect("/");
}
