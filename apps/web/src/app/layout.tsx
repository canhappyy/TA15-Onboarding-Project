import type { Metadata } from "next"
import { Inter, Geist_Mono } from "next/font/google" // <-- Import fonts
import "leaflet/dist/leaflet.css"
import "./globals.css"

import { ThemeProvider } from "@/components/providers/theme-provider"

// Configure font variables
const inter = Inter({
  subsets: ["latin"],
  variable: "--font-sans",
})

const geistMono = Geist_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
})

export const metadata: Metadata = {
  title: "ClearWaY",
  description: "Accessible journey planning and crowd information",
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en" className={`${inter.variable} ${geistMono.variable}`} suppressHydrationWarning>
      <body>
        <ThemeProvider>
          <main className="min-h-screen bg-[#eef3fa] p-4 transition-colors duration-300 dark:bg-slate-950">
            {children}
          </main>
        </ThemeProvider>
      </body>
    </html>
  )
}
