import { ImageResponse } from 'next/og';

import { shop } from '@/lib/config';

// Favicon generata a build time: nessun file binario da mantenere nel repo.
export const size = { width: 64, height: 64 };
export const contentType = 'image/png';

export default function Icon() {
  return new ImageResponse(
    (
      <div
        style={{
          width: '100%',
          height: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: '#111418',
          color: '#ffffff',
          fontSize: 38,
          fontWeight: 700,
          borderRadius: 14,
        }}
      >
        {shop.name.trim().charAt(0).toUpperCase() || 'A'}
      </div>
    ),
    size,
  );
}
