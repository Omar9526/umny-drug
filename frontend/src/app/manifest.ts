import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Умный друг",
    short_name: "Умный друг",
    description: "Твой умный друг по учёбе",
    start_url: "/",
    display: "standalone",
    orientation: "portrait",
    background_color: "#FBFBF6",
    theme_color: "#005359",
    lang: "ru",
    categories: ["education", "kids"],
    icons: [
      { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png" },
      { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png" },
      { src: "/icons/icon-512-maskable.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
  };
}
