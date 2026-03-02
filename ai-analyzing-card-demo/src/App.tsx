import { useState } from 'react';

export default function App() {
  const [isLoading, setIsLoading] = useState(true);

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center p-4 font-sans">
      <div className="space-y-8 flex flex-col items-center">
        <div className="text-center space-y-2">
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">AI Border Animation</h1>
          <p className="text-slate-500 text-sm">Pure CSS rotating border with breathing glow.</p>
        </div>

        {/* The Card with only border animation */}
        <div 
          onClick={() => setIsLoading(!isLoading)}
          className={`ai-analyzing-card ${isLoading ? 'is-loading' : ''} w-64 h-64 shadow-sm transition-all duration-500 cursor-pointer flex items-center justify-center bg-white`}
        >
          <span className="text-slate-300 text-xs font-mono uppercase tracking-widest select-none">
            {isLoading ? 'Active' : 'Idle'}
          </span>
        </div>

        <button
          onClick={() => setIsLoading(!isLoading)}
          className="px-6 py-2 bg-indigo-600 text-white rounded-full font-medium hover:bg-indigo-700 transition-colors shadow-md active:scale-95"
        >
          Toggle Animation
        </button>
      </div>
    </div>
  );
}
