import { Theme } from "@radix-ui/themes";
import { cleanup, render, screen } from "@testing-library/react";
import type { ReactElement, ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ErrorBlock } from "~/api";
import { TaskStatus } from "~/api";

import { AlphaErrorBlock } from "./AlphaErrorBlock.tsx";

const makeErrorBlock = (overrides: Partial<ErrorBlock> = {}): ErrorBlock => ({
  type: "error",
  objectType: "ErrorBlock",
  message: "Something went wrong.",
  traceback: "Traceback (most recent call last): ...",
  errorType: "builtins.Exception",
  ...overrides,
});

const renderErrorBlock = (props: {
  block: ErrorBlock;
  isLastMessage?: boolean;
  taskStatus?: TaskStatus;
  onRetryRequest?: () => void;
}): ReturnType<typeof render> => {
  const Wrapper = ({ children }: { children: ReactNode }): ReactElement => <Theme>{children}</Theme>;

  return render(
    <AlphaErrorBlock
      block={props.block}
      isLastMessage={props.isLastMessage ?? true}
      taskStatus={props.taskStatus ?? TaskStatus.RUNNING}
      onRetryRequest={props.onRetryRequest}
    />,
    { wrapper: Wrapper },
  );
};

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("AlphaErrorBlock", () => {
  it("offers a retry button on the last message of a non-errored task", () => {
    renderErrorBlock({ block: makeErrorBlock(), onRetryRequest: vi.fn() });
    expect(screen.getByText(/Retry Request/)).toBeInTheDocument();
  });

  it("does not offer retry when the task has errored", () => {
    renderErrorBlock({ block: makeErrorBlock(), taskStatus: TaskStatus.ERROR, onRetryRequest: vi.fn() });
    expect(screen.queryByText(/Retry Request/)).not.toBeInTheDocument();
  });

  it("renders the error message and label", () => {
    renderErrorBlock({ block: makeErrorBlock({ message: "Boom." }) });
    expect(screen.getByText("Boom.")).toBeInTheDocument();
    expect(screen.getByText("Exception")).toBeInTheDocument();
  });
});
