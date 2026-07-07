import { useState } from "react";
import "./App.css";
import { QueuePage } from "./pages/QueuePage";
import { ReviewPage } from "./pages/ReviewPage";

function App() {
  const [selectedId, setSelectedId] = useState<string | null>(null);

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <div className="logo-mark">
            <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 2 4 5v6c0 5 3.5 8.5 8 11 4.5-2.5 8-6 8-11V5l-8-3Z" />
              <path d="M9 12h6M12 9v6" strokeLinecap="round" />
            </svg>
          </div>
          <div className="brand-text">
            <span className="brand-title">AI Denial Management Agent</span>
            <span className="brand-subtitle">Automated Denial Resolution</span>
          </div>
        </div>
      </header>
      <main className="page-content">
        {selectedId ? (
          <ReviewPage id={selectedId} onBack={() => setSelectedId(null)} />
        ) : (
          <QueuePage onSelect={setSelectedId} />
        )}
      </main>
    </div>
  );
}

export default App;
