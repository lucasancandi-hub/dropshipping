'use client';

type Props = {
  value: number;
  onChange: (value: number) => void;
  min?: number;
  max?: number;
  compact?: boolean;
};

/** Selettore quantità con area tap adeguata anche in versione compatta. */
export function QuantityStepper({ value, onChange, min = 1, max = 99, compact = false }: Props) {
  const clamp = (next: number) => onChange(Math.min(max, Math.max(min, next)));
  const height = compact ? 'h-9' : 'h-14';
  const width = compact ? 'w-8' : 'w-11';

  return (
    <div
      className={`inline-flex ${height} items-center rounded-full border border-neutral-200 dark:border-neutral-700`}
    >
      <button
        type="button"
        onClick={() => clamp(value - 1)}
        aria-label="Diminuisci quantità"
        className={`${width} h-full rounded-l-full text-lg leading-none transition hover:bg-neutral-100 dark:hover:bg-neutral-800`}
      >
        −
      </button>

      <input
        type="number"
        value={value}
        min={min}
        max={max}
        inputMode="numeric"
        aria-label="Quantità"
        onChange={(event) => clamp(Number.parseInt(event.target.value, 10) || min)}
        className={`${compact ? 'w-9 text-sm' : 'w-12 text-base'} h-full border-0 bg-transparent text-center font-semibold [appearance:textfield] focus:outline-none [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none`}
      />

      <button
        type="button"
        onClick={() => clamp(value + 1)}
        aria-label="Aumenta quantità"
        className={`${width} h-full rounded-r-full text-lg leading-none transition hover:bg-neutral-100 dark:hover:bg-neutral-800`}
      >
        +
      </button>
    </div>
  );
}
