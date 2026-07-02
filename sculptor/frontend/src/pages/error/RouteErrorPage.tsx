import type { ReactElement } from "react";
import { useRouteError } from "react-router-dom";

import { ErrorPage } from "./ErrorPage.tsx";

export const RouteErrorPage = (): ReactElement => {
  const error = useRouteError();
  return <ErrorPage error={error} />;
};
