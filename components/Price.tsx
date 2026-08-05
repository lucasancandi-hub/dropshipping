import { labels } from '@/lib/config';
import { discountPercent, formatPrice } from '@/lib/format';

type Props = {
  price: number | null;
  listPrice?: number | null;
  onRequest?: boolean;
  size?: 'sm' | 'lg';
};

/** Prezzo con eventuale prezzo pieno barrato e badge sconto. */
export function Price({ price, listPrice = null, onRequest = false, size = 'sm' }: Props) {
  if (onRequest || price === null) {
    return <span className="tag-request">{labels.priceOnRequest}</span>;
  }

  const discount = discountPercent(price, listPrice);
  const scale = size === 'lg' ? 'text-2xl' : 'text-[15px]';

  return (
    <span className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
      <span className={`${scale} font-semibold`}>{formatPrice(price)}</span>

      {listPrice !== null && listPrice > price && (
        <span
          className={`${size === 'lg' ? 'text-base' : 'text-sm'} text-neutral-400 line-through`}
        >
          {formatPrice(listPrice)}
        </span>
      )}

      {discount !== null && (
        <span className="rounded-full bg-neutral-900 px-2 py-0.5 text-xs font-medium text-white dark:bg-white dark:text-neutral-900">
          -{discount}%
        </span>
      )}
    </span>
  );
}
