import type { Metadata } from "next";
import { Sora, Space_Mono } from "next/font/google";
import "./globals.css";

const sora = Sora({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const spaceMono = Space_Mono({
  variable: "--font-geist-mono",
  weight: ["400", "700"],
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "YL Olympic Draft",
  description: "Draft athletes with friends across Olympic events.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${sora.variable} ${spaceMono.variable} antialiased`}
      >
        {children}
      </body>
    </html>
  );
}
