import Header from "../components/Header";
import Footer from "../components/Footer";
import WhatsAppButton from "../components/WhatsAppButton";

function ClientLayout({ children }) {
  return (
    <>
      <Header />
      <main className="min-h-screen">
        {children}
      </main>
      <Footer />
      <WhatsAppButton />
    </>
  );
}

export default ClientLayout;
