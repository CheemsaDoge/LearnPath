import { Route, Routes } from "react-router-dom";
import { GraphPage } from "./pages/GraphPage";
import { Home } from "./pages/Home";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/g/:graphId" element={<GraphPage />} />
    </Routes>
  );
}
