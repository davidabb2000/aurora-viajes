import Sidebar from "../components/Sidebar";

function AdminLayout({ children }) {
  return (
    <div className="min-h-screen">
      <Sidebar />
      {/* El desplazamiento coincide con el ancho real de la barra (w-72). */}
      <div className="flex min-h-screen flex-col md:ml-72">
        <main className="flex-1 px-3 pb-12 pt-4 sm:px-6">
          {children}
        </main>
      </div>
    </div>
  );
}

export default AdminLayout;
