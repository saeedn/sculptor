import { Box, Flex, SegmentedControl, Select, Separator, Switch } from "@radix-ui/themes";
import { useAtom, useAtomValue } from "jotai";
import { atomWithStorage } from "jotai/utils";
import { Monitor, Moon, Sun } from "lucide-react";
import { type ReactElement, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { themeSettingsAtom } from "~/common/state/atoms/theme.ts";
import { ModelSelectOptions } from "~/components/ModelSelectOptions.tsx";

import { ElementIds, UserConfigField } from "../../api";
import {
  configuredDefaultModelAtom,
  defaultEffortLevelAtom,
  isAlwaysInterruptAndSendAtom,
  isDefaultFastModeAtom,
  isEntityMentionsEnabledAtom,
  isPiAgentEnabledAtom,
  isRichMarkdownRenderingEnabledAtom,
  isSmoothStreamingUserPreferenceAtom,
  userEmailAtom,
} from "../../common/state/atoms/userConfig.ts";
import { useUserConfig } from "../../common/state/hooks/useUserConfig.ts";
import { mergeClasses, optional } from "../../common/Utils.ts";
import { EFFORT_DISPLAY_NAMES, EFFORT_OPTIONS } from "../../components/effortConstants.ts";
import type { ToastContent } from "../../components/Toast.tsx";
import { Toast, ToastType } from "../../components/Toast.tsx";
import { AccountFieldRow } from "./components/AccountFieldRow.tsx";
import { ActionsSettingsSection } from "./components/ActionsSettingsSection.tsx";
import { CIBabysitterSettingsSection } from "./components/CIBabysitterSettingsSection.tsx";
import { DependenciesSettingsSection } from "./components/DependenciesSettingsSection.tsx";
import { EnvironmentVariablesSection } from "./components/EnvironmentVariablesSection.tsx";
import { FileBrowserSettingsSection } from "./components/FileBrowserSettingsSection.tsx";
import { GitSettingsSection } from "./components/GitSettingsSection.tsx";
import { KeybindingsSection } from "./components/KeybindingsSection.tsx";
import { PiSettingsSection } from "./components/PiSettingsSection.tsx";
import { ReposSection } from "./components/ReposSection.tsx";
import { SettingRow } from "./components/SettingRow.tsx";
import { SettingsSectionLayout } from "./components/SettingsSection.tsx";
import { SETTINGS_SECTIONS, SettingsSection, type SettingsSectionId } from "./sections.ts";
import styles from "./SettingsPage.module.scss";

type SettingsSection = SettingsSectionId;

// Both maps are pure projections of the module-level SETTINGS_SECTIONS
// registry, so they're hoisted out of the component to avoid rebuilding
// them on every render.
const SECTION_DISPLAY_NAMES: Partial<Record<SettingsSection, string>> = Object.fromEntries(
  SETTINGS_SECTIONS.map((s) => [s.id, s.displayName]),
);
const SECTION_TEST_IDS: Partial<Record<SettingsSection, string>> = Object.fromEntries(
  SETTINGS_SECTIONS.map((s) => [s.id, s.testId]),
);
const getDisplayName = (section: SettingsSection): string => SECTION_DISPLAY_NAMES[section] ?? section;

const activeSectionAtom = atomWithStorage<SettingsSection>("sculptor-settings-active-section", SettingsSection.GENERAL);

export const SettingsPage = (): ReactElement => {
  const [activeSection, setActiveSection] = useAtom(activeSectionAtom);
  const [searchParams] = useSearchParams();

  // Apply ?section= query param once on mount (e.g. when linked from an error block).
  useEffect(() => {
    const sectionParam = searchParams.get("section");
    if (sectionParam && (Object.values(SettingsSection) as Array<string>).includes(sectionParam)) {
      setActiveSection(sectionParam as SettingsSection);
    }
  }, [searchParams, setActiveSection]);
  const [themeSettings, setThemeSettings] = useAtom(themeSettingsAtom);
  const configuredDefaultModel = useAtomValue(configuredDefaultModelAtom);
  const userEmail = useAtomValue(userEmailAtom);
  const isAlwaysInterruptAndSend = useAtomValue(isAlwaysInterruptAndSendAtom);
  const isPiAgentEnabled = useAtomValue(isPiAgentEnabledAtom);
  const visibleSections = SETTINGS_SECTIONS;
  // The mobile Select binds value={activeSection}, so its options must always
  // include the active section — even one normally hidden — or the trigger
  // renders blank.
  const mobileSections = SETTINGS_SECTIONS.filter((s) => visibleSections.includes(s) || s.id === activeSection);
  const isEntityMentionsEnabled = useAtomValue(isEntityMentionsEnabledAtom);
  const isRichMarkdownRenderingEnabled = useAtomValue(isRichMarkdownRenderingEnabledAtom);
  const isSmoothStreamingEnabled = useAtomValue(isSmoothStreamingUserPreferenceAtom);
  const isDefaultFastMode = useAtomValue(isDefaultFastModeAtom);
  const defaultEffortLevel = useAtomValue(defaultEffortLevelAtom);
  const [toast, setToast] = useState<ToastContent | null>(null);

  const { updateField } = useUserConfig();

  const handleSettingChange = async (fieldConstant: UserConfigField, value: unknown): Promise<void> => {
    try {
      await updateField(fieldConstant, value);
      setToast({
        type: ToastType.SUCCESS,
        title: "Setting updated",
      });
    } catch (error) {
      console.error(`Failed to update ${fieldConstant}:`, error);
      setToast({
        type: ToastType.ERROR,
        title: `Failed to update setting`,
      });
    }
  };

  return (
    <>
      <Flex
        direction="column"
        className={styles.container}
        style={{ containerName: "settings-page", containerType: "inline-size" }}
      >
        <Flex position="relative" flexGrow="1" data-testid={ElementIds.SETTINGS_PAGE} minHeight="0" overflow="hidden">
          <Flex direction="column" px="6" pt="8" pb="4" className={styles.sidebar}>
            <Flex direction="column" gap="2">
              {visibleSections.map(({ id }) => (
                <Box key={id}>
                  {id === SettingsSection.EXPERIMENTAL && <Separator size="4" my="2" className={styles.navSeparator} />}
                  <Box
                    className={mergeClasses(styles.navItem, optional(activeSection === id, styles.active))}
                    onClick={() => setActiveSection(id)}
                    px="3"
                    py="2"
                    data-testid={SECTION_TEST_IDS[id] ?? ""}
                  >
                    {getDisplayName(id)}
                  </Box>
                </Box>
              ))}
            </Flex>
          </Flex>
          <div className={styles.contentScroll} data-testid={ElementIds.SETTINGS_CONTENT}>
            <Flex direction="column" className={styles.mobileNav} px="5" pt="5">
              <Select.Root value={activeSection} onValueChange={(value) => setActiveSection(value as SettingsSection)}>
                <Select.Trigger variant="soft" />
                <Select.Content>
                  {mobileSections.map(({ id }) => (
                    <Select.Item key={id} value={id} data-testid={SECTION_TEST_IDS[id] ?? ""}>
                      {getDisplayName(id)}
                    </Select.Item>
                  ))}
                </Select.Content>
              </Select.Root>
            </Flex>
            <Flex className={styles.contentArea}>
              {activeSection === SettingsSection.GENERAL && (
                <SettingsSectionLayout description="General application preferences.">
                  <SettingRow title="Theme" description="Control the appearance of Sculptor">
                    <SegmentedControl.Root
                      value={themeSettings.appearance}
                      onValueChange={(value) =>
                        setThemeSettings((prev) => ({
                          ...prev,
                          appearance: value as "light" | "dark" | "system",
                        }))
                      }
                      size="2"
                      className={styles.themeToggle}
                      data-testid={ElementIds.SETTINGS_THEME_SELECT}
                    >
                      <SegmentedControl.Item value="light">
                        <Flex align="center" gap="1">
                          <Sun size={16} />
                          Light
                        </Flex>
                      </SegmentedControl.Item>
                      <SegmentedControl.Item value="dark">
                        <Flex align="center" gap="1">
                          <Moon size={16} />
                          Dark
                        </Flex>
                      </SegmentedControl.Item>
                      <SegmentedControl.Item value="system">
                        <Flex align="center" gap="1">
                          <Monitor size={16} />
                          System
                        </Flex>
                      </SegmentedControl.Item>
                    </SegmentedControl.Root>
                  </SettingRow>
                </SettingsSectionLayout>
              )}
              {activeSection === SettingsSection.AGENT && (
                <SettingsSectionLayout description="Configure default agent behavior and model preferences.">
                  <SettingRow title="Default Model" description="Select the default model for new agents.">
                    <Select.Root
                      value={configuredDefaultModel ?? "None"}
                      onValueChange={(value) => {
                        if (value === "None") {
                          handleSettingChange(UserConfigField.DEFAULT_LLM, null);
                        } else {
                          handleSettingChange(UserConfigField.DEFAULT_LLM, value);
                        }
                      }}
                    >
                      <Select.Trigger
                        variant="soft"
                        className={styles.settingControl}
                        data-testid={ElementIds.SETTINGS_DEFAULT_MODEL_SELECT}
                      />
                      <Select.Content>
                        <Select.Item key="None" value="None">
                          Most Recently Used
                        </Select.Item>
                        <ModelSelectOptions optionTestId={ElementIds.SETTINGS_DEFAULT_MODEL_OPTION} />
                      </Select.Content>
                    </Select.Root>
                  </SettingRow>

                  <SettingRow
                    title="Fast Mode"
                    description="When enabled, new agents default to fast mode for faster output."
                  >
                    <Switch
                      checked={isDefaultFastMode}
                      onCheckedChange={(checked) => handleSettingChange(UserConfigField.DEFAULT_FAST_MODE, checked)}
                      data-testid={ElementIds.SETTINGS_DEFAULT_FAST_MODE_TOGGLE}
                    />
                  </SettingRow>

                  <SettingRow title="Effort Level" description="Default thinking effort level for new agents.">
                    <Select.Root
                      value={defaultEffortLevel}
                      onValueChange={(value) => handleSettingChange(UserConfigField.DEFAULT_EFFORT_LEVEL, value)}
                    >
                      <Select.Trigger
                        variant="soft"
                        className={styles.settingControl}
                        data-testid={ElementIds.SETTINGS_DEFAULT_EFFORT_LEVEL_SELECT}
                      />
                      <Select.Content>
                        {EFFORT_OPTIONS.map((level) => (
                          <Select.Item
                            key={level}
                            value={level}
                            data-testid={ElementIds.SETTINGS_DEFAULT_EFFORT_LEVEL_OPTION}
                          >
                            {EFFORT_DISPLAY_NAMES[level]}
                          </Select.Item>
                        ))}
                      </Select.Content>
                    </Select.Root>
                  </SettingRow>
                </SettingsSectionLayout>
              )}
              {activeSection === SettingsSection.DEPENDENCIES && (
                <DependenciesSettingsSection onSettingChange={handleSettingChange} />
              )}
              {activeSection === SettingsSection.PI && (
                <PiSettingsSection
                  onSettingChange={handleSettingChange}
                  onNavigateToExperimental={() => setActiveSection(SettingsSection.EXPERIMENTAL)}
                />
              )}
              {activeSection === SettingsSection.KEYBINDINGS && (
                <KeybindingsSection onSettingChange={handleSettingChange} />
              )}
              {activeSection === SettingsSection.PRIVACY && (
                <SettingsSectionLayout description="Your email address.">
                  <AccountFieldRow
                    title="Email Address"
                    description="Email address associated with your account"
                    value={userEmail ?? ""}
                    elementId={ElementIds.SETTINGS_EMAIL_FIELD}
                  />
                </SettingsSectionLayout>
              )}
              {activeSection === SettingsSection.REPOSITORIES && <ReposSection setToast={setToast} />}
              {activeSection === SettingsSection.ACTIONS && <ActionsSettingsSection setToast={setToast} />}
              {activeSection === SettingsSection.GIT && <GitSettingsSection onSettingChange={handleSettingChange} />}
              {activeSection === SettingsSection.CI && (
                <CIBabysitterSettingsSection onSettingChange={handleSettingChange} />
              )}
              {activeSection === SettingsSection.FILE_BROWSER && (
                <FileBrowserSettingsSection onSettingChange={handleSettingChange} />
              )}
              {activeSection === SettingsSection.PROJECT_ENV_VARS && (
                <EnvironmentVariablesSection onSettingChange={handleSettingChange} />
              )}
              {activeSection === SettingsSection.EXPERIMENTAL && (
                <SettingsSectionLayout description="Features that are still being developed. These may change or be removed.">
                  <SettingRow
                    title="Always interrupt and send"
                    description="When enabled, new messages immediately interrupt the agent instead of being queued."
                  >
                    <Select.Root
                      value={isAlwaysInterruptAndSend ? "true" : "false"}
                      onValueChange={(value) =>
                        handleSettingChange(UserConfigField.IS_ALWAYS_INTERRUPT_AND_SEND, value === "true")
                      }
                    >
                      <Select.Trigger variant="soft" data-testid={ElementIds.SETTINGS_ALWAYS_INTERRUPT_SELECT} />
                      <Select.Content>
                        <Select.Item value="false" data-testid={ElementIds.SETTINGS_ALWAYS_INTERRUPT_DISABLED_OPTION}>
                          Disabled
                        </Select.Item>
                        <Select.Item value="true" data-testid={ElementIds.SETTINGS_ALWAYS_INTERRUPT_OPTION}>
                          Enabled
                        </Select.Item>
                      </Select.Content>
                    </Select.Root>
                  </SettingRow>
                  <SettingRow
                    title="Smooth Streaming"
                    description="Smoothly animate text as it streams in, rather than showing it in bursts."
                  >
                    <Switch
                      checked={isSmoothStreamingEnabled}
                      onCheckedChange={(checked) =>
                        handleSettingChange(UserConfigField.IS_SMOOTH_STREAMING_ENABLED, checked)
                      }
                    />
                  </SettingRow>
                  <SettingRow
                    title="Entity Mentions"
                    description="Type + in the chat input to mention repositories, workspaces, and agents."
                  >
                    <Switch
                      checked={isEntityMentionsEnabled}
                      onCheckedChange={(checked) =>
                        handleSettingChange(UserConfigField.ENABLE_ENTITY_MENTIONS, checked)
                      }
                      data-testid={ElementIds.SETTINGS_ENABLE_ENTITY_MENTIONS_TOGGLE}
                    />
                  </SettingRow>
                  <SettingRow
                    title="Rich markdown rendering"
                    description="Render .md and .markdown files as formatted HTML in the file viewer instead of source. Toggle via the eye icon in the diff toolbar."
                  >
                    <Switch
                      checked={isRichMarkdownRenderingEnabled}
                      onCheckedChange={(checked) =>
                        handleSettingChange(UserConfigField.ENABLE_RICH_MARKDOWN_RENDERING, checked)
                      }
                      data-testid={ElementIds.SETTINGS_ENABLE_RICH_MARKDOWN_RENDERING_TOGGLE}
                    />
                  </SettingRow>
                  <SettingRow
                    title="Pi agent"
                    description="Offer the experimental pi agent as a choice when creating new agents."
                  >
                    <Switch
                      checked={isPiAgentEnabled}
                      onCheckedChange={(checked) => handleSettingChange(UserConfigField.ENABLE_PI_AGENT, checked)}
                      data-testid={ElementIds.SETTINGS_ENABLE_PI_AGENT_TOGGLE}
                    />
                  </SettingRow>
                </SettingsSectionLayout>
              )}
            </Flex>
          </div>
        </Flex>
      </Flex>
      <Toast
        open={!!toast}
        onOpenChange={(open) => !open && setToast(null)}
        title={toast?.title}
        description={toast?.description}
        type={toast?.type}
      />
    </>
  );
};
