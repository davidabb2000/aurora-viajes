import Header from "../components/Header";
import Footer from "../components/Footer";
import WhatsAppButton from "../components/WhatsAppButton";

function ClientLayout({ children }) {
  return (
    <>
      <Header />
      <main className="flex flex-1 flex-col">
        {children}
      </main>
      <Footer />
      <WhatsAppButton />
    </>
  );
}

export default ClientLayout;
