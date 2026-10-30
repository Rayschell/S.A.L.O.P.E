import { useEffect, useState } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import Navbar from './Navbar.jsx'
import Sidebar from './Sidebar.jsx'

const MOBILE_QUERY = '(max-width: 767px)'

export default function Layout() {
  const [isMobile, setIsMobile] = useState(() => window.matchMedia(MOBILE_QUERY).matches)
  const [sidebarOpen, setSidebarOpen] = useState(() => !window.matchMedia(MOBILE_QUERY).matches)
  const location = useLocation()

  useEffect(() => {
    const mq = window.matchMedia(MOBILE_QUERY)
    const onChange = (e) => {
      setIsMobile(e.matches)
      setSidebarOpen(!e.matches)
    }
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [])

  // Sur mobile, le tiroir se referme dès qu'on change de page
  useEffect(() => {
    if (isMobile) setSidebarOpen(false)
  }, [location.pathname, isMobile])

  const inlineSidebar = sidebarOpen && !isMobile

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateRows: '48px 1fr',
        gridTemplateColumns: inlineSidebar ? '200px 1fr' : '1fr',
        height: '100dvh',
        overflow: 'hidden',
      }}
    >
      <Navbar onToggleSidebar={() => setSidebarOpen((v) => !v)} />
      {inlineSidebar && <Sidebar />}
      {isMobile && sidebarOpen && (
        <>
          <div
            onClick={() => setSidebarOpen(false)}
            style={{ position: 'fixed', inset: '48px 0 0 0', background: 'rgba(0,0,0,0.5)', zIndex: 60 }}
          />
          <div style={{ position: 'fixed', top: 48, left: 0, bottom: 0, width: 240, zIndex: 61, display: 'flex' }}>
            <Sidebar />
          </div>
        </>
      )}
      <main
        style={{
          gridRow: 2,
          gridColumn: inlineSidebar ? 2 : 1,
          overflowY: 'auto',
          padding: isMobile ? 12 : 20,
          background: 'var(--bg-base)',
          minWidth: 0,
        }}
      >
        <Outlet />
      </main>
    </div>
  )
}
