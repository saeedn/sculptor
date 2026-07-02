import { Box, Flex, SegmentedControl, Select } from "@radix-ui/themes";
import { useAtom } from "jotai";
import { atomWithStorage } from "jotai/utils";
import { Monitor, Moon, Sun } from "lucide-react";
import { type ReactElement, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { themeSettingsAtom } from "~/common/state/atoms/theme.ts";

import type { UserConfigField } from "../../api";
import { ElementIds } from "../../api";
import { useUserConfig } from "../../common/state/hooks/useUserConfig.ts";
import { mergeClasses, optional } from "../../common/Utils.ts";
import type { ToastContent } from "../../components/Toast.tsx";
import { Toast, ToastType } from "../../components/Toast.tsx";
import { ActionsSettingsSection } from "./components/ActionsSettingsSection.tsx";
import { CIBabysitterSettingsSection } from "./components/CIBabysitterSettingsSection.tsx";
import { EnvironmentVariablesSection } from "./components/EnvironmentVariablesSection.tsx";
import { FileBrowserSettingsSection } from "./components/FileBrowserSettingsSection.tsx";
import { GitSettingsSection } from "./components/GitSettingsSection.tsx";
import { KeybindingsSection } from "./components/KeybindingsSection.tsx";
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
              {SETTINGS_SECTIONS.map(({ id }) => (
                <Box key={id}>
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
                  {SETTINGS_SECTIONS.map(({ id }) => (
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
              {activeSection === SettingsSection.KEYBINDINGS && (
                <KeybindingsSection onSettingChange={handleSettingChange} />
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
