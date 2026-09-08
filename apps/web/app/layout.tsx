import type { Metadata } from 'next';
import './globals.css';
export const metadata: Metadata = { title: 'Topo · Map explorer', description: 'Explore locally generated OpenStreetMap tiles.' };
export default function RootLayout({children}: {children: React.ReactNode}) {return <html lang="en"><body>{children}</body></html>}
