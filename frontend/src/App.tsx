import { Navigate, Route, Routes } from "react-router-dom"

import { AppShell } from "@/components/app-shell"
import { AnalysisPage } from "@/pages/analysis"
import { HomePage } from "@/pages/home"
import { LabPage } from "@/pages/lab"
import { PlayPage } from "@/pages/play"

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<HomePage />} />
        <Route path="jogar" element={<PlayPage />} />
        <Route path="analise" element={<AnalysisPage />} />
        <Route path="laboratorio" element={<LabPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}
