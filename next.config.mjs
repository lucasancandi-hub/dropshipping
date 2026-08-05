/** @type {import('next').NextConfig} */
const nextConfig = {
  // Il catalogo arriva da CDN esterni che cambiano col fornitore: le immagini
  // restano <img> semplici, così non serve mantenere una allowlist di host né
  // consumare la quota di ottimizzazione immagini di Vercel.
  reactStrictMode: true,
  poweredByHeader: false,
};

export default nextConfig;
