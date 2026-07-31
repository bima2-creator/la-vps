import React from "react";
import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider } from "@/context/AuthContext";
import { Toaster } from "@/components/ui/sonner";
import ProtectedRoute from "@/components/ProtectedRoute";
import Layout from "@/components/Layout";
import LoginPage from "@/pages/LoginPage";
import DashboardPage from "@/pages/DashboardPage";
import WorkOrdersPage from "@/pages/WorkOrdersPage";
import WorkOrderFormPage from "@/pages/WorkOrderFormPage";
import ReportsPage from "@/pages/ReportsPage";
import UsersPage from "@/pages/UsersPage";
import AuditLogPage from "@/pages/AuditLogPage";
import InvoicesPage from "@/pages/InvoicesPage";
import MasterPerangkatPage from "@/pages/MasterPerangkatPage";
import BankDataPage from "@/pages/BankDataPage";

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route
            element={
              <ProtectedRoute>
                <Layout />
              </ProtectedRoute>
            }
          >
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/workorders" element={<WorkOrdersPage />} />
            <Route
              path="/workorders/new"
              element={
                <ProtectedRoute roles={["admin", "operator"]}>
                  <WorkOrderFormPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/workorders/:id"
              element={
                <ProtectedRoute roles={["admin", "operator"]}>
                  <WorkOrderFormPage />
                </ProtectedRoute>
              }
            />
            <Route path="/reports" element={<ReportsPage />} />
            <Route
              path="/invoices"
              element={
                <ProtectedRoute roles={["admin", "operator"]}>
                  <InvoicesPage />
                </ProtectedRoute>
              }
            />
            <Route path="/perangkat" element={<MasterPerangkatPage />} />
            <Route
              path="/bank-data"
              element={
                <ProtectedRoute roles={["admin"]}>
                  <BankDataPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/users"
              element={
                <ProtectedRoute roles={["admin"]}>
                  <UsersPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/audit"
              element={
                <ProtectedRoute roles={["admin"]}>
                  <AuditLogPage />
                </ProtectedRoute>
              }
            />
          </Route>
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </BrowserRouter>
      <Toaster richColors position="top-right" theme="dark" />
    </AuthProvider>
  );
}
