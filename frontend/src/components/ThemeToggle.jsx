import React from 'react';
import { Sun, Moon } from 'lucide-react';

export function ThemeToggle({ theme, onChange }) {
  return (
    <div className="flex items-center gap-2">
      <button
        type="button"
        onClick={() => onChange('light')}
        className={
          'mac-button px-3 py-2 text-xs font-medium flex items-center gap-2 ' +
          (theme === 'light' ? 'ring-2 ring-[var(--accent-weak)] border-[color:var(--accent)]' : '')
        }
        aria-pressed={theme === 'light'}
      >
        <Sun className="w-4 h-4" />
        Light
      </button>
      <button
        type="button"
        onClick={() => onChange('dark')}
        className={
          'mac-button px-3 py-2 text-xs font-medium flex items-center gap-2 ' +
          (theme === 'dark' ? 'ring-2 ring-[var(--accent-weak)] border-[color:var(--accent)]' : '')
        }
        aria-pressed={theme === 'dark'}
      >
        <Moon className="w-4 h-4" />
        Dark
      </button>
    </div>
  );
}

