import { Button, Flex, Link, Spinner, Text } from "@radix-ui/themes";
import { CheckCircle2Icon, CircleXIcon } from "lucide-react";
import type { ReactElement } from "react";
import { useEffect, useState } from "react";

import { ElementIds, getToolAvailability } from "~/api";

import styles from "./OnboardingWizard.module.scss";

// Where users go to install the missing tools. Sculptor checks for these on
// PATH but never installs them itself.
const CLAUDE_INSTALL_URL = "https://docs.anthropic.com/en/docs/claude-code/setup";
const GIT_INSTALL_URL = "https://git-scm.com/downloads";

type ToolRowProps = {
  testId: string;
  name: string;
  isFound: boolean;
  installUrl: string;
  missingTestId?: string;
};

const ToolRow = ({ testId, name, isFound, installUrl, missingTestId }: ToolRowProps): ReactElement => (
  <Flex direction="column" gap="1" data-testid={testId}>
    <Flex gap="2" align="center">
      {isFound ? <CheckCircle2Icon size={16} color="var(--green-9)" /> : <CircleXIcon size={16} color="var(--red-9)" />}
      <Text size="3">
        {name} {isFound ? "found on your PATH" : "not found on your PATH"}
      </Text>
    </Flex>
    {!isFound && (
      <Text size="2" color="gray" data-testid={missingTestId}>
        Sculptor could not find {name} on your PATH. You can still continue, but {name} must be installed for Sculptor
        to work.{" "}
        <Link href={installUrl} target="_blank" className={styles.linkText}>
          How to install {name}
        </Link>
      </Text>
    )}
  </Flex>
);

type PathCheckStepProps = {
  onContinue: () => void;
  isLoading: boolean;
};

export const PathCheckStep = ({ onContinue, isLoading }: PathCheckStepProps): ReactElement => {
  const [isChecking, setIsChecking] = useState(true);
  const [isClaudeFound, setIsClaudeFound] = useState(false);
  const [isGitFound, setIsGitFound] = useState(false);

  useEffect(() => {
    const checkTools = async (): Promise<void> => {
      try {
        const { data: availability } = await getToolAvailability({ meta: { skipWsAck: true } });
        if (availability) {
          setIsClaudeFound(availability.claude);
          setIsGitFound(availability.git);
        }
      } catch (error) {
        // The PATH check is advisory and non-blocking — if it fails we simply
        // report both tools as missing and still let the user proceed.
        console.error("Failed to check tool availability:", error);
      }
      setIsChecking(false);
    };

    checkTools();
  }, []);

  return (
    <Flex direction="column" gap="3" data-testid={ElementIds.ONBOARDING_PATH_CHECK_STEP}>
      <Text className={styles.titleText}>Check your tools</Text>
      <Text color="gray" className={styles.secondaryText}>
        Sculptor uses the Claude and Git command-line tools. We check that they are available on your PATH — we never
        install or change anything.
      </Text>

      {isChecking ? (
        <Flex justify="center" mt="3">
          <Spinner />
        </Flex>
      ) : (
        <Flex direction="column" gap="3" mt="2">
          <ToolRow
            testId={ElementIds.ONBOARDING_TOOL_STATUS_CLAUDE}
            name="Claude"
            isFound={isClaudeFound}
            installUrl={CLAUDE_INSTALL_URL}
            missingTestId={ElementIds.ONBOARDING_TOOL_MISSING_CLAUDE_MESSAGE}
          />
          <ToolRow
            testId={ElementIds.ONBOARDING_TOOL_STATUS_GIT}
            name="Git"
            isFound={isGitFound}
            installUrl={GIT_INSTALL_URL}
          />
        </Flex>
      )}

      <Button
        mt="2"
        size="3"
        variant="solid"
        className={styles.primaryButton}
        disabled={isChecking || isLoading}
        onClick={onContinue}
        data-testid={ElementIds.ONBOARDING_PATH_CHECK_CONTINUE}
      >
        {isLoading ? <Spinner /> : "Continue"}
      </Button>
    </Flex>
  );
};
