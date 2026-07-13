import "./globals.css";

export const metadata = {
  title: "StorePlug",
  description:
    "Discover products and order directly from StorePlug storefronts.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
