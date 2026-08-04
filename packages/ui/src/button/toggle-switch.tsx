/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { Switch } from "@headlessui/react";
// helpers
import { cn } from "../utils";

interface IToggleSwitchProps {
  value: boolean;
  onChange: (value: boolean) => void;
  /** Screen-reader-only name. Use `labelContent` when the text is meant to be seen. */
  label?: string;
  /**
   * Visible, clickable label rendered beside the switch.
   *
   * Worth having on the component rather than at each call site: three call sites had
   * built their own by wrapping the switch in a div that carried the click, and passing
   * the switch an empty `onChange` so the two would not both fire. That works for a mouse
   * and leaves the keyboard dead, because Headless UI routes Space through the switch's
   * own handler -- straight into the empty function. `Switch.Label` is clickable and
   * associated natively, so the switch keeps its real handler and nothing needs a wrapper.
   */
  labelContent?: React.ReactNode;
  labelClassName?: string;
  size?: "sm" | "md" | "lg";
  disabled?: boolean;
  className?: string;
}

function ToggleSwitch(props: IToggleSwitchProps) {
  const { value, onChange, label, labelContent, labelClassName, size = "sm", disabled, className } = props;

  const control = (
    <Switch
      checked={value}
      disabled={disabled}
      onChange={onChange}
      className={cn(
        "relative inline-flex h-6 w-10 flex-shrink-0 cursor-pointer rounded-full border border-subtle bg-layer-1 transition-colors duration-200 ease-in-out focus:outline-none",
        {
          "h-4 w-7": size === "sm",
          "h-5 w-9": size === "md",
          "bg-accent-primary": value && !disabled,
          "bg-(--text-color-icon-placeholder)": !value && !disabled,
          "cursor-not-allowed bg-accent-primary opacity-50": value && disabled,
          "cursor-not-allowed bg-(--text-color-icon-placeholder) opacity-50": !value && disabled,
        },
        className
      )}
    >
      <span className="sr-only">{label}</span>
      <span
        aria-hidden="true"
        className={cn(
          "inline-block h-5 w-5 transform self-center rounded-full bg-(--text-color-icon-on-color) ring-0 transition duration-200 ease-in-out",
          {
            "h-3 w-3 translate-x-3.5": size === "sm" && value,
            "h-3 w-3 translate-x-0.5": size === "sm" && !value,
            "h-4 w-4 translate-x-4": size === "md" && value,
            "h-4 w-4 translate-x-0.5": size === "md" && !value,
            "translate-x-4": size === "lg" && value,
            "translate-x-0.5": size === "lg" && !value,
          }
        )}
      />
    </Switch>
  );

  if (!labelContent) return control;

  return (
    <Switch.Group as="div" className="inline-flex items-center gap-1.5">
      {control}
      <Switch.Label className={cn("cursor-pointer select-none", { "cursor-not-allowed": disabled }, labelClassName)}>
        {labelContent}
      </Switch.Label>
    </Switch.Group>
  );
}

ToggleSwitch.displayName = "plane-ui-toggle-switch";

export { ToggleSwitch };
