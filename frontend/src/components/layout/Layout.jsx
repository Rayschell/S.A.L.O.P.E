import { useState } from 'react'
import { Outlet } from 'react-router-dom'
import Navbar from './Navbar.jsx'
import Sidebar from './Sidebar.jsx'

export default function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(true)

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateRows: '56px 1fr',
        gridTemplateColumns: sidebarOpen ? '220px 1fr' : '1fr',
        height: '100vh',
        overflow: 'hidden',
      }}
    >
      <Navbar onToggleSidebar={() => setSidebarOpen((v) => !v)} />
      {sidebarOpen && <Sidebar />}
      <main
        style={{
          gridRow: 2,
          gridColumn: sidebarOpen ? 2 : 1,
          overflowY: 'auto',
          padding: 28,
          background: 'var(--bg-base)',
          minWidth: 0,
        }}
      >
        <Outlet />
      </main>
    </div>
  )
}
