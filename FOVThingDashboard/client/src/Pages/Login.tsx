import React from "react";
import LoginForm from "../components/LoginForm";

type Props = { onLogin: (token: string) => void };

export default function LoginPage({ onLogin }: Props) {
  return (
    <div className="min-h-screen bg-blue-50">
      {/* Logo and Form Container */}
      <div className="flex flex-col items-center justify-center min-h-screen p-8">
        <LoginForm onLogin={onLogin} />
      </div>
    </div>
  );
}
