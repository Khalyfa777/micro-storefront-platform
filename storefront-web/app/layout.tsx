import "./globals.css";

export const metadata = {
  title: "Micro Storefront Platform",
  description: "Create a beautiful storefront and sell online in minutes.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
