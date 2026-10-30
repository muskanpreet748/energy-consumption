import { useState } from 'react'
import DecisionDesk from './components/DecisionDesk.jsx'
import AccuracyDashboard from './components/AccuracyDashboard.jsx'
import AboutData from './components/AboutData.jsx'

const TABS = [
  { id: 'decision', label: 'Decision Desk', component: DecisionDesk },
  { id: 'accuracy', label: 'Forecast Accuracy', component: AccuracyDashboard },
  { id: 'about', label: 'About the data', component: AboutData },
]

export default function App() {
  const [active, setActive] = useState('decision')
  const Active = TABS.find((tab) => tab.id === active).component

  return (
    <div className="app">
      <header className="masthead">
        <h1>Wind Decision Desk</h1>
        <p className="subtitle">
          Day-ahead procurement pilot · Great Britain wind · January 2026 · data
          from Elexon BMRS
        </p>
        <nav className="tabs">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              type="button"
              className={`tab ${tab.id === active ? 'active' : ''}`}
              onClick={() => setActive(tab.id)}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </header>

      <main>
        <Active />
      </main>

      <footer className="footer">
        Point-in-time analysis: every figure is measured against the forecast
        published <em>before</em> the 09:50 day-ahead gate closure — never a
        forecast issued after the event.
      </footer>
    </div>
  )
}
