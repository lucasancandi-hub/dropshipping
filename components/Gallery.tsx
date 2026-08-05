'use client';

import { useState } from 'react';

/**
 * Galleria prodotto: immagine grande + miniature in griglia fluida.
 *
 * Con una sola immagine le miniature spariscono; su mobile la griglia diventa
 * una colonna sola.
 */
export function Gallery({ images, title }: { images: string[]; title: string }) {
  const [active, setActive] = useState(0);

  if (images.length === 0) {
    return <div className="aspect-4/5 w-full rounded-card bg-neutral-100 dark:bg-neutral-900" />;
  }

  const current = images[Math.min(active, images.length - 1)];

  return (
    <div className="flex flex-col gap-3">
      <img
        key={current}
        src={current}
        alt={`${title} — immagine ${active + 1} di ${images.length}`}
        decoding="async"
        className="aspect-4/5 w-full rounded-card bg-neutral-100 object-cover dark:bg-neutral-900"
      />

      {images.length > 1 && (
        <ul className="grid grid-cols-4 gap-3 sm:grid-cols-5">
          {images.map((image, index) => (
            <li key={image}>
              <button
                type="button"
                onClick={() => setActive(index)}
                aria-label={`Mostra immagine ${index + 1}`}
                aria-current={index === active}
                className={`block w-full overflow-hidden rounded-xl transition ${
                  index === active
                    ? 'opacity-100 ring-2 ring-neutral-900 dark:ring-white'
                    : 'opacity-60 hover:opacity-100'
                }`}
              >
                <img
                  src={image}
                  alt=""
                  loading="lazy"
                  decoding="async"
                  className="aspect-square w-full bg-neutral-100 object-cover dark:bg-neutral-900"
                />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
