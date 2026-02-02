import { useEffect, useState } from 'react';
import { Menu, X } from 'lucide-react';
import { Link } from 'react-router-dom';
import logoUrl from '../assets/logo.svg';

export function TopBar({
  left,
  title,
  right,
  menuTitle,
  menuItems,
}) {
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    if (!isOpen) return;
    const onKeyDown = (e) => {
      if (e.key === 'Escape') setIsOpen(false);
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [isOpen]);

  return (
    <>
      <header className="sticky top-0 z-20">
        <div className="border-b border-[color:var(--border)] bg-[color:var(--bg)]/60 backdrop-blur-md">
          <div className="max-w-7xl mx-auto px-5 sm:px-6 lg:px-8 h-16 flex items-center justify-between gap-3">
            <div className="min-w-0 flex items-center gap-3">
              <Link to="/" className="flex items-center gap-2 shrink-0" aria-label="Home" title="Home">
                <img src={logoUrl} alt="" className="w-8 h-8 rounded-xl" />
              </Link>
              {left}
              {title ? (
                <div className="min-w-0">
                  <div className="text-sm sm:text-base font-semibold tracking-tight truncate">{title}</div>
                </div>
              ) : null}
            </div>
            <div className="flex items-center gap-2">
              {right}
              <button
                type="button"
                className="mac-btn px-2 py-2 text-xs"
                onClick={() => setIsOpen(true)}
                aria-label="Open menu"
                title="Menu"
              >
                <Menu className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      </header>

      {isOpen && (
        <div className="fixed inset-0 z-30">
          <button
            type="button"
            className="absolute inset-0 bg-black/50"
            onClick={() => setIsOpen(false)}
            aria-label="Close menu overlay"
          />
          <div className="absolute right-4 top-4 w-[320px] max-w-[calc(100vw-2rem)] mac-panel p-4">
            <div className="flex items-center justify-between gap-3">
              <div className="text-sm font-semibold">{menuTitle || 'Menu'}</div>
              <button
                type="button"
                className="mac-btn px-2 py-2 text-xs"
                onClick={() => setIsOpen(false)}
                aria-label="Close menu"
                title="Close"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="pt-3 space-y-2">
              {typeof menuItems === 'function' ? menuItems({ close: () => setIsOpen(false) }) : menuItems}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
