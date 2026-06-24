import { Flex } from "@radix-ui/themes";
import type { ReactElement } from "react";
import { useState } from "react";

import { completeOnboarding, getConfigStatus } from "~/api";
import { HTTPException } from "~/common/Errors.ts";
import { TitleBar } from "~/components/TitleBar";

import { AddRepoStep } from "./AddRepoStep.tsx";
import styles from "./OnboardingWizard.module.scss";
import { PathCheckStep } from "./PathCheckStep.tsx";
import { StepIndicator } from "./StepIndicator.tsx";

// eslint-disable-next-line react-refresh/only-export-components -- enum-style const shared with non-component code
export const OnboardingStep = {
  PATH_CHECK: "PATH_CHECK",
  ADD_REPO: "ADD_REPO",
} as const;

export type OnboardingStep = (typeof OnboardingStep)[keyof typeof OnboardingStep];

const STEP_ORDER: Array<OnboardingStep> = [OnboardingStep.PATH_CHECK, OnboardingStep.ADD_REPO];
const STEP_COUNT = STEP_ORDER.length;

type OnboardingWizardProps = {
  initialStep: OnboardingStep;
  onComplete: () => void;
};

export const OnboardingWizard = ({ initialStep, onComplete }: OnboardingWizardProps): ReactElement => {
  const [currentStep, setCurrentStep] = useState<OnboardingStep>(initialStep);
  const [maxVisitedStep, setMaxVisitedStep] = useState(STEP_ORDER.indexOf(initialStep));
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const goToStep = (step: OnboardingStep): void => {
    setCurrentStep(step);
    setMaxVisitedStep((prev) => Math.max(prev, STEP_ORDER.indexOf(step)));
    setError(null);
  };

  const handlePathCheckContinue = async (): Promise<void> => {
    setIsLoading(true);
    setError(null);

    try {
      // Returning users who already have a project skip the add-repo step.
      const { data: configStatus } = await getConfigStatus({ meta: { skipWsAck: true } });
      if (configStatus?.hasProject) {
        await completeOnboarding({ meta: { skipWsAck: true } });
        onComplete();
        return;
      }

      goToStep(OnboardingStep.ADD_REPO);
    } catch (error) {
      let errorMessage = "Failed to check configuration";
      if (error instanceof HTTPException) {
        errorMessage = error.detail;
      } else if (error instanceof Error) {
        errorMessage = error.message;
      }
      setError(errorMessage);
    } finally {
      setIsLoading(false);
    }
  };

  const handleAddRepoComplete = async (): Promise<void> => {
    setIsLoading(true);
    setError(null);

    try {
      await completeOnboarding({
        meta: { skipWsAck: true },
      });

      onComplete();
    } catch (error) {
      let errorMessage = "Failed to complete onboarding";
      if (error instanceof HTTPException) {
        errorMessage = error.detail;
      } else if (error instanceof Error) {
        errorMessage = error.message;
      }
      setError(errorMessage);
    } finally {
      setIsLoading(false);
    }
  };

  const handleStepClick = (index: number): void => {
    goToStep(STEP_ORDER[index]);
  };

  const currentStepIndex = STEP_ORDER.indexOf(currentStep);

  const renderStep = (): ReactElement => {
    if (currentStep === OnboardingStep.PATH_CHECK) {
      return <PathCheckStep onContinue={handlePathCheckContinue} isLoading={isLoading} />;
    }

    return <AddRepoStep onComplete={handleAddRepoComplete} isLoading={isLoading} error={error} />;
  };

  return (
    <Flex direction="column" className={styles.wizardContainer}>
      <TitleBar />
      <Flex direction="column" className={styles.contentArea}>
        <div className={styles.stepContent}>{renderStep()}</div>
      </Flex>
      <StepIndicator
        totalSteps={STEP_COUNT}
        currentStep={currentStepIndex}
        maxVisitedStep={maxVisitedStep}
        onStepClick={handleStepClick}
      />
    </Flex>
  );
};
