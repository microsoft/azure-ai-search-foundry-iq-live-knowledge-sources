import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Foundry IQ Live Knowledge Sources',
  description: 'Demo app for MCP Server and Fabric Ontology Knowledge Sources.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
