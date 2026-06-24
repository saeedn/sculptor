import { Spinner } from "@radix-ui/themes";
import type { ReactElement, ReactNode } from "react";
import { useEffect, useState } from "react";

import { getConfigStatus } from "../api";
import { OnboardingStep, OnboardingWizard } from "./onboarding-wizard";

type RequireOnboardingProps = {
  children: ReactNode;
};

export const RequireOnboarding = ({ children }: RequireOnboardingProps): ReactElement => {
  const [isCheckingConfig, setIsCheckingConfig] = useState(true);
  const [isOnboardingComplete, setIsOnboardingComplete] = useState(false);
  const [currentOnboardingStep, setCurrentOnboardingStep] = useState<OnboardingStep>(OnboardingStep.PATH_CHECK);

  // Check config status to determine if onboarding is needed
  useEffect(() => {
    const checkConfigStatus = async (): Promise<void> => {
      try {
        const { data: configStatus } = await getConfigStatus({
          meta: { skipWsAck: true },
        });

        // Onboarding is complete once the user has consented (backfilled on
        // completion) and registered a project. The PATH check is advisory
        // and never gates completion.
        const isComplete = configStatus.hasPrivacyConsent && configStatus.hasProject;

        if (isComplete) {
          setIsOnboardingComplete(true);
        } else {
          // New users start at the PATH-check screen; returning users without
          // a project still pass through it before reaching add-repo.
          setCurrentOnboardingStep(OnboardingStep.PATH_CHECK);
          setIsOnboardingComplete(false);
        }
      } catch (error) {
        console.error("Failed to check config status:", error);
        // If config check fails, assume onboarding is needed
        setIsOnboardingComplete(false);
        setCurrentOnboardingStep(OnboardingStep.PATH_CHECK);
      }
      setIsCheckingConfig(false);
    };

    checkConfigStatus();
  }, []);

  const handleOnboardingComplete = (): void => {
    setIsOnboardingComplete(true);
  };

  if (isCheckingConfig) {
    return <Spinner />;
  }

  if (!isOnboardingComplete) {
    return <OnboardingWizard initialStep={currentOnboardingStep} onComplete={handleOnboardingComplete} />;
  }

  return <>{children}</>;
};
