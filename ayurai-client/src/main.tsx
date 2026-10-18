import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { BrowserRouter } from "react-router"

import "./index.css"
import App from "./App.tsx"
import { ThemeProvider } from "@/components/theme-provider.tsx"
import { TooltipProvider } from "@/components/ui/tooltip"
import { WorkspaceProvider } from "@/context/workspace"

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    {/* The clinical UI is designed for the light theme only. */}
    <ThemeProvider defaultTheme="light" storageKey="ayurai-theme" enableHotkey={false}>
      <TooltipProvider>
        <BrowserRouter>
          <WorkspaceProvider>
            <App />
          </WorkspaceProvider>
        </BrowserRouter>
      </TooltipProvider>
    </ThemeProvider>
  </StrictMode>
)
