import Link from "next/link";
import styles from "./HomePage.module.css";

export const metadata = {
  title: "StorePlug | Simple online stores for sellers",
  description:
    "Create a mobile-first storefront, list products, receive orders, and sell through WhatsApp.",
};

const features = [
  "Mobile-first storefronts",
  "Product and stock management",
  "WhatsApp ordering",
  "Order tracking",
  "Seller dashboard",
  "Built for African micro-businesses",
];

export default function HomePage() {
  return (
    <main className={styles.page}>
      <section className={styles.hero}>
        <nav className={styles.nav}>
          <div className={styles.brand}>
            <span className={styles.logo}>SP</span>
            <span>StorePlug</span>
          </div>

          <a
            className={styles.navLink}
            href="https://dashboard.storeplughq.com"
          >
            Login
          </a>
        </nav>

        <div className={styles.heroGrid}>
          <div className={styles.heroCopy}>
            <p className={styles.kicker}>Storefronts for modern sellers</p>

            <h1>Launch your online store in minutes.</h1>

            <p className={styles.lead}>
              StorePlug helps small businesses create a clean storefront, list
              products, receive orders, and sell through WhatsApp without
              building a full website from scratch.
            </p>

            <div className={styles.actions}>
              <a
                className={styles.primaryBtn}
                href="https://dashboard.storeplughq.com"
              >
                Login to dashboard
              </a>

              <Link className={styles.secondaryBtn} href="/tgfashion">
                View demo store
              </Link>
            </div>
          </div>

          <div className={styles.previewCard} aria-label="Storefront preview">
            <div className={styles.previewTop}></div>

            <div className={styles.storeCard}>
              <div className={styles.avatar}>T</div>
              <p className={styles.category}>fashion</p>
              <h2>TG Fashion Store</h2>
              <p>Premium sneakers, fashion, and digital products.</p>

              <div className={styles.previewButtons}>
                <span>Message on WhatsApp</span>
                <span>Order now</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className={styles.features}>
        <p className={styles.sectionKicker}>Why StorePlug</p>
        <h2>Everything a seller needs to start taking orders online.</h2>

        <div className={styles.featureGrid}>
          {features.map((feature) => (
            <div className={styles.featureCard} key={feature}>
              <span></span>
              <p>{feature}</p>
            </div>
          ))}
        </div>
      </section>

      <section className={styles.cta}>
        <h2>Ready to give your business a store link?</h2>
        <p>
          Share one simple link with customers and manage everything from your
          dashboard.
        </p>

        <div className={styles.actions}>
          <a
            className={styles.primaryBtn}
            href="https://dashboard.storeplughq.com"
          >
            Go to dashboard
          </a>

          <Link className={styles.secondaryBtn} href="/tgfashion">
            See example
          </Link>
        </div>
      </section>
    </main>
  );
}
