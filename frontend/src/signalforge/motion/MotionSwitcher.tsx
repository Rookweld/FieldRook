import { applyMotionMode, useMotionMode } from "./motionPreference";
import type { MotionMode } from "./motionPreference";

type MotionChoice = {
  value: MotionMode;
  label: string;
  hint: string;
};

const CHOICES: MotionChoice[] = [
  { value: "alive", label: "Alive", hint: "Full ambient motion" },
  { value: "quiet", label: "Quiet", hint: "Dimmed, slowed motion" },
  { value: "off", label: "Off", hint: "No decorative motion" },
];

type MotionSwitcherProps = {
  /** Accessible group label. Defaults to "Motion". */
  label?: string;
  /** Optional id prefix when several switchers share a page. */
  idPrefix?: string;
};

/**
 * Keyboard-operable Alive/Quiet/Off switcher. Real radio inputs give free
 * arrow-key + tab behaviour, focus-visible styling, and screen-reader
 * semantics; choosing a mode persists `fieldrook.motion.v1` and flips
 * `body[data-motion]` immediately.
 */
export function MotionSwitcher({ label = "Motion", idPrefix = "sf-motion" }: MotionSwitcherProps) {
  const mode = useMotionMode();
  return (
    <div className="sf-motion-switcher" role="radiogroup" aria-label={label}>
      {CHOICES.map((choice) => {
        const id = `${idPrefix}-${choice.value}`;
        return (
          <span className="sf-motion-option" key={choice.value}>
            <input
              type="radio"
              id={id}
              name={idPrefix}
              value={choice.value}
              checked={mode === choice.value}
              onChange={() => applyMotionMode(choice.value)}
              aria-describedby={`${id}-hint`}
            />
            <label className="sf-motion-label" htmlFor={id} title={choice.hint}>
              {choice.label}
            </label>
            <span id={`${id}-hint`} hidden>
              {choice.hint}
            </span>
          </span>
        );
      })}
    </div>
  );
}
