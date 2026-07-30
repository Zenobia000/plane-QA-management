/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

export type TEstimateTimeInputProps = {
  value?: number;
  handleEstimateInputValue: (value: string) => void;
};

/**
 * A time-denominated estimate point, entered as hours and minutes and stored as minutes.
 *
 * Minutes rather than a decimal of hours because 1.75h is a number people have to convert
 * before they can act on it, and because summing minutes is exact where summing thirds of
 * an hour is not.
 */
export function EstimateTimeInput({ value, handleEstimateInputValue }: TEstimateTimeInputProps) {
  const total = Number(value) || 0;
  const hours = Math.floor(total / 60);
  const minutes = total % 60;

  const emit = (nextHours: number, nextMinutes: number) =>
    handleEstimateInputValue(String(Math.max(0, nextHours) * 60 + Math.max(0, Math.min(59, nextMinutes))));

  return (
    <div className="flex items-center gap-1.5">
      <label className="flex items-center gap-1">
        <input
          type="number"
          min={0}
          aria-label="Hours"
          className="h-8 w-16 rounded border border-subtle bg-surface-1 px-2 text-12 text-primary outline-none focus:border-accent-strong"
          value={hours}
          onChange={(event) => emit(Number(event.target.value), minutes)}
        />
        <span className="text-11 text-tertiary">h</span>
      </label>
      <label className="flex items-center gap-1">
        <input
          type="number"
          min={0}
          max={59}
          aria-label="Minutes"
          className="h-8 w-16 rounded border border-subtle bg-surface-1 px-2 text-12 text-primary outline-none focus:border-accent-strong"
          value={minutes}
          onChange={(event) => emit(hours, Number(event.target.value))}
        />
        <span className="text-11 text-tertiary">m</span>
      </label>
    </div>
  );
}
