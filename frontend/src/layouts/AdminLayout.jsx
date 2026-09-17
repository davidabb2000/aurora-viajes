import Sidebar from "../components/Sidebar";
import Footer from "../components/Footer";

function AdminLayout({ children }) {
  return (
    <div className="min-h-screen">
      <Sidebar />
      <div className="min-h-screen md:ml-64">
        <main className="min-h-screen">
          {children}
        </main>
        <Footer />
      </div>
    </div>
  );
}

export default AdminLayout;
