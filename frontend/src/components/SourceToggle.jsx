export default function SourceToggle({ value, onChange }) {
  return (
    <div
      role="tablist"
      aria-label="Legislative source selection"
      className="inline-flex items-center p-1 bg-slate-200/80 rounded-xl border border-slate-200 w-full sm:w-auto"
    >
      <button
        type="button"
        role="tab"
        id="tab-source-ls"
        aria-selected={value === 'LS'}
        aria-controls="works-list"
        onClick={() => onChange('LS')}
        className={`flex-1 sm:flex-initial min-h-[44px] px-6 py-2.5 rounded-lg text-sm font-semibold transition-all flex items-center justify-center cursor-pointer ${
          value === 'LS'
            ? 'bg-blue-600 text-white shadow-xs'
            : 'text-slate-600 hover:text-slate-900 hover:bg-slate-200/60'
        }`}
      >
        Lok Sabha
      </button>
      <button
        type="button"
        role="tab"
        id="tab-source-rs"
        aria-selected={value === 'RS'}
        aria-controls="works-list"
        onClick={() => onChange('RS')}
        className={`flex-1 sm:flex-initial min-h-[44px] px-6 py-2.5 rounded-lg text-sm font-semibold transition-all flex items-center justify-center cursor-pointer ${
          value === 'RS'
            ? 'bg-blue-600 text-white shadow-xs'
            : 'text-slate-600 hover:text-slate-900 hover:bg-slate-200/60'
        }`}
      >
        Rajya Sabha
      </button>
    </div>
  );
}
