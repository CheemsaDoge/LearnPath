import { Route, Routes } from "react-router-dom";
import { Dashboard } from "./pages/Dashboard";
import { GraphPage } from "./pages/GraphPage";
import { Home } from "./pages/Home";
import { Login } from "./pages/Login";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/g/:graphId" element={<GraphPage />} />
      <Route path="/dashboard" element={<Dashboard />} />
      <Route path="/login" element={<Login />} />
    </Routes>
  );
}
