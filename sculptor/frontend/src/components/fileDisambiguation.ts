/**
 * Compute disambiguated display names for a list of file paths.
 * Paths with unique basenames display as just the basename.
 * Paths sharing a basename get the minimum unique parent prefix prepended
 * as `parentDir/.../basename`. If even the full path isn't unique, the
 * full path is used as-is.
 */
export const disambiguateFileNames = (filePaths: ReadonlyArray<string>): Map<string, string> => {
  const result = new Map<string, string>();
  if (filePaths.length === 0) return result;

  const basename = (path: string): string => {
    const parts = path.split("/");
    return parts[parts.length - 1] || path;
  };

  // Group paths by basename
  const groups = new Map<string, Array<string>>();
  for (const path of filePaths) {
    const base = basename(path);
    const group = groups.get(base);
    if (group) {
      group.push(path);
    } else {
      groups.set(base, [path]);
    }
  }

  for (const [base, paths] of groups) {
    // Two mentions of the same file aren't really a collision — they point at
    // the same thing. Dedupe before disambiguating so identical paths render
    // as the bare basename instead of expanding to the full path.
    const distinctPaths = Array.from(new Set(paths));

    if (distinctPaths.length === 1) {
      result.set(paths[0], base);
      continue;
    }

    // For duplicate basenames, find minimum unique prefix.
    // Split each path into segments and walk from the end.
    const segmentsList = distinctPaths.map((p) => p.split("/"));

    for (let i = 0; i < distinctPaths.length; i++) {
      const segments = segmentsList[i];
      let isFound = false;

      for (let depth = 2; depth <= segments.length; depth++) {
        const candidate = segments.slice(segments.length - depth).join("/");
        const isUnique = segmentsList.every((otherSegments, j) => {
          if (j === i) return true;
          if (otherSegments.length < depth) return true;
          const otherCandidate = otherSegments.slice(otherSegments.length - depth).join("/");
          return otherCandidate !== candidate;
        });
        if (isUnique) {
          const parentDir = segments[segments.length - depth];
          result.set(distinctPaths[i], `${parentDir}/.../${base}`);
          isFound = true;
          break;
        }
      }

      if (!isFound) {
        result.set(distinctPaths[i], distinctPaths[i]);
      }
    }
  }

  return result;
};
