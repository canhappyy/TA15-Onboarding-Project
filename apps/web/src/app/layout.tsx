import type { Metadata } from "next"
import "leaflet/dist/leaflet.css"
import "./globals.css"

import { ThemeProvider } from "@/components/providers/theme-provider"

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
    <html lang="en" suppressHydrationWarning>
      <body>
        <ThemeProvider>
          <main className="min-h-screen p-4">
            {children}
          </main>
        </ThemeProvider>
      </body>
    </html>
  )
}