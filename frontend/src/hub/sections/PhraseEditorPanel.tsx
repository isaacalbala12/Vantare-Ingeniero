import { CollapsibleSection } from "../components/CollapsibleSection";
import { t } from "../../i18n/strings";
import { useAppStore } from "../../store/config";

export type PhraseCategory = "spotter" | "triggers";
export type PhraseProfile = "standard" | "formal" | "aggressive";

export interface PhraseCatalog {
  spotter: Record<string, Record<string, string>>;
  triggers: Record<string, Record<string, string>>;
}

export function templateToLines(template: string): string {
  return template
    .split("|")
    .map((line) => line.trim())
    .filter(Boolean)
    .join("\n");
}

export function linesToTemplate(text: string): string {
  return text
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .join("|");
}

export function listSpotterKeys(catalog: PhraseCatalog, profile: PhraseProfile): string[] {
  return Object.keys(catalog.spotter[profile] ?? {}).sort();
}

export function listTriggerKeys(catalog: PhraseCatalog): string[] {
  return Object.keys(catalog.triggers ?? {}).sort();
}

export function readMergedTemplate(
  catalog: PhraseCatalog,
  category: PhraseCategory,
  profile: PhraseProfile,
  key: string,
): string {
  if (category === "spotter") {
    return catalog.spotter[profile]?.[key] ?? "";
  }
  return catalog.triggers[key]?.[profile] ?? "";
}

/** Construye overrides usuario: solo entradas distintas del bundle. */
export function buildUserOverrides(
  _merged: PhraseCatalog,
  defaults: PhraseCatalog,
  category: PhraseCategory,
  profile: PhraseProfile,
  key: string,
  template: string,
  existing: PhraseCatalog,
): PhraseCatalog {
  const user: PhraseCatalog = {
    spotter: { ...(existing.spotter ?? {}) },
    triggers: { ...(existing.triggers ?? {}) },
  };
  const defaultTemplate =
    category === "spotter"
      ? defaults.spotter[profile]?.[key] ?? ""
      : defaults.triggers[key]?.[profile] ?? "";

  if (template.trim() === defaultTemplate.trim()) {
    if (category === "spotter") {
      const profileMap = { ...(user.spotter[profile] ?? {}) };
      delete profileMap[key];
      if (Object.keys(profileMap).length) {
        user.spotter[profile] = profileMap;
      } else {
        delete user.spotter[profile];
      }
    } else {
      const keyMap = { ...(user.triggers[key] ?? {}) };
      delete keyMap[profile];
      if (Object.keys(keyMap).length) {
        user.triggers[key] = keyMap;
      } else {
        delete user.triggers[key];
      }
    }
    return user;
  }

  if (category === "spotter") {
    user.spotter[profile] = { ...(user.spotter[profile] ?? {}), [key]: template };
  } else {
    user.triggers[key] = { ...(user.triggers[key] ?? {}), [profile]: template };
  }
  return user;
}

interface PhraseEditorPanelProps {
  merged: PhraseCatalog | null;
  defaults: PhraseCatalog | null;
  category: PhraseCategory;
  profile: PhraseProfile;
  selectedKey: string;
  draftLines: string;
  status: string;
  busy: boolean;
  onCategory: (c: PhraseCategory) => void;
  onProfile: (p: PhraseProfile) => void;
  onKey: (key: string) => void;
  onDraftLines: (text: string) => void;
  onSave: () => void;
  onExport: () => void;
  onImport: () => void;
  onReset: () => void;
}

export function PhraseEditorPanel({
  merged,
  defaults,
  category,
  profile,
  selectedKey,
  draftLines,
  status,
  busy,
  onCategory,
  onProfile,
  onKey,
  onDraftLines,
  onSave,
  onExport,
  onImport,
  onReset,
}: PhraseEditorPanelProps) {
  const uiLanguage = useAppStore((s) => s.config.uiLanguage);
  const keys =
    merged && category === "spotter"
      ? listSpotterKeys(merged, profile)
      : merged
        ? listTriggerKeys(merged)
        : [];

  return (
    <CollapsibleSection title={t(uiLanguage, "customPhrases")} defaultOpen>
      <p className="text-[10px] text-a1-text-muted leading-relaxed mb-2">
        {t(uiLanguage, "phraseEditorHelp")}
      </p>
      <div className="flex flex-wrap gap-2 mb-2">
        <select
          value={category}
          onChange={(e) => onCategory(e.target.value as PhraseCategory)}
          className="bg-[#1a1a1a] border border-[#333] rounded px-2 py-1 text-[11px] text-white"
        >
          <option value="spotter">Spotter</option>
          <option value="triggers">Triggers</option>
        </select>
        <select
          value={profile}
          onChange={(e) => onProfile(e.target.value as PhraseProfile)}
          className="bg-[#1a1a1a] border border-[#333] rounded px-2 py-1 text-[11px] text-white"
        >
          <option value="standard">Standard</option>
          <option value="formal">Formal</option>
          <option value="aggressive">Aggressive</option>
        </select>
        <select
          value={selectedKey}
          onChange={(e) => onKey(e.target.value)}
          className="flex-1 min-w-[140px] bg-[#1a1a1a] border border-[#333] rounded px-2 py-1 text-[11px] text-white"
        >
          {keys.map((k) => (
            <option key={k} value={k}>
              {k}
            </option>
          ))}
        </select>
      </div>
      <textarea
        value={draftLines}
        onChange={(e) => onDraftLines(e.target.value)}
        rows={5}
        disabled={!merged || busy}
        className="w-full bg-[#1a1a1a] border border-[#333] rounded px-2 py-1.5 text-[11px] text-white font-mono"
        placeholder={t(uiLanguage, "oneVariantPerLine")}
      />
      {defaults && merged && selectedKey && (
        <p className="text-[9px] text-a1-text-muted mt-1">
          Default bundle:{" "}
          {templateToLines(
            readMergedTemplate(defaults, category, profile, selectedKey) || `(${t(uiLanguage, "empty")})`,
          ).replace(/\n/g, " · ")}
        </p>
      )}
      <div className="flex flex-wrap gap-2 mt-2">
        <button type="button" className="hub-btn-secondary text-[11px]" disabled={busy} onClick={onSave}>
          {t(uiLanguage, "savePhrase")}
        </button>
        <button type="button" className="hub-btn-secondary text-[11px]" disabled={busy} onClick={onExport}>
          {t(uiLanguage, "exportJson")}
        </button>
        <button type="button" className="hub-btn-secondary text-[11px]" disabled={busy} onClick={onImport}>
          {t(uiLanguage, "importJson")}
        </button>
        <button type="button" className="hub-btn-secondary text-[11px]" disabled={busy} onClick={onReset}>
          {t(uiLanguage, "restoreDefaults")}
        </button>
      </div>
      {status && <span className="text-[10px] text-a1-text-muted mt-1 block">{status}</span>}
    </CollapsibleSection>
  );
}
