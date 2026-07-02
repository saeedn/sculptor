import { QueryClientProvider } from "@tanstack/react-query";
import { Provider as JotaiProvider } from "jotai/react";
import type { ErrorInfo, ReactElement, ReactNode } from "react";
import { Component } from "react";

import { queryClient } from "~/common/queryClient.ts";

import { BackendStatusBoundary } from "./components/BackendStatusBoundary.tsx";
import { ConfigLoader } from "./components/ConfigLoader.tsx";
import { TanstackDevtoolsMount } from "./components/DevPanel/TanstackDevtoolsMount.tsx";
import { RequireOnboarding } from "./components/RequireOnboarding.tsx";
import { ThemeProvider } from "./components/ThemeProvider.tsx";
import { ToastProvider } from "./components/Toast.tsx";
import { useAppZoom } from "./hooks/useAppZoom.ts";
import { ErrorPage } from "./pages/error/ErrorPage.tsx";
import { Router } from "./Router.tsx";

type AppErrorBoundaryProps = { children: ReactNode };
type AppErrorBoundaryState = { error: Error | null };

// Error boundary: catches render errors anywhere in the tree and shows the
// ErrorPage fallback.
class AppErrorBoundary extends Component<AppErrorBoundaryProps, AppErrorBoundaryState> {
  state: AppErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): AppErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error("Uncaught render error:", error, info.componentStack);
  }

  render(): ReactNode {
    if (this.state.error !== null) {
      return <ErrorPage error={this.state.error} />;
    }
    return this.props.children;
  }
}

export const App = (): ReactElement => {
  useAppZoom();

  return (
    <AppErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <JotaiProvider>
          <ThemeProvider>
            <ToastProvider>
              <BackendStatusBoundary>
                <RequireOnboarding>
                  <ConfigLoader>
                    <Router />
                  </ConfigLoader>
                </RequireOnboarding>
              </BackendStatusBoundary>
            </ToastProvider>
          </ThemeProvider>
          <TanstackDevtoolsMount />
        </JotaiProvider>
      </QueryClientProvider>
    </AppErrorBoundary>
  );
};
