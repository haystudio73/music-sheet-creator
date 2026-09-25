import { useId, useState, type ReactNode } from 'react';
import { ChevronDown, ChevronUp } from 'lucide-react';
import { t } from './i18n';

export default function CollapsibleSection({
  title,
  children,
  className = '',
  storageKey,
  defaultOpen = true,
}: {
  title: ReactNode;
  children: ReactNode;
  className?: string;
  storageKey?: string;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState<boolean>(() => {
    if (storageKey) {
      try {
        const saved = localStorage.getItem(`box_open_${storageKey}`);
        if (saved !== null) {
          return saved === 'true';
        }
      } catch {}
    }
    return defaultOpen;
  });
  const id = useId();

  const toggle = () => {
    setOpen(previous => {
      const next = !previous;
      if (storageKey) {
        try {
          localStorage.setItem(`box_open_${storageKey}`, String(next));
        } catch {}
      }
      return next;
    });
  };

  return (
    <section className={`collapsible-section ${className}`}>
      <div className="collapse-heading">
        {title}
        <button
          className="icon-button collapse-toggle"
          aria-expanded={open}
          aria-controls={id}
          aria-label={t(open ? 'Thu gọn mục' : 'Mở rộng mục')}
          onClick={toggle}
        >
          {open ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </button>
      </div>
      <div id={id} hidden={!open}>
        {children}
      </div>
    </section>
  );
}
