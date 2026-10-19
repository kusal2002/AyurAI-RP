import { Link } from "react-router"
import { Compass } from "lucide-react"

import { EmptyState, Panel } from "@/components/shared/page"
import { Button } from "@/components/ui/button"

export function NotFoundPage() {
  return (
    <Panel>
      <EmptyState
        icon={Compass}
        title="Page not found"
        description="This address does not match any screen in the workspace."
        action={
          <Button variant="outline" render={<Link to="/" />} nativeButton={false}>
            Back to overview
          </Button>
        }
      />
    </Panel>
  )
}
