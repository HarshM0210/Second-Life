import { Routes, Route } from "react-router-dom";
import ReturnInitiate from "./pages/ReturnInitiate";
import ReturnSubmit from "./pages/ReturnSubmit";

function App() {
  return (
    <div className="min-h-screen bg-gray-50">
      <Routes>
        <Route
          path="/"
          element={
            <div className="p-8 text-center text-gray-600">
              Second Life - Returns & Grading
            </div>
          }
        />
        <Route path="/return/initiate" element={<ReturnInitiate />} />
        <Route path="/return/qa" element={<ReturnSubmit />} />
        <Route
          path="/return/health-card"
          element={
            <div className="mx-auto max-w-2xl px-4 py-8">
              <h1 className="text-2xl font-bold text-gray-900">Health Card</h1>
              <p className="mt-2 text-gray-600">
                Health Card display coming soon.
              </p>
            </div>
          }
        />
        <Route
          path="/return/p2p-choice"
          element={
            <div className="mx-auto max-w-2xl px-4 py-8">
              <h1 className="text-2xl font-bold text-gray-900">
                P2P Marketplace Option
              </h1>
              <p className="mt-2 text-gray-600">P2P choice page coming soon.</p>
            </div>
          }
        />
      </Routes>
    </div>
  );
}

export default App;
