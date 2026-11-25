import './globals.css';

export const metadata = {
  title: 'CineSense — Find your next favorite',
  description: 'A more personal way to discover what to watch next.',
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
